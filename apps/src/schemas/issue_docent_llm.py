from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


class ArticleBriefOutput(BaseModel):
    article_pk: int
    article_id: str
    article_order: int = Field(ge=0)
    brief: str = Field(min_length=1)
    key_facts: list[str] = Field(default_factory=list)
    source_views: list[str] = Field(default_factory=list)


class SummaryPoints(BaseModel):
    core_event: list[str] = Field(default_factory=list)
    market_reaction: list[str] = Field(default_factory=list)
    source_views: list[str] = Field(default_factory=list)
    not_clear_points: list[str] = Field(default_factory=list)
    preserved_evidence: list[str] = Field(default_factory=list)


class ClusterSummaryOutput(BaseModel):
    title: str = Field(min_length=1)
    teaser: str = Field(min_length=1)
    summary_points: SummaryPoints
    summary: str = Field(min_length=1)


SectionType = Literal[
    "what_happened",
    "why_it_matters",
    "expert_view",
    "what_is_not_clear",
    "wrap_up",
]

REQUIRED_SECTION_TYPES = {"what_happened", "why_it_matters", "wrap_up"}


class IssueDocentSection(BaseModel):
    section_type: SectionType
    title: str = Field(min_length=1)
    paragraphs: list[str] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def reject_empty_paragraphs(self) -> "IssueDocentSection":
        if any(not paragraph.strip() for paragraph in self.paragraphs):
            raise ValueError("paragraphs must not contain empty strings")
        return self


class IssueDocentOutput(BaseModel):
    explanation: list[IssueDocentSection] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_required_sections(self) -> "IssueDocentOutput":
        section_types = [section.section_type for section in self.explanation]
        missing = REQUIRED_SECTION_TYPES - set(section_types)
        if missing:
            raise ValueError(f"missing required sections: {sorted(missing)}")
        if len(section_types) != len(set(section_types)):
            raise ValueError("section_type values must be unique")
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
