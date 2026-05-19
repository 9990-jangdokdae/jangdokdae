from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


class ArticleBriefOutput(BaseModel):
    article_pk: int
    article_id: str
    article_order: int = Field(ge=0)
    brief: str = Field(min_length=1)
    core_event: str = Field(min_length=1)
    key_numbers: list[str] = Field(default_factory=list)
    stated_background: list[str] = Field(default_factory=list)
    stated_market_reactions: list[str] = Field(default_factory=list)
    stated_interpretations: list[str] = Field(default_factory=list)
    low_priority_details: list[str] = Field(default_factory=list)


class IssueDocentPlanParagraph(BaseModel):
    section: Literal[
        "fact",
        "background",
        "performance_detail",
        "policy_detail",
        "market_reaction",
    ]
    source_article_orders: list[int] = Field(min_length=1)
    facts: list[str] = Field(min_length=1, max_length=3)


class IssueDocentContentPlanOutput(BaseModel):
    central_article_order: int = Field(ge=0)
    central_issue: str = Field(min_length=1)
    selected_article_orders: list[int] = Field(min_length=1, max_length=3)
    omitted_article_orders: list[int] = Field(default_factory=list)
    paragraphs: list[IssueDocentPlanParagraph] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def validate_article_order_consistency(
        self,
        info: ValidationInfo,
    ) -> "IssueDocentContentPlanOutput":
        selected = set(self.selected_article_orders)
        omitted = set(self.omitted_article_orders)
        if info.context and "available_article_orders" in info.context:
            available = set(info.context["available_article_orders"])
            if not selected <= available:
                raise ValueError("selected_article_orders must have available article briefs")
        if info.context and "allowed_plan_sections" in info.context:
            allowed_sections = set(info.context["allowed_plan_sections"])
            for paragraph in self.paragraphs:
                if paragraph.section not in allowed_sections:
                    raise ValueError("paragraph section must be allowed in this generation context")
        if self.central_article_order not in selected:
            raise ValueError("central_article_order must be included in selected_article_orders")
        if selected & omitted:
            raise ValueError("selected_article_orders and omitted_article_orders must not overlap")
        for paragraph in self.paragraphs:
            sources = set(paragraph.source_article_orders)
            if not sources <= selected:
                raise ValueError("paragraph source_article_orders must be selected articles")
        return self


class IssueDocentContentOutput(BaseModel):
    title: str = Field(
        min_length=1,
        description="중심 기사에서 다루는 회사나 상품과 핵심 변화를 바탕으로 한 쉬운 제목",
    )
    teaser: str = Field(
        min_length=1,
        description="목록 카드용 짧은 소개",
    )
    summary: str = Field(
        min_length=1,
        description="상세 본문",
    )

    @field_validator("title")
    @classmethod
    def reject_numeric_title(cls, title: str) -> str:
        if any(char.isdigit() for char in title):
            raise ValueError("title must not include numbers")
        return title

    @field_validator("title", "teaser", "summary")
    @classmethod
    def reject_model_judgment_phrasing(cls, value: str) -> str:
        blocked_phrases = ("보입니다", "보이며", "풀이됩니다", "분석됩니다")
        if any(phrase in value for phrase in blocked_phrases):
            raise ValueError("content must not use model judgment phrasing")
        return value

    @model_validator(mode="after")
    def validate_summary_paragraph_count(self, info: ValidationInfo) -> "IssueDocentContentOutput":
        if not info.context or "min_summary_paragraphs" not in info.context:
            return self
        min_summary_paragraphs = int(info.context["min_summary_paragraphs"])
        paragraph_count = len(
            [paragraph for paragraph in self.summary.split("\n\n") if paragraph.strip()]
        )
        if paragraph_count < min_summary_paragraphs:
            raise ValueError("summary must keep the requested paragraph separation")
        return self


class IssueDocentQuiz(BaseModel):
    quiz_id: str | None = None
    kind: Literal["term", "issue"]
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    answer_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=1)

    @field_validator("options")
    @classmethod
    def reject_empty_options(cls, options: list[str]) -> list[str]:
        if any(not option.strip() for option in options):
            raise ValueError("options must not contain empty strings")
        return options


class QuizOutput(BaseModel):
    quizzes: list[IssueDocentQuiz] = Field(min_length=2, max_length=2)

    @classmethod
    def model_validate_with_term_candidates(
        cls,
        value: object,
        *,
        has_term_candidates: bool,
    ) -> "QuizOutput":
        return cls.model_validate(
            value,
            context={"has_term_candidates": has_term_candidates},
        )

    @model_validator(mode="after")
    def validate_quiz_kinds(self, info: ValidationInfo) -> "QuizOutput":
        if not info.context or "has_term_candidates" not in info.context:
            return self
        has_term_candidates = bool(info.context["has_term_candidates"])
        kinds = [quiz.kind for quiz in self.quizzes]
        expected = ["term", "issue"] if has_term_candidates else ["issue", "issue"]
        if kinds != expected:
            raise ValueError(f"quiz kinds must be {expected}")
        return self
