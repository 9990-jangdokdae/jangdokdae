from dataclasses import dataclass

from apps.src.repositories.issue_docent import IssueDocentRepository
from apps.src.issue_docent.graphs.graph import build_issue_docent_graph
from apps.src.issue_docent.graphs.state import IssueDocentPersistPayload
from apps.src.issue_docent.llm.client import IssueDocentLLMClient


@dataclass(frozen=True)
class GenerationResult:
    cluster_id: int
    issue_docent_id: int | None
    status: str
    title: str | None = None


class IssueDocentGenerationService:
    def __init__(
        self,
        repository: IssueDocentRepository,
        llm_client: IssueDocentLLMClient | None = None,
    ) -> None:
        self.repository = repository
        self.graph = build_issue_docent_graph(llm_client)

    async def generate_for_cluster(
        self,
        cluster_id: int,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> GenerationResult:
        context = await self.repository.get_cluster_context(cluster_id)
        if context is None:
            raise ValueError(f"cluster {cluster_id} was not found")

        stock_terms = await self.repository.get_stock_terms()
        result = await self.graph.ainvoke({"cluster": context, "stock_terms": stock_terms})
        payload: IssueDocentPersistPayload = result["persist_payload"]
        if dry_run:
            return GenerationResult(
                cluster_id=cluster_id,
                issue_docent_id=None,
                status="dry_run",
                title=payload.title,
            )

        issue_docent_id = await self.repository.persist_issue_docent(
            cluster_id=payload.cluster_id,
            title=payload.title,
            teaser=payload.teaser,
            summary=payload.summary,
            quizzes=payload.quizzes,
            force=force,
        )
        await self.repository.session.commit()

        return GenerationResult(
            cluster_id=cluster_id,
            issue_docent_id=issue_docent_id,
            status="persisted" if issue_docent_id is not None else "skipped_existing",
            title=payload.title,
        )

    async def generate_batch(
        self,
        *,
        limit: int,
        force: bool = False,
        dry_run: bool = False,
    ) -> list[GenerationResult]:
        cluster_ids = await self.repository.fetch_target_cluster_ids(limit=limit, force=force)
        results: list[GenerationResult] = []
        for cluster_id in cluster_ids:
            results.append(
                await self.generate_for_cluster(
                    cluster_id,
                    force=force,
                    dry_run=dry_run,
                )
            )
        return results
