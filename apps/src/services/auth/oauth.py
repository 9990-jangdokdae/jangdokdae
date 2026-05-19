"""카카오 / 구글 OAuth API 호출 로직."""

import urllib.parse

import httpx

from apps.src.config import getenv

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── 카카오 ─────────────────────────────────────────────────────────────────


def kakao_login_url(redirect_uri: str, state: str) -> str:
    """state 포함 카카오 OAuth 인가 URL을 반환한다. (RFC 6749 §10.12 CSRF 방지)"""
    params = {
        "client_id": getenv.KAKAO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    return f"{KAKAO_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def kakao_fetch_user(code: str, redirect_uri: str) -> dict:
    """인가 코드로 카카오 사용자 정보를 가져온다."""
    async with httpx.AsyncClient() as client:
        # 1. access_token 교환
        token_res = await client.post(
            KAKAO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": getenv.KAKAO_CLIENT_ID,
                "client_secret": getenv.KAKAO_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        # 2. 사용자 정보 조회
        user_res = await client.get(
            KAKAO_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_res.raise_for_status()
        data = user_res.json()

    kakao_account = data.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    return {
        "provider": "kakao",
        "provider_id": str(data["id"]),
        "nickname": profile.get("nickname", "카카오 사용자"),
    }


# ── 구글 ───────────────────────────────────────────────────────────────────


def google_login_url(redirect_uri: str, state: str) -> str:
    """state 포함 구글 OAuth 인가 URL을 반환한다. (RFC 6749 §10.12 CSRF 방지)"""
    params = {
        "client_id": getenv.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def google_fetch_user(code: str, redirect_uri: str) -> dict:
    """인가 코드로 구글 사용자 정보를 가져온다."""
    async with httpx.AsyncClient() as client:
        # 1. access_token 교환
        token_res = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": getenv.GOOGLE_CLIENT_ID,
                "client_secret": getenv.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        # 2. 사용자 정보 조회
        user_res = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_res.raise_for_status()
        data = user_res.json()

    return {
        "provider": "google",
        "provider_id": data["sub"],
        "nickname": data.get("name", "구글 사용자"),
    }
