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
    section: Literal["fact", "background", "market_reaction"]
    source_article_orders: list[int] = Field(min_length=1)
    facts: list[str] = Field(min_length=1, max_length=3)


class IssueDocentContentPlanOutput(BaseModel):
    central_article_order: int = Field(ge=0)
    central_issue: str = Field(min_length=1)
    selected_article_orders: list[int] = Field(min_length=1, max_length=3)
    omitted_article_orders: list[int] = Field(default_factory=list)
    paragraphs: list[IssueDocentPlanParagraph] = Field(min_length=1, max_length=3)


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
