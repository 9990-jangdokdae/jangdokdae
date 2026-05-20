"""OAuth 로그인 및 JWT 인증 라우터."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config import getenv
from apps.src.config.database import get_db
from apps.src.dependencies.auth import COOKIE_NAME, get_current_user
from apps.src.models.user import User
from apps.src.repositories import refresh_token as refresh_token_repo
from apps.src.schemas.users import UserResponse
from apps.src.services.auth import jwt
from apps.src.services.auth import oauth

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_EXPIRE_DAYS = 7
STATE_COOKIE = "oauth_state"
STATE_MAX_AGE = 60 * 10  # 10분
RETURN_URL_COOKIE = "return_url"
RETURN_URL_MAX_AGE = 60 * 10  # 10분


def _is_production() -> bool:
    return getenv.APP_ENV == "production"


def _callback_url(request: Request, provider: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/auth/{provider}/callback"


async def _upsert_user(session: AsyncSession, user_info: dict) -> User:
    """provider + provider_id로 사용자를 찾거나 생성한다.
    INSERT ... ON CONFLICT DO UPDATE를 사용해 동시 요청에도 안전하다.
    """
    stmt = (
        pg_insert(User)
        .values(**user_info)
        .on_conflict_do_update(
            index_elements=["provider", "provider_id"],
            set_={"nickname": user_info["nickname"]},
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    user = result.scalar_one()
    await session.commit()
    return user


def _set_access_cookie(response: Response, token: str) -> None:
    """Access Token을 session cookie로 설정한다.
    max_age 없음 → 브라우저 완전 종료 시 자동 삭제.
    SameSite=Lax는 크로스사이트 fetch/XHR에서 쿠키를 차단하므로 프로덕션에서 사용 불가."""
    is_prod = _is_production()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="none" if is_prod else "lax",
        secure=is_prod,
    )


def _delete_access_cookie(response: Response) -> None:
    """_set_access_cookie와 동일한 속성으로 쿠키를 삭제한다."""
    is_prod = _is_production()
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        samesite="none" if is_prod else "lax",
        secure=is_prod,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Refresh Token을 session cookie로 설정한다."""
    is_prod = _is_production()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="none" if is_prod else "lax",
        secure=is_prod,
    )


def _delete_refresh_cookie(response: Response) -> None:
    """_set_refresh_cookie와 동일한 속성으로 쿠키를 삭제한다."""
    is_prod = _is_production()
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        samesite="none" if is_prod else "lax",
        secure=is_prod,
    )


def _set_state_cookie(response: Response, state: str) -> None:
    """CSRF 방지용 OAuth state를 단수명 쿠키에 저장한다."""
    response.set_cookie(
        key=STATE_COOKIE,
        value=state,
        httponly=True,
        max_age=STATE_MAX_AGE,
        samesite="lax",
        secure=_is_production(),
    )


def _validate_state(request: Request, state: str | None) -> None:
    """콜백에서 state 파라미터와 쿠키를 대조해 CSRF를 방지한다."""
    stored = request.cookies.get(STATE_COOKIE)
    if not stored or stored != state:
        raise HTTPException(status_code=400, detail="잘못된 인증 요청입니다")


def _safe_return_url(url: str) -> str:
    """오픈 리다이렉트 방지: 상대 경로(/)만 허용, 그 외는 홈으로."""
    if url.startswith("/") and not url.startswith("//"):
        return url
    return "/"


async def _issue_token_pair(
    response: Response, session: AsyncSession, user_id: int
) -> None:
    """Access Token + Refresh Token을 발급해 쿠키에 설정하고 DB에 저장한다."""
    access_token = jwt.create_access_token(user_id)
    raw_rt = jwt.create_refresh_token()
    rt_hash = jwt.hash_token(raw_rt)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    await refresh_token_repo.create(session, user_id, rt_hash, expires_at)
    await session.commit()

    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, raw_rt)


# ── 카카오 ─────────────────────────────────────────────────────────────────


@router.get("/kakao/login")
async def kakao_login(request: Request, return_url: str = "/"):
    state = secrets.token_urlsafe(32)
    redirect_uri = _callback_url(request, "kakao")
    response = RedirectResponse(oauth.kakao_login_url(redirect_uri, state))
    _set_state_cookie(response, state)
    response.set_cookie(
        key=RETURN_URL_COOKIE,
        value=_safe_return_url(return_url),
        httponly=True,
        max_age=RETURN_URL_MAX_AGE,
        samesite="lax",
        secure=_is_production(),
    )
    return response


@router.get("/kakao/callback")
async def kakao_callback(
    request: Request,
    code: str,
    state: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    _validate_state(request, state)

    try:
        user_info = await oauth.kakao_fetch_user(code, _callback_url(request, "kakao"))
        user = await _upsert_user(session, user_info)

        return_path = _safe_return_url(request.cookies.get(RETURN_URL_COOKIE, "/"))
        response = RedirectResponse(url=f"{getenv.CLIENT_URL}{return_path}")
        response.delete_cookie(key=RETURN_URL_COOKIE)
        await _issue_token_pair(response, session, user.id)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"카카오 인증 실패: {e}")


# ── 구글 ───────────────────────────────────────────────────────────────────


@router.get("/google/login")
async def google_login(request: Request, return_url: str = "/"):
    state = secrets.token_urlsafe(32)
    redirect_uri = _callback_url(request, "google")
    response = RedirectResponse(oauth.google_login_url(redirect_uri, state))
    _set_state_cookie(response, state)
    response.set_cookie(
        key=RETURN_URL_COOKIE,
        value=_safe_return_url(return_url),
        httponly=True,
        max_age=RETURN_URL_MAX_AGE,
        samesite="lax",
        secure=_is_production(),
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    _validate_state(request, state)

    try:
        user_info = await oauth.google_fetch_user(code, _callback_url(request, "google"))
        user = await _upsert_user(session, user_info)

        return_path = _safe_return_url(request.cookies.get(RETURN_URL_COOKIE, "/"))
        response = RedirectResponse(url=f"{getenv.CLIENT_URL}{return_path}")
        response.delete_cookie(key=RETURN_URL_COOKIE)
        await _issue_token_pair(response, session, user.id)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"구글 인증 실패: {e}")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """현재 로그인 사용자를 반환한다."""
    return user


@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
):
    """Refresh Token으로 새 Access Token + Refresh Token을 발급한다 (Rotation)."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다")

    token_hash = jwt.hash_token(refresh_token)
    db_token = await refresh_token_repo.get_by_hash(session, token_hash)

    if db_token is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")

    if db_token.revoked:
        # 이미 사용된 토큰 재사용 → 탈취 감지, 해당 유저의 모든 토큰 폐기
        await refresh_token_repo.revoke_all_for_user(session, db_token.user_id)
        await session.commit()
        # HTTPException은 injected Response의 쿠키를 무시하므로 JSONResponse를 직접 반환
        error_response = JSONResponse(
            status_code=401,
            content={"detail": "보안 위협이 감지되었습니다. 다시 로그인해주세요"},
        )
        _delete_access_cookie(error_response)
        _delete_refresh_cookie(error_response)
        return error_response

    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="리프레시 토큰이 만료되었습니다")

    # Rotation: 기존 토큰 폐기 + 만료 토큰 정리 후 새 토큰 쌍 발급 (동일 트랜잭션)
    await refresh_token_repo.revoke(session, token_hash)
    user_id = db_token.user_id
    await refresh_token_repo.delete_expired_for_user(session, user_id)

    new_access = jwt.create_access_token(user_id)
    new_raw_rt = jwt.create_refresh_token()
    new_rt_hash = jwt.hash_token(new_raw_rt)
    new_expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    await refresh_token_repo.create(session, user_id, new_rt_hash, new_expires)
    await session.commit()

    _set_access_cookie(response, new_access)
    _set_refresh_cookie(response, new_raw_rt)
    return {"ok": True}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    session: AsyncSession = Depends(get_db),
):
    """로그아웃: DB에서 Refresh Token을 폐기하고 양쪽 쿠키를 삭제한다."""
    if refresh_token:
        await refresh_token_repo.revoke(session, jwt.hash_token(refresh_token))
        await session.commit()
    _delete_access_cookie(response)
    _delete_refresh_cookie(response)
    return {"ok": True}
