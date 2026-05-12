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
