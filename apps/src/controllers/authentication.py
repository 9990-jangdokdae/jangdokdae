"""OAuth 로그인 및 JWT 인증 라우터."""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.db_session_factory import get_db
from apps.src.models.user import User
from apps.src.services.authentication import oauth
from apps.src.utils import jwt_utils

router = APIRouter()

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30일


def _callback_url(request: Request, provider: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/auth/{provider}/callback"


async def _upsert_user(session: AsyncSession, user_info: dict) -> User:
    """provider + provider_id로 사용자를 찾거나 생성한다."""
    stmt = select(User).where(
        User.provider == user_info["provider"],
        User.provider_id == user_info["provider_id"],
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(**user_info)
        session.add(user)
    else:
        user.nickname = user_info["nickname"]

    await session.commit()
    await session.refresh(user)
    return user


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
        secure=False,  # 로컬 개발용 (프로덕션에서는 True)
    )


# ── 카카오 ─────────────────────────────────────────────────────────────────


@router.get("/kakao/login")
async def kakao_login(request: Request):
    redirect_uri = _callback_url(request, "kakao")
    return RedirectResponse(oauth.kakao_login_url(redirect_uri))


@router.get("/kakao/callback")
async def kakao_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    try:
        user_info = await oauth.kakao_fetch_user(code, _callback_url(request, "kakao"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"카카오 인증 실패: {e}")

    user = await _upsert_user(session, user_info)
    token = jwt_utils.create_access_token(user.id)

    frontend_url = os.environ.get("CLIENT_URL", "http://localhost:3000")
    response = RedirectResponse(url=frontend_url)
    _set_auth_cookie(response, token)
    return response


# ── 구글 ───────────────────────────────────────────────────────────────────


@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = _callback_url(request, "google")
    return RedirectResponse(oauth.google_login_url(redirect_uri))


@router.get("/google/callback")
async def google_callback(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    try:
        user_info = await oauth.google_fetch_user(code, _callback_url(request, "google"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"구글 인증 실패: {e}")

    user = await _upsert_user(session, user_info)
    token = jwt_utils.create_access_token(user.id)

    frontend_url = os.environ.get("CLIENT_URL", "http://localhost:3000")
    response = RedirectResponse(url=frontend_url)
    _set_auth_cookie(response, token)
    return response


# ── 공통 ───────────────────────────────────────────────────────────────────


@router.get("/me")
async def get_me(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """쿠키의 JWT를 검증하고 현재 사용자를 반환한다."""
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

    return {
        "id": str(user.id),
        "nickname": user.nickname,
        "provider": user.provider,
    }


@router.post("/logout")
async def logout():
    response = Response(content='{"ok": true}', media_type="application/json")
    response.delete_cookie(COOKIE_NAME)
    return response
