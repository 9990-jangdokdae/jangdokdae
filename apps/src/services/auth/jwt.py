"""JWT 생성 및 검증 유틸리티."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from apps.src.config import getenv

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        getenv.JWT_SECRET,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> int | None:
    """토큰을 검증하고 user_id를 반환한다. 유효하지 않으면 None."""
    try:
        payload = jwt.decode(token, getenv.JWT_SECRET, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
