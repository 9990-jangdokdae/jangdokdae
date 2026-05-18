"""Analyzer API.

issue-docent 상세가 요약/퀴즈를 담당한다면,
여기서는 cluster_id 기준으로 분석 본문과 sidebar 데이터를 제공한다.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.models.analyzer_dto import AnalysisResponse, SidebarContext
from apps.src.repositories.article_analysis import ArticleAnalysisRepository
from apps.src.services.analyzer.analyzer_service import ClusterAnalyzerService

router = APIRouter()


@router.get("/health")
def analysis_health() -> dict[str, str]:
    return {"status": "ok", "service": "analyzer"}


@router.get("/sidebar-context/{cluster_id}", response_model=SidebarContext)
async def get_sidebar_context(
    cluster_id: str,
    session: AsyncSession = Depends(get_db),
) -> SidebarContext:
    service = ClusterAnalyzerService()
    repository = ArticleAnalysisRepository(session)
    response = await service.get_live_sidebar_context(cluster_id, repository)
    if response is None:
        raise HTTPException(status_code=404, detail="Analyzer result not found")
    return response


# issue-docent 상세와 별도로, analyzer 본문/초기 sidebar를 cluster_id 기준으로 제공한다.
@router.get("/detail/{cluster_id}", response_model=AnalysisResponse)
async def get_analysis_detail(
    cluster_id: str,
    session: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    repository = ArticleAnalysisRepository(session)
    response = await service.get_persisted_analysis(cluster_id, repository)
    if response is None:
        raise HTTPException(status_code=404, detail="Analyzer result not found")
    return response


@router.post("/persist/{cluster_id}", response_model=AnalysisResponse)
async def persist_analysis_detail(
    cluster_id: str,
    session: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    repository = ArticleAnalysisRepository(session)
    response = await service.persist_analysis_from_db(cluster_id, repository)
    await session.commit()
    return response


@router.post("/analyze-cluster", response_model=AnalysisResponse)
def analyze_cluster(request: dict[str, Any]) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    return service.analyze_cluster(request)


@router.post("/analyze-clusters", response_model=list[AnalysisResponse])
def analyze_clusters(request: dict[str, Any] | list[dict[str, Any]]) -> list[AnalysisResponse]:
    service = ClusterAnalyzerService()
    return service.analyze_clusters(request)
