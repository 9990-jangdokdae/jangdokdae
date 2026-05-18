from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# 읽는 순서:
# 1) AnalysisRequest: 코드가 LLM에 넘기기 직전 입력
# 2) LLMAnalysisResponse: Gemini가 바로 반환하는 1차 결과
# 3) AnalysisResponse: 코드 후처리까지 끝난 최종 결과
PointType = Literal["시장반응", "원인", "리스크", "리스크완화", "성장근거", "전망", "핵심수치"]
IssueLayer = Literal["주요 이슈", "직접 촉발 이슈", "시장 해석 이슈", "중장기 전망 이슈"]
IssueType = Literal["시장반응", "원인", "해석", "전망", "리스크", "성장논리", "핵심수치"]


class ArticleMetadata(BaseModel):
    """기사에 붙는 기본 힌트 묶음."""
    company_names: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class CompanyContextRecord(BaseModel):
    name: str
    relation: str = "mentioned"
    ticker: str | None = None
    sector: str | None = None
    metrics: dict[str, str] = Field(default_factory=dict)


class SectorContextRecord(BaseModel):
    name: str
    relation: str = "mentioned"
    metrics: dict[str, str] = Field(default_factory=dict)


class MarketIndicatorRecord(BaseModel):
    name: str
    value: str | None = None
    change: str | None = None


class StructuredContext(BaseModel):
    """회사/섹터/시장 지표를 한 번에 담는 정형 문맥."""
    companies: list[CompanyContextRecord] = Field(default_factory=list)
    sectors: list[SectorContextRecord] = Field(default_factory=list)
    market_indicators: list[MarketIndicatorRecord] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    """대표 기사 본문과 정형 context를 묶은 analyzer 표준 입력."""
    article_id: str
    title: str | None = None
    summary_hint: list[str] = Field(default_factory=list)
    content: str = Field(min_length=20)
    metadata: ArticleMetadata = Field(default_factory=ArticleMetadata)
    cluster_id: str | None = None
    cluster_size: int | None = None
    source_titles: list[str] = Field(default_factory=list)
    context: StructuredContext = Field(default_factory=StructuredContext)


class AnalysisSection(BaseModel):
    title: str
    summary: str


class LLMAnalysisResponse(BaseModel):
    """Gemini가 직접 반환하는 1차 구조화 결과."""
    article_id: str
    summary: str
    selected_issue_candidates: list[str] = Field(default_factory=list)
    issue_selection_reason: str | None = None
    summary_points: list[str] = Field(default_factory=list)
    evidence_sentences: list[str] = Field(default_factory=list)
    analysis_sections: list[AnalysisSection] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    opportunity_factors: list[str] = Field(default_factory=list)


class RelatedCompanyCard(BaseModel):
    name: str
    ticker: str | None = None
    sector: str | None = None
    current_price: str | None = None
    price_change_pct: str | None = None


class RelatedMarketCard(BaseModel):
    name: str
    value: str | None = None
    change_pct: str | None = None


class KeyMetric(BaseModel):
    label: str
    value: str
    emphasis: str | None = None


class SidebarContext(BaseModel):
    """프론트 우측 sidebar에 바로 꽂히는 정형 데이터 묶음."""
    related_companies: list[RelatedCompanyCard] = Field(default_factory=list)
    related_markets: list[RelatedMarketCard] = Field(default_factory=list)
    key_metrics: list[KeyMetric] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    """프론트가 읽는 메인 분석 블록."""
    summary: str | None = None
    selected_issue_candidates: list[str] = Field(default_factory=list)
    issue_selection_reason: str | None = None
    summary_points: list[str] = Field(default_factory=list)
    evidence_sentences: list[str] = Field(default_factory=list)
    analysis_sections: list[AnalysisSection] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    opportunity_factors: list[str] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    """분석 본문과 sidebar를 한 번에 담는 최종 응답."""
    cluster_id: str | None = None
    analysis_summary: AnalysisSummary = Field(default_factory=AnalysisSummary)
    market_context: StructuredContext = Field(default_factory=StructuredContext)
    sidebar_context: SidebarContext = Field(default_factory=SidebarContext)
