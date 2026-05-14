from datetime import datetime
from sqlalchemy import BigInteger, Identity, String, Text, SmallInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from .base import Base


class CompanyMaster(Base):
    __tablename__ = "company_master"

    id:         Mapped[int]          = mapped_column(BigInteger, Identity(), primary_key=True)
    krx_code:   Mapped[str]          = mapped_column(String(6), unique=True, nullable=False)
    dart_code:  Mapped[str | None]   = mapped_column(String(8), unique=True)
    krx_name:   Mapped[str]          = mapped_column(String(100), nullable=False)
    dart_name:  Mapped[str | None]   = mapped_column(String(100))
    sector:     Mapped[str | None]   = mapped_column(String(50))
    market:     Mapped[str | None]   = mapped_column(String(10))
    updated_at: Mapped[datetime]     = mapped_column(DateTime, nullable=False, default=datetime.now)

    financial_statements: Mapped[list["DartFinancialStatement"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    dart_documents:       Mapped[list["DartDocument"]]           = relationship(back_populates="company", cascade="all, delete-orphan")


class DartFinancialStatement(Base):
    __tablename__ = "dart_financial_statements"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", "fs_div", "reprt_code"),)

    id:                  Mapped[int]          = mapped_column(BigInteger, Identity(), primary_key=True)
    company_id:          Mapped[int]          = mapped_column(BigInteger, ForeignKey("company_master.id", ondelete="CASCADE"), nullable=False)
    fiscal_year:         Mapped[int]          = mapped_column(SmallInteger, nullable=False)
    fs_div:              Mapped[str]          = mapped_column(String(5), nullable=False)
    rcept_no:            Mapped[str]          = mapped_column(String(20), nullable=False)
    reprt_code:          Mapped[str]          = mapped_column(String(10), nullable=False)
    revenue:             Mapped[int | None]   = mapped_column(BigInteger)
    operating_income:    Mapped[int | None]   = mapped_column(BigInteger)
    income_before_tax:   Mapped[int | None]   = mapped_column(BigInteger)
    net_income:          Mapped[int | None]   = mapped_column(BigInteger)
    current_assets:      Mapped[int | None]   = mapped_column(BigInteger)
    total_assets:        Mapped[int | None]   = mapped_column(BigInteger)
    current_liabilities: Mapped[int | None]   = mapped_column(BigInteger)
    total_liabilities:   Mapped[int | None]   = mapped_column(BigInteger)
    capital_stock:       Mapped[int | None]   = mapped_column(BigInteger)
    retained_earnings:   Mapped[int | None]   = mapped_column(BigInteger)
    total_equity:        Mapped[int | None]   = mapped_column(BigInteger)
    currency:            Mapped[str]          = mapped_column(String(5), nullable=False, default="KRW")
    updated_at:          Mapped[datetime]     = mapped_column(DateTime, nullable=False, default=datetime.now)

    company: Mapped["CompanyMaster"] = relationship(back_populates="financial_statements")


class DartDocument(Base):
    __tablename__ = "dart_document"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", "section", "subsection"),)

    id:            Mapped[int]               = mapped_column(BigInteger, Identity(), primary_key=True)
    company_id:    Mapped[int]               = mapped_column(BigInteger, ForeignKey("company_master.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[str]               = mapped_column(String(20), nullable=False)
    fiscal_year:   Mapped[int]               = mapped_column(SmallInteger, nullable=False)
    period_type:   Mapped[str]               = mapped_column(String(10), nullable=False)
    section:       Mapped[str]               = mapped_column(String, nullable=False)
    subsection:    Mapped[str]               = mapped_column(Text, nullable=False, server_default="")
    content:       Mapped[str]               = mapped_column(String, nullable=False)
    embedding:     Mapped[list[float] | None] = mapped_column(Vector(768))
    source:        Mapped[str]               = mapped_column(String(20), nullable=False, default="DART")
    source_url:    Mapped[str | None]        = mapped_column(String)
    created_at:    Mapped[datetime]          = mapped_column(DateTime, nullable=False, default=datetime.now)

    company: Mapped["CompanyMaster"] = relationship(back_populates="dart_documents")
