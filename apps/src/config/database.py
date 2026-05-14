import os
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from pgvector.sqlalchemy import Vector  # noqa: F401 — vector 타입 등록


def _asyncpg_url(url: str) -> str:
    """Neon 표준 URL(postgresql://)을 asyncpg 드라이버 URL로 변환."""
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    url = url.replace("sslmode=require", "ssl=require")
    url = url.replace("&channel_binding=require", "").replace("channel_binding=require&", "")
    return url


def AsyncSessionLocal() -> AsyncSession:
    """매 호출마다 새 엔진을 생성한다(NullPool).
    파이프라인은 asyncio.run()을 단계별로 호출하므로 루프가 매번 바뀜.
    NullPool을 쓰면 커넥션이 루프에 묶이지 않아 충돌이 없다.
    """
    url = _asyncpg_url(os.environ["DATABASE_URL"])
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory()


# ── FastAPI API 서버용 세션 팩토리 ─────────────────────────────────────────
# 파이프라인과 달리 FastAPI는 단일 이벤트 루프에서 동작하므로 커넥션 풀을 사용한다.

_api_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_api_session_factory() -> async_sessionmaker[AsyncSession]:
    """최초 호출 시 엔진을 생성한다(지연 초기화).
    모듈 임포트 시점이 아닌 첫 요청 시점에 DATABASE_URL을 읽어
    load_dotenv() 호출 순서와 무관하게 동작한다.
    """
    global _api_session_factory
    if _api_session_factory is None:
        url = _asyncpg_url(os.environ["DATABASE_URL"])
        engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,   # 사용 전 연결 상태 확인 → 닫힌 연결 자동 재연결
            pool_recycle=300,     # 5분마다 연결 재생성 (Neon 유휴 타임아웃 이전)
        )
        _api_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return _api_session_factory


async def get_db() -> AsyncSession:  # type: ignore[return]
    """FastAPI Depends용 DB 세션 의존성."""
    async with _get_api_session_factory()() as session:
        yield session
