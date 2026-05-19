from apps.src.issue_docent.scripts.dry_run_issue_docent_quality import (
    build_quality_review_row,
    load_cached_article_brief,
    write_cached_article_brief,
)
from apps.src.schemas.issue_docent_llm import ArticleBriefOutput


def test_build_quality_review_row_includes_required_manual_gates():
    row = build_quality_review_row(
        cluster_id=1,
        title="KB자산운용 ETF 순자산이 커졌습니다",
        teaser="KB자산운용의 ETF 순자산이 연초보다 늘었습니다.",
        summary="첫 문단입니다.\n\n둘째 문단입니다.",
    )

    assert row["cluster_id"] == 1
    assert row["manual_gates"] == {
        "output_quality": "UNREVIEWED",
        "prompt_quality": "UNREVIEWED",
        "beginner_difficulty": "UNREVIEWED",
        "central_article_reflection": "UNREVIEWED",
        "concision": "UNREVIEWED",
    }
    assert row["paragraph_count"] == 2


def test_article_brief_cache_returns_matching_prompt_hash(tmp_path):
    brief = ArticleBriefOutput(
        article_pk=1,
        article_id="article-1",
        article_order=0,
        brief="기사 요약",
        core_event="중심 사건",
        key_numbers=["10억 원"],
        stated_background=[],
        stated_market_reactions=[],
        stated_interpretations=[],
        low_priority_details=[],
    )

    write_cached_article_brief(
        cache_dir=tmp_path,
        cluster_id=7,
        article_id="article-1",
        article_order=0,
        prompt_hash="prompt-a",
        brief=brief,
    )

    cached = load_cached_article_brief(
        cache_dir=tmp_path,
        cluster_id=7,
        article_id="article-1",
        article_order=0,
        prompt_hash="prompt-a",
    )

    assert cached == brief


def test_article_brief_cache_ignores_stale_prompt_hash(tmp_path):
    brief = ArticleBriefOutput(
        article_pk=1,
        article_id="article-1",
        article_order=0,
        brief="기사 요약",
        core_event="중심 사건",
        key_numbers=[],
        stated_background=[],
        stated_market_reactions=[],
        stated_interpretations=[],
        low_priority_details=[],
    )

    write_cached_article_brief(
        cache_dir=tmp_path,
        cluster_id=7,
        article_id="article-1",
        article_order=0,
        prompt_hash="prompt-a",
        brief=brief,
    )

    assert (
        load_cached_article_brief(
            cache_dir=tmp_path,
            cluster_id=7,
            article_id="article-1",
            article_order=0,
            prompt_hash="prompt-b",
        )
        is None
    )
