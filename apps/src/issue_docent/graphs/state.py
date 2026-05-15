import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

from apps.src.repositories.issue_docent import ArticleForGeneration, ClusterGenerationContext
from apps.src.schemas.issue_docent_llm import (
    ArticleBriefOutput,
    ClusterSummaryOutput,
    IssueDocentOutput,
    QuizOutput,
)
from apps.src.services.issue_docent.term_matcher import StockTermForMatch


class IssueDocentPersistPayload(BaseModel):
    cluster_id: int
    title: str = Field(min_length=1)
    teaser: str = Field(min_length=1)
    summary: dict[str, Any]
    explanation: list[dict] = Field(min_length=3, max_length=5)
    quizzes: list[dict] = Field(min_length=2, max_length=2)


class IssueDocentState(TypedDict, total=False):
    cluster: ClusterGenerationContext
    article: ArticleForGeneration
    stock_terms: list[StockTermForMatch]
    article_briefs: Annotated[list[ArticleBriefOutput], operator.add]
    cluster_summary: ClusterSummaryOutput
    issue_docent: IssueDocentOutput
    quiz_term_candidates: list[dict]
    quizzes: QuizOutput
    persist_payload: IssueDocentPersistPayload
