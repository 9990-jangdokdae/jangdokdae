from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.models.analyzer_dto import AnalysisResponse, AnalysisSummary, SidebarContext, StructuredContext
from apps.src.models.article_analysis import ArticleAnalysis


class ArticleAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_analysis_result(self, cluster_id: str | int) -> AnalysisResponse | None:
        normalized_cluster_id = _coerce_cluster_id(cluster_id)
        if normalized_cluster_id is None:
            return None
        stmt = select(ArticleAnalysis).where(ArticleAnalysis.cluster_id == normalized_cluster_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        return AnalysisResponse(
            cluster_id=str(row.cluster_id),
            analysis_summary=AnalysisSummary.model_validate(row.analysis_summary or {}),
            market_context=StructuredContext.model_validate(row.market_context or {}),
            sidebar_context=SidebarContext.model_validate(row.sidebar_context or {}),
        )

    async def upsert_analysis_result(
        self,
        *,
        cluster_id: str | int,
        result: AnalysisResponse,
    ) -> int | None:
        normalized_cluster_id = _coerce_cluster_id(result.cluster_id or cluster_id)
        if normalized_cluster_id is None:
            raise ValueError("cluster_id must be numeric to persist analyzer result")

        analysis_summary = result.analysis_summary.model_dump(mode="json")
        market_context = result.market_context.model_dump(mode="json")
        sidebar_context = result.sidebar_context.model_dump(mode="json")

        stmt = (
            insert(ArticleAnalysis)
            .values(
                cluster_id=normalized_cluster_id,
                analysis_summary=analysis_summary,
                market_context=market_context,
                sidebar_context=sidebar_context,
            )
            .on_conflict_do_update(
                index_elements=[ArticleAnalysis.cluster_id],
                set_={
                    "analysis_summary": analysis_summary,
                    "market_context": market_context,
                    "sidebar_context": sidebar_context,
                    "updated_at": func.now(),
                },
            )
            .returning(ArticleAnalysis.id)
        )

        return (await self.session.execute(stmt)).scalar_one_or_none()


def _coerce_cluster_id(value: str | int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
