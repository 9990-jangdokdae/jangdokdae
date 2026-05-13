"""FastAPI 전용 DB 세션 팩토리.

파이프라인용 database.py는 NullPool(asyncio.run() 호환)을 사용하지만,
FastAPI는 앱 생명주기 동안 하나의 이벤트 루프가 유지되므로 커넥션 풀을 사용한다.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.src.config.database import _asyncpg_url


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    url = _asyncpg_url(os.environ["DATABASE_URL"])
    engine = create_async_engine(url, pool_size=5, max_overflow=10)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 앱 시작 시 한 번만 생성
SessionFactory = _make_session_factory()


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with SessionFactory() as session:
        yield session
