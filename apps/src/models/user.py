from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import ARRAY, BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apps.src.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("provider", "provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(10))
    provider_id: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str] = mapped_column(String(100))
    interest_sectors: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    interest_companies: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
