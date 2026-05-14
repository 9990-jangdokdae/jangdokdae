from datetime import date, datetime
from sqlalchemy import BigInteger, Identity, Date, Integer, Boolean, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Cluster(Base):
    __tablename__ = "clusters"
    __table_args__ = (UniqueConstraint("run_date", "cluster_seq"),)

    id:           Mapped[int]      = mapped_column(BigInteger, Identity(), primary_key=True)
    run_date:     Mapped[date]     = mapped_column(Date, nullable=False)
    cluster_seq:  Mapped[int]      = mapped_column(Integer, nullable=False)
    size:         Mapped[int]      = mapped_column(Integer, nullable=False)
    is_singleton: Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False)
    created_at:   Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    cluster_articles:  Mapped[list["ClusterArticle"]]    = relationship(back_populates="cluster", cascade="all, delete-orphan")
    entity_extraction: Mapped["EntityExtraction | None"] = relationship(back_populates="cluster", cascade="all, delete-orphan")


class ClusterArticle(Base):
    __tablename__ = "cluster_articles"

    cluster_id:             Mapped[int]          = mapped_column(BigInteger, ForeignKey("clusters.id", ondelete="CASCADE"), primary_key=True)
    article_id:             Mapped[int]          = mapped_column(BigInteger, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    similarity_to_centroid: Mapped[float | None] = mapped_column(Float)

    cluster: Mapped["Cluster"] = relationship(back_populates="cluster_articles")
    article: Mapped["Article"] = relationship(back_populates="cluster_articles")


class EntityExtraction(Base):
    __tablename__ = "entity_extraction"

    id:            Mapped[int]       = mapped_column(BigInteger, Identity(), primary_key=True)
    cluster_id:    Mapped[int]       = mapped_column(BigInteger, ForeignKey("clusters.id", ondelete="CASCADE"), unique=True, nullable=False)
    company_names: Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)
    sectors:       Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)
    keywords:      Mapped[list[str]] = mapped_column(ARRAY(TEXT), nullable=False, default=list)

    cluster: Mapped["Cluster"] = relationship(back_populates="entity_extraction")
