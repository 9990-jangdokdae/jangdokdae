import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from apps.src.config.database import AsyncSessionLocal
from apps.src.issue_docent.article_selection import select_articles_for_deep_brief
from apps.src.issue_docent.llm.client import IssueDocentLLMClient
from apps.src.issue_docent.llm.prompt_loader import load_prompt
from apps.src.repositories.issue_docent import IssueDocentRepository
from apps.src.schemas.issue_docent_llm import ArticleBriefOutput


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


def prompt_hash(prompt_name: str) -> str:
    return hashlib.sha256(load_prompt(prompt_name).encode("utf-8")).hexdigest()


def article_brief_cache_path(
    *,
    cache_dir: Path,
    cluster_id: int,
    article_order: int,
) -> Path:
    return cache_dir / f"cluster_{cluster_id}_article_{article_order}_brief.json"


def load_cached_article_brief(
    *,
    cache_dir: Path | None,
    cluster_id: int,
    article_id: str,
    article_order: int,
    prompt_hash: str,
) -> ArticleBriefOutput | None:
    if cache_dir is None:
        return None
    path = article_brief_cache_path(
        cache_dir=cache_dir,
        cluster_id=cluster_id,
        article_order=article_order,
    )
    if not path.exists():
        return None
    cached = json.loads(path.read_text(encoding="utf-8"))
    if cached.get("prompt_hash") != prompt_hash:
        return None
    if cached.get("article_id") != article_id:
        return None
    return ArticleBriefOutput.model_validate(cached["brief"])


def write_cached_article_brief(
    *,
    cache_dir: Path | None,
    cluster_id: int,
    article_id: str,
    article_order: int,
    prompt_hash: str,
    brief: ArticleBriefOutput,
) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = article_brief_cache_path(
        cache_dir=cache_dir,
        cluster_id=cluster_id,
        article_order=article_order,
    )
    path.write_text(
        json.dumps(
            {
                "cluster_id": cluster_id,
                "article_id": article_id,
                "article_order": article_order,
                "prompt_hash": prompt_hash,
                "brief": brief.model_dump(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run Issue Docent quality review.")
    parser.add_argument("--cluster-id", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--structured-attempts", type=int, default=1)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    rows: list[dict[str, Any]] = []
    llm_client = IssueDocentLLMClient(structured_output_max_attempts=args.structured_attempts)
    article_prompt_hash = prompt_hash("article_brief.md")
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
                cached_brief = load_cached_article_brief(
                    cache_dir=args.cache_dir,
                    cluster_id=cluster_id,
                    article_id=article.article_id,
                    article_order=article.article_order,
                    prompt_hash=article_prompt_hash,
                )
                if cached_brief is not None:
                    print(
                        f"[quality] cluster {cluster_id}: article_brief order={article.article_order} cached",
                        file=sys.stderr,
                    )
                    article_briefs.append(cached_brief)
                    continue
                print(
                    f"[quality] cluster {cluster_id}: article_brief order={article.article_order}",
                    file=sys.stderr,
                )
                article_brief = await llm_client.generate_article_brief(article)
                write_cached_article_brief(
                    cache_dir=args.cache_dir,
                    cluster_id=cluster_id,
                    article_id=article.article_id,
                    article_order=article.article_order,
                    prompt_hash=article_prompt_hash,
                    brief=article_brief,
                )
                article_briefs.append(article_brief)

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
