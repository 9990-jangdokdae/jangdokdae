import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from apps.src.repositories.issue_docent import ArticleForGeneration, ClusterGenerationContext
from apps.src.schemas.issue_docent_llm import (
    ArticleBriefOutput,
    IssueDocentContentOutput,
    QuizOutput,
)
from apps.src.services.issue_docent.term_matcher import StockTermForMatch


class IssueDocentPersistPayload(BaseModel):
    cluster_id: int
    title: str = Field(min_length=1)
    teaser: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    quizzes: list[dict] = Field(min_length=2, max_length=2)


class IssueDocentState(TypedDict, total=False):
    cluster: ClusterGenerationContext
    article: ArticleForGeneration
    stock_terms: list[StockTermForMatch]
    article_briefs: Annotated[list[ArticleBriefOutput], operator.add]
    issue_docent_content: IssueDocentContentOutput
    quiz_term_candidates: list[dict]
    quizzes: QuizOutput
    persist_payload: IssueDocentPersistPayload
