from datetime import datetime
from sqlalchemy import BigInteger, Identity, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Article(Base):
    __tablename__ = "articles"

    id:             Mapped[int]          = mapped_column(BigInteger, Identity(), primary_key=True)
    article_id:     Mapped[str]          = mapped_column(String(20), nullable=False, unique=True)
    office_id:      Mapped[str | None]   = mapped_column(String(10))
    title:          Mapped[str]          = mapped_column(Text, nullable=False)
    url:            Mapped[str]          = mapped_column(Text, nullable=False)
    press:          Mapped[str | None]   = mapped_column(String(100))
    published_date: Mapped[datetime]     = mapped_column(DateTime, nullable=False)
    content:        Mapped[str]          = mapped_column(Text, nullable=False)

    cluster_articles: Mapped[list["ClusterArticle"]] = relationship(back_populates="article", cascade="all, delete-orphan")
