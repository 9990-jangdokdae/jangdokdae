"""사용자 관심 프로필 및 analyzer 라우터."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.config.sectors import SECTORS
from apps.src.dependencies.auth import get_current_user
from apps.src.models.DTO import AnalysisResponse, SidebarContext
from apps.src.models.user import User
from apps.src.schemas.users import InterestProfileBody, InterestProfileResponse
from apps.src.services.analyzer.analyzer_service import ClusterAnalyzerService

router = APIRouter()
analyzer_router = APIRouter()


@router.get("/sectors")
async def get_sectors():
    """섹터 목록을 반환한다. sectors.py가 단일 진실 소스."""
    return {"sectors": SECTORS}


@router.get("/profile", response_model=InterestProfileResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """현재 로그인 사용자의 관심 프로필(섹터·종목)을 반환한다."""
    return InterestProfileResponse(
        sectors=user.interest_sectors,
        companies=user.interest_companies,
    )


@router.put("/profile", response_model=InterestProfileResponse)
async def update_profile(
    body: InterestProfileBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """현재 로그인 사용자의 관심 프로필을 수정한다.
    get_current_user와 별도 세션이 주입되므로 user.id로 재조회 후 수정한다.
    """
    result = await session.execute(select(User).where(User.id == user.id))
    db_user = result.scalar_one()
    db_user.interest_sectors = body.sectors
    db_user.interest_companies = body.companies
    await session.commit()
    return InterestProfileResponse(
        sectors=db_user.interest_sectors,
        companies=db_user.interest_companies,
    )


@analyzer_router.get("/health")
def analysis_health() -> dict[str, str]:
    return {"status": "ok", "service": "analyzer"}


@analyzer_router.get("/sidebar-context/{cluster_id}", response_model=SidebarContext)
def get_sidebar_context(cluster_id: str) -> SidebarContext:
    service = ClusterAnalyzerService()
    return service.build_sidebar_context_from_db(cluster_id)


# issue-docent 상세와 별도로, analyzer 본문/초기 sidebar를 cluster_id 기준으로 제공한다.
@analyzer_router.get("/detail/{cluster_id}", response_model=AnalysisResponse)
def get_analysis_detail(cluster_id: str) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    return service.analyze_cluster_from_db(cluster_id)


@analyzer_router.post("/analyze-cluster", response_model=AnalysisResponse)
def analyze_cluster(request: dict[str, Any]) -> AnalysisResponse:
    service = ClusterAnalyzerService()
    return service.analyze_cluster(request)


@analyzer_router.post("/analyze-clusters", response_model=list[AnalysisResponse])
def analyze_clusters(request: dict[str, Any] | list[dict[str, Any]]) -> list[AnalysisResponse]:
    service = ClusterAnalyzerService()
    return service.analyze_clusters(request)


@analyzer_router.post("/analyze", response_model=AnalysisResponse, include_in_schema=False)
def analyze_legacy_cluster(request: dict[str, Any]) -> AnalysisResponse:
    return analyze_cluster(request)


@analyzer_router.post("/analyze-batch", response_model=list[AnalysisResponse], include_in_schema=False)
def analyze_legacy_clusters(request: dict[str, Any] | list[dict[str, Any]]) -> list[AnalysisResponse]:
    return analyze_clusters(request)
