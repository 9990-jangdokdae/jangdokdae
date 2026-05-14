"""사용자 관심 프로필 및 섹터 목록 라우터."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.config.sectors import SECTORS
from apps.src.dependencies.auth import get_current_user
from apps.src.models.user import User
from apps.src.schemas.users import InterestProfileBody, InterestProfileResponse

router = APIRouter()


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
