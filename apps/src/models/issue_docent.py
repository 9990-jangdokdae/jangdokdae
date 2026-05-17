from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.src.models.base import Base


class IssueDocent(Base):
    __tablename__ = "issue_docent"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    cluster_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clusters.id"),
        nullable=False,
        unique=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    teaser: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    quizzes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("now()"),
    )
