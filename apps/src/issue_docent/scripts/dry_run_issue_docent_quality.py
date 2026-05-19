import argparse
import asyncio
import hashlib
import json
import re
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

REVIEW_BLOCKED_PHRASES = (
    "보입니다",
    "보이며",
    "풀이됩니다",
    "분석됩니다",
)

ARTICLE_HYPE_PHRASES = (
    "역대급",
)

CAUSAL_SUPPORT_PHRASES = (
    "보조했습니다",
    "보조했다",
    "반전시켰습니다",
    "반전시켰다",
)

INVESTMENT_BENEFIT_PHRASES = (
    "혜택",
    "수혜",
    "가능성",
)

LOW_PRIORITY_TECHNICAL_CATALYSTS = (
    "SOCAMM2",
    "RDIMM",
    "토큰 제한",
)

ALLOWED_PLAN_SECTIONS = {
    "fact",
    "background",
    "performance_detail",
    "policy_detail",
}


def build_quality_review_row(
    *,
    cluster_id: int,
    title: str,
    teaser: str,
    summary: str,
    content_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "cluster_id": cluster_id,
        "title": title,
        "teaser": teaser,
        "summary": summary,
        "paragraph_count": len([part for part in summary.split("\n\n") if part.strip()]),
        "manual_gates": {gate: "UNREVIEWED" for gate in REQUIRED_MANUAL_GATES},
    }
    if content_plan is not None:
        row["content_plan"] = content_plan
    auto_gates, auto_review_notes = evaluate_quality_gates(row)
    row["auto_gates"] = auto_gates
    row["auto_review_notes"] = auto_review_notes
    return row


def evaluate_quality_gates(row: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    notes: list[str] = []
    content_plan = row.get("content_plan") or {}
    text = "\n".join([row["title"], row["teaser"], row["summary"]])
    paragraph_count = int(row["paragraph_count"])

    if any(char.isdigit() for char in row["title"]):
        notes.append("title must not include numbers")
    if len(re.findall(r"\d+(?:[.,]\d+)?", row["teaser"])) > 1:
        notes.append("teaser must include at most one number")
    if any(phrase in text for phrase in REVIEW_BLOCKED_PHRASES):
        notes.append("content must not use model judgment phrasing")
    if any(phrase in text for phrase in ARTICLE_HYPE_PHRASES):
        notes.append("content must not use article-hype wording")
    if any(phrase in text for phrase in CAUSAL_SUPPORT_PHRASES):
        notes.append("content must not use causal-support wording")
    if any(phrase in row["summary"] for phrase in INVESTMENT_BENEFIT_PHRASES):
        notes.append("summary must not include investment-benefit wording")
    if any(phrase in row["summary"] for phrase in LOW_PRIORITY_TECHNICAL_CATALYSTS):
        notes.append("summary must not include low-priority technical catalysts")
    if paragraph_count > 2:
        notes.append("summary must be at most two paragraphs")

    selected_article_orders = content_plan.get("selected_article_orders") or [0]
    if selected_article_orders != [0]:
        notes.append("selected_article_orders must stay on representative article only")
    sections = {
        paragraph.get("section")
        for paragraph in content_plan.get("paragraphs", [])
        if isinstance(paragraph, dict)
    }
    if not sections <= ALLOWED_PLAN_SECTIONS:
        notes.append("content_plan contains a disallowed section")

    gates = {
        "output_quality": "PASS",
        "prompt_quality": "PASS",
        "beginner_difficulty": "PASS",
        "central_article_reflection": "PASS",
        "concision": "PASS",
    }
    if any(
        note
        for note in notes
        if note.startswith("title")
        or note.startswith("content")
        or note.startswith("summary must not")
    ):
        gates["output_quality"] = "FAIL"
    if any(note.startswith("content_plan") for note in notes):
        gates["prompt_quality"] = "FAIL"
    if any(
        note
        for note in notes
        if note.startswith("content")
        or note.startswith("summary must not")
        or note.startswith("teaser")
    ):
        gates["beginner_difficulty"] = "FAIL"
    if any(note.startswith("selected_article_orders") for note in notes):
        gates["central_article_reflection"] = "FAIL"
    if any(note.startswith("summary must be") or note.startswith("teaser") for note in notes):
        gates["concision"] = "FAIL"
    return gates, notes


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
