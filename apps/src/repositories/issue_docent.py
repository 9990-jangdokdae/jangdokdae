from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.models.article import Article
from apps.src.models.cluster import Cluster, ClusterArticle, EntityExtraction
from apps.src.models.company import CompanyMaster
from apps.src.models.issue_docent import IssueDocent
from apps.src.models.stock_term import StockTerm
from apps.src.services.issue_docent.sector_companies import CompanyMasterCandidate
from apps.src.services.issue_docent.term_matcher import StockTermForMatch


@dataclass(frozen=True)
class SourceArticleRecord:
    article_id: str
    title: str
    press: str | None
    published_date: datetime
    url: str


@dataclass(frozen=True)
class IssueDocentListRecord:
    id: int
    cluster_id: int
    title: str
    teaser: str
    extracted_company_names: list[str]
    article_count: int
    created_at: datetime


@dataclass(frozen=True)
class IssueDocentDetailRecord(IssueDocentListRecord):
    explanation: list[dict[str, Any]]
    quizzes: list[dict[str, Any]]


@dataclass(frozen=True)
class ArticleForGeneration:
    article_pk: int
    article_id: str
    article_order: int
    title: str
    url: str
    press: str | None
    published_date: datetime
    content: str
    similarity_to_centroid: float | None


@dataclass(frozen=True)
class ClusterGenerationContext:
    cluster_id: int
    run_date: date
    cluster_seq: int
    size: int
    is_singleton: bool
    created_at: datetime
    company_names: list[str]
    sectors: list[str]
    keywords: list[str]
    articles: list[ArticleForGeneration]


class IssueDocentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch_target_cluster_ids(self, limit: int, force: bool = False) -> list[int]:
        stmt = select(Cluster.id).order_by(Cluster.created_at.asc()).limit(limit)
        if not force:
            stmt = stmt.outerjoin(IssueDocent, IssueDocent.cluster_id == Cluster.id).where(
                IssueDocent.id.is_(None)
            )
        return list((await self.session.scalars(stmt)).all())

    async def get_cluster_context(self, cluster_id: int) -> ClusterGenerationContext | None:
        cluster_stmt = (
            select(Cluster, EntityExtraction)
            .outerjoin(EntityExtraction, EntityExtraction.cluster_id == Cluster.id)
            .where(Cluster.id == cluster_id)
        )
        cluster_row = (await self.session.execute(cluster_stmt)).one_or_none()
        if cluster_row is None:
            return None

        cluster, entity = cluster_row
        article_stmt = (
            select(Article, ClusterArticle.similarity_to_centroid)
            .join(ClusterArticle, ClusterArticle.article_id == Article.id)
            .where(ClusterArticle.cluster_id == cluster_id)
            .order_by(
                ClusterArticle.similarity_to_centroid.desc().nulls_last(),
                Article.published_date.desc(),
            )
        )
        article_rows = (await self.session.execute(article_stmt)).all()
        articles = [
            ArticleForGeneration(
                article_pk=article.id,
                article_id=article.article_id,
                article_order=index,
                title=article.title,
                url=article.url,
                press=article.press,
                published_date=article.published_date,
                content=article.content,
                similarity_to_centroid=similarity_to_centroid,
            )
            for index, (article, similarity_to_centroid) in enumerate(article_rows)
        ]

        return ClusterGenerationContext(
            cluster_id=cluster.id,
            run_date=cluster.run_date,
            cluster_seq=cluster.cluster_seq,
            size=cluster.size,
            is_singleton=cluster.is_singleton,
            created_at=cluster.created_at,
            company_names=list(entity.company_names) if entity else [],
            sectors=list(entity.sectors) if entity else [],
            keywords=list(entity.keywords) if entity else [],
            articles=articles,
        )

    async def persist_issue_docent(
        self,
        *,
        cluster_id: int,
        title: str,
        teaser: str,
        summary: str,
        explanation: list[dict[str, Any]],
        quizzes: list[dict[str, Any]],
        force: bool = False,
    ) -> int | None:
        stmt = (
            insert(IssueDocent)
            .values(
                cluster_id=cluster_id,
                title=title,
                teaser=teaser,
                summary=summary,
                explanation=explanation,
                quizzes=quizzes,
            )
            .returning(IssueDocent.id)
        )
        if force:
            stmt = stmt.on_conflict_do_update(
                index_elements=[IssueDocent.cluster_id],
                set_={
                    "title": title,
                    "teaser": teaser,
                    "summary": summary,
                    "explanation": explanation,
                    "quizzes": quizzes,
                },
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[IssueDocent.cluster_id])

        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_issue_docents(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[IssueDocentListRecord], int]:
        total = await self.session.scalar(select(func.count()).select_from(IssueDocent))
        stmt = (
            _issue_docent_base_select()
            .order_by(IssueDocent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        return [_list_record_from_row(row) for row in rows], int(total or 0)

    async def get_issue_docent(self, issue_docent_id: int) -> IssueDocentDetailRecord | None:
        stmt = _issue_docent_base_select(IssueDocent.explanation, IssueDocent.quizzes).where(
            IssueDocent.id == issue_docent_id
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return _detail_record_from_row(row)

    async def get_source_articles(self, cluster_id: int) -> list[SourceArticleRecord]:
        stmt = (
            select(
                Article.article_id,
                Article.title,
                Article.press,
                Article.published_date,
                Article.url,
            )
            .join(ClusterArticle, ClusterArticle.article_id == Article.id)
            .where(ClusterArticle.cluster_id == cluster_id)
            .order_by(
                ClusterArticle.similarity_to_centroid.desc().nulls_last(),
                Article.published_date.desc(),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return [SourceArticleRecord(*row) for row in rows]

    async def get_stock_terms(self) -> list[StockTermForMatch]:
        stmt = select(
            StockTerm.id,
            StockTerm.term,
            StockTerm.aliases,
            StockTerm.category,
            StockTerm.definition,
        ).order_by(StockTerm.id.asc())
        rows = (await self.session.execute(stmt)).all()
        return [
            StockTermForMatch(
                id=row.id,
                term=row.term,
                aliases=list(row.aliases or []),
                category=row.category,
                definition=row.definition,
            )
            for row in rows
        ]

    async def get_company_master_candidates(
        self,
        company_names: list[str],
    ) -> list[CompanyMasterCandidate]:
        if not company_names:
            return []

        stmt = select(
            CompanyMaster.id,
            CompanyMaster.krx_name,
            CompanyMaster.dart_name,
            CompanyMaster.sector,
            CompanyMaster.market,
        ).where(
            or_(
                CompanyMaster.krx_name.in_(company_names),
                CompanyMaster.dart_name.in_(company_names),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            CompanyMasterCandidate(
                id=row.id,
                krx_name=row.krx_name,
                dart_name=row.dart_name,
                sector=row.sector,
                market=row.market,
            )
            for row in rows
        ]


def _issue_docent_base_select(*extra_columns: Any) -> Select[tuple[Any, ...]]:
    return (
        select(
            IssueDocent.id,
            IssueDocent.cluster_id,
            IssueDocent.title,
            IssueDocent.teaser,
            EntityExtraction.company_names.label("extracted_company_names"),
            func.count(ClusterArticle.article_id).label("article_count"),
            IssueDocent.created_at,
            *extra_columns,
        )
        .select_from(IssueDocent)
        .outerjoin(EntityExtraction, EntityExtraction.cluster_id == IssueDocent.cluster_id)
        .outerjoin(ClusterArticle, ClusterArticle.cluster_id == IssueDocent.cluster_id)
        .group_by(
            IssueDocent.id,
            IssueDocent.cluster_id,
            IssueDocent.title,
            IssueDocent.teaser,
            IssueDocent.created_at,
            EntityExtraction.company_names,
            *extra_columns,
        )
    )


def _list_record_from_row(row: Any) -> IssueDocentListRecord:
    return IssueDocentListRecord(
        id=row.id,
        cluster_id=row.cluster_id,
        title=row.title,
        teaser=row.teaser,
        extracted_company_names=list(row.extracted_company_names or []),
        article_count=row.article_count,
        created_at=row.created_at,
    )


def _detail_record_from_row(row: Any) -> IssueDocentDetailRecord:
    return IssueDocentDetailRecord(
        id=row.id,
        cluster_id=row.cluster_id,
        title=row.title,
        teaser=row.teaser,
        extracted_company_names=list(row.extracted_company_names or []),
        article_count=row.article_count,
        created_at=row.created_at,
        explanation=list(row.explanation or []),
        quizzes=list(row.quizzes or []),
    )
