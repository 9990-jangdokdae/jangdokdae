"""Analyzer API.

issue-docent 상세가 요약/퀴즈를 담당한다면,
여기서는 cluster_id 기준으로 분석 본문과 sidebar 데이터를 제공한다.
"""

from typing import Any

from fastapi import APIRouter

from apps.src.models.analyzer_dto import AnalysisResponse, SidebarContext
from apps.src.services.analyzer.analyzer_service import ClusterAnalyzerService

router = APIRouter()


@router.get("/health")
def analysis_health() -> dict[str, str]:
    return {"status": "ok", "service": "analyzer"}


@router.get("/sidebar-context/{cluster_id}", response_model=SidebarContext)
def get_sidebar_context(cluster_id: str) -> SidebarContext:
    service = ClusterAnalyzerService()
    return service.build_sidebar_context_from_db(cluster_id)


# issue-docent 상세와 별도로, analyzer 본문/초기 sidebar를 cluster_id 기준으로 제공한다.
@router.get("/detail/{cluster_id}", response_model=AnalysisResponse)
def get_analysis_detail(cluster_id: str) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    return service.analyze_cluster_from_db(cluster_id)


@router.post("/analyze-cluster", response_model=AnalysisResponse)
def analyze_cluster(request: dict[str, Any]) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    return service.analyze_cluster(request)


@router.post("/analyze-clusters", response_model=list[AnalysisResponse])
def analyze_clusters(request: dict[str, Any] | list[dict[str, Any]]) -> list[AnalysisResponse]:
    service = ClusterAnalyzerService()
    return service.analyze_clusters(request)
