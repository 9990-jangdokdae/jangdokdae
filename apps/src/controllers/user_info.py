"""사용자 관심 프로필 및 섹터 목록 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.db_session_factory import get_db
from apps.src.config.sectors import SECTORS
from apps.src.models.user import User
from apps.src.utils import jwt_utils

router = APIRouter()

COOKIE_NAME = "access_token"


async def _get_current_user(request: Request, session: AsyncSession) -> User:
    """쿠키의 JWT를 검증하고 현재 사용자를 반환한다. 인증 실패 시 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    user_id = jwt_utils.decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    return user


class InterestProfileBody(BaseModel):
    sectors: list[str]
    companies: list[str]


@router.get("/sectors")
async def getSectors():
    """섹터 목록을 반환한다. sectors.py가 단일 진실 소스."""
    return {"sectors": SECTORS}


@router.get("/profile")
async def getProfile(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """현재 로그인 사용자의 관심 프로필(섹터·종목)을 반환한다."""
    user = await _get_current_user(request, session)
    return {
        "sectors": user.interest_sectors,
        "companies": user.interest_companies,
    }


@router.put("/profile")
async def updateProfile(
    body: InterestProfileBody,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """현재 로그인 사용자의 관심 프로필을 저장한다."""
    user = await _get_current_user(request, session)
    user.interest_sectors = body.sectors
    user.interest_companies = body.companies
    await session.commit()
    return {"sectors": user.interest_sectors, "companies": user.interest_companies}
