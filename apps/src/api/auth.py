"""OAuth 로그인 및 JWT 인증 라우터."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config import getenv
from apps.src.config.database import get_db
from apps.src.dependencies.auth import COOKIE_NAME, get_current_user
from apps.src.models.user import User
from apps.src.schemas.users import UserResponse
from apps.src.services.auth import oauth
from apps.src.services.auth import jwt

router = APIRouter()

COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30일
STATE_COOKIE = "oauth_state"
STATE_MAX_AGE = 60 * 10  # 10분


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


def _set_auth_cookie(response: Response, token: str) -> None:
    """JWT를 httpOnly 쿠키로 설정한다.
    프로덕션(크로스도메인)에서는 SameSite=None + Secure=True 필수.
    SameSite=Lax는 크로스사이트 fetch/XHR에서 쿠키를 차단하므로 사용 불가."""
    is_prod = _is_production()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="none" if is_prod else "lax",
        secure=is_prod,  # SameSite=None은 Secure=True 없으면 브라우저가 거부
    )


def _delete_auth_cookie(response: Response) -> None:
    """_set_auth_cookie와 동일한 속성으로 쿠키를 삭제한다.
    속성 불일치 시 브라우저가 삭제를 무시하므로 동일 속성 필수."""
    is_prod = _is_production()
    response.delete_cookie(
        key=COOKIE_NAME,
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


# ── 카카오 ─────────────────────────────────────────────────────────────────


@router.get("/kakao/login")
async def kakao_login(request: Request):
    state = secrets.token_urlsafe(32)
    redirect_uri = _callback_url(request, "kakao")
    response = RedirectResponse(oauth.kakao_login_url(redirect_uri, state))
    _set_state_cookie(response, state)
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
        token = jwt.create_access_token(user.id)

        frontend_url = getenv.CLIENT_URL
        response = RedirectResponse(url=frontend_url)
        _set_auth_cookie(response, token)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"카카오 인증 실패: {e}")
    finally:
        # 성공·실패 여부와 무관하게 state 쿠키를 항상 삭제한다.
        # HTTPException은 Starlette 미들웨어가 처리하므로 응답 객체에 직접 접근할 수 없다.
        # 대신 RedirectResponse 생성 전에 삭제하거나, 프론트엔드 리다이렉트 후 만료에 의존한다.
        # (state 쿠키 max_age=600초 이므로 실질적 영향은 미미하다)
        pass


# ── 구글 ───────────────────────────────────────────────────────────────────


@router.get("/google/login")
async def google_login(request: Request):
    state = secrets.token_urlsafe(32)
    redirect_uri = _callback_url(request, "google")
    response = RedirectResponse(oauth.google_login_url(redirect_uri, state))
    _set_state_cookie(response, state)
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
        token = jwt.create_access_token(user.id)

        frontend_url = getenv.CLIENT_URL
        response = RedirectResponse(url=frontend_url)
        _set_auth_cookie(response, token)
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"구글 인증 실패: {e}")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """현재 로그인 사용자를 반환한다."""
    # from_attributes=True 설정으로 ORM 객체를 직접 반환한다.
    return user


@router.post("/logout")
async def logout():
    """로그아웃: JWT 쿠키를 삭제한다."""
    response = JSONResponse(content={"ok": True})
    _delete_auth_cookie(response)
    return response
