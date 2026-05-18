from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MatchedTerm(BaseModel):
    term_id: int
    term: str
    category: str
    definition: str
    start: int
    end: int


class SummaryParagraph(BaseModel):
    text: str
    matched_terms: list[MatchedTerm] = []


class SummaryContent(BaseModel):
    paragraphs: list[SummaryParagraph]


class SourceArticle(BaseModel):
    article_id: str
    title: str
    press: str | None
    published_date: datetime
    url: str


class IssueDocentQuiz(BaseModel):
    quiz_id: str
    kind: Literal["term", "issue"]
    question: str
    options: list[str]
    answer_index: int
    explanation: str


class SectorCompany(BaseModel):
    company_id: int | None
    name: str
    market: str | None


class SectorCompanies(BaseModel):
    sector: str | None
    companies: list[SectorCompany]


class IssueDocentListItem(BaseModel):
    id: int
    cluster_id: int
    title: str
    teaser: str
    sector_companies: list[SectorCompanies]
    article_count: int
    created_at: datetime


class IssueDocentListResponse(BaseModel):
    items: list[IssueDocentListItem]
    total: int
    limit: int
    offset: int


class IssueDocentDetailResponse(BaseModel):
    id: int
    cluster_id: int
    title: str
    teaser: str
    sector_companies: list[SectorCompanies]
    article_count: int
    summary: SummaryContent
    articles: list[SourceArticle]
    quizzes: list[IssueDocentQuiz]
    created_at: datetime
