from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import ARRAY, BigInteger, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from apps.src.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(10))
    provider_id: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str] = mapped_column(String(100))

    # server_default로 PostgreSQL NOT NULL 제약을 충족한다.
    # Python-side default는 ORM INSERT 시 사용되고,
    # server_default는 DB 수준에서 기본값을 제공해 컬럼 누락 INSERT를 방지한다.
    interest_sectors: Mapped[List[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )
    interest_companies: Mapped[List[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("ARRAY[]::text[]"),
    )
    
    created_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
