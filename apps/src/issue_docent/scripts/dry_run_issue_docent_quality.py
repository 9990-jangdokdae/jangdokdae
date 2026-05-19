import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from apps.src.config.database import AsyncSessionLocal
from apps.src.issue_docent.article_selection import select_articles_for_deep_brief
from apps.src.issue_docent.llm.client import IssueDocentLLMClient
from apps.src.repositories.issue_docent import IssueDocentRepository


REQUIRED_MANUAL_GATES = [
    "output_quality",
    "prompt_quality",
    "beginner_difficulty",
    "central_article_reflection",
    "concision",
]


def build_quality_review_row(
    *,
    cluster_id: int,
    title: str,
    teaser: str,
    summary: str,
    content_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "cluster_id": cluster_id,
        "title": title,
        "teaser": teaser,
        "summary": summary,
        "paragraph_count": len([part for part in summary.split("\n\n") if part.strip()]),
        "manual_gates": {gate: "UNREVIEWED" for gate in REQUIRED_MANUAL_GATES},
    }
    if content_plan is not None:
        row["content_plan"] = content_plan
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run Issue Docent quality review.")
    parser.add_argument("--cluster-id", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--structured-attempts", type=int, default=1)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    llm_client = IssueDocentLLMClient(structured_output_max_attempts=args.structured_attempts)
    async with AsyncSessionLocal() as session:
        repository = IssueDocentRepository(session)
        for cluster_id in args.cluster_id:
            print(f"[quality] cluster {cluster_id}: load context", file=sys.stderr)
            cluster = await repository.get_cluster_context(cluster_id)
            if cluster is None:
                raise RuntimeError(f"cluster {cluster_id} was not found")
            await repository.session.rollback()

            article_briefs = []
            for article in select_articles_for_deep_brief(cluster.articles):
                print(
                    f"[quality] cluster {cluster_id}: article_brief order={article.article_order}",
                    file=sys.stderr,
                )
                article_briefs.append(await llm_client.generate_article_brief(article))

            print(f"[quality] cluster {cluster_id}: content_plan", file=sys.stderr)
            content_plan = await llm_client.generate_content_plan(
                cluster=cluster,
                article_briefs=article_briefs,
            )
            print(f"[quality] cluster {cluster_id}: summary", file=sys.stderr)
            content = await llm_client.generate_issue_docent_content(
                cluster=cluster,
                article_briefs=article_briefs,
                content_plan=content_plan,
            )
            rows.append(
                build_quality_review_row(
                    cluster_id=cluster_id,
                    title=content.title,
                    teaser=content.teaser,
                    summary=content.summary,
                    content_plan=content_plan.model_dump(),
                )
            )
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
