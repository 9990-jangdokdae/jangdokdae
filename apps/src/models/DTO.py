from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PointType = Literal["시장반응", "원인", "리스크", "리스크완화", "성장근거", "전망", "핵심수치"]
IssueLayer = Literal["주요 이슈", "직접 촉발 이슈", "시장 해석 이슈", "중장기 전망 이슈"]
IssueType = Literal["시장반응", "원인", "해석", "전망", "리스크", "성장논리", "핵심수치"]


class ArticleMetadata(BaseModel):
    company_names: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    article_id: str
    title: str | None = None
    summary_hint: list[str] = Field(default_factory=list)
    content: str = Field(min_length=20)
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata)


class KeyNumberRecord(BaseModel):
    label: str
    value: str
    entity: str | None = None
    time_context: str | None = None


class IssueCandidateRecord(BaseModel):
    issue_id: str
    issue: str
    issue_layer: IssueLayer
    issue_type: IssueType
    related_entities: list[str] = Field(default_factory=list)
    supporting_sentences: list[str] = Field(default_factory=list)
    centrality_score: int = 3
    market_relevance_score: int = 3
    support_strength_score: int = 3
    forward_value_score: int = 3
    entity_focus_score: int = 3
    is_primary: bool = False


class AnalysisPointRecord(BaseModel):
    point_id: str
    linked_issue_id: str | None = None
    point: str
    point_type: PointType
    summary_role: str
    issue_layer: IssueLayer | None = None
    key_numbers: list[KeyNumberRecord] = Field(default_factory=list)
    related_entity: list[str] = Field(default_factory=list)
    evidence_sentence: str
    evidence_sentences: list[str] = Field(default_factory=list)
    is_source_grounded: bool = True


class CoverageCheck(BaseModel):
    primary_issue_checked: bool = False
    market_reaction_checked: bool = False
    cause_checked: bool = False
    risk_checked: bool = False
    market_interpretation_checked: bool = False
    growth_or_outlook_checked: bool = False
    outlook_checked: bool = False
    key_numbers_checked: bool = False


class AnalysisResponse(BaseModel):
    article_id: str
    news_type: str
    primary_issue_id: str | None = None
    summary: str
    issue_candidates: list[IssueCandidateRecord] = Field(default_factory=list)
    secondary_issue_ids: list[str] = Field(default_factory=list)
    summary_points: list[AnalysisPointRecord] = Field(default_factory=list)
    coverage_check: CoverageCheck
    debug: dict[str, Any] = Field(default_factory=dict)
