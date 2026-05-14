"""FastAPI 인증 의존성.

authentication.py와 user_info.py 양쪽에서 동일하게 사용할 수 있도록
JWT 검증 + 사용자 조회 로직을 단일 FastAPI Dependency로 분리한다.
"""

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.models.user import User
from apps.src.services.auth import jwt

COOKIE_NAME = "access_token"


async def get_current_user(
    access_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
) -> User:
    """httpOnly 쿠키의 JWT를 검증하고 User 객체를 반환한다. 실패 시 401."""
    if not access_token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")

    user_id = jwt.decode_access_token(access_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")

    return user
