from apps.src.issue_docent.scripts.dry_run_issue_docent_quality import (
    build_quality_review_row,
    evaluate_quality_gates,
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
    assert row["auto_gates"] == {
        "output_quality": "PASS",
        "prompt_quality": "PASS",
        "beginner_difficulty": "PASS",
        "central_article_reflection": "PASS",
        "concision": "PASS",
    }


def test_evaluate_quality_gates_flags_known_quality_regressions():
    row = build_quality_review_row(
        cluster_id=2,
        title="코스피가 하락했습니다",
        teaser="코스피가 7999.67을 기록한 뒤 외국인의 5.6조 원 매도로 하락했습니다.",
        summary=(
            "외국인의 역대급 매도가 지수를 하락으로 반전시켰습니다.\n\n"
            "SOCAMM2와 RDIMM이 혜택을 받을 가능성도 함께 언급됐습니다.\n\n"
            "셋째 문단입니다."
        ),
        content_plan={
            "central_article_order": 0,
            "selected_article_orders": [0, 1],
            "paragraphs": [
                {"section": "fact", "source_article_orders": [0], "facts": ["사실"]},
                {"section": "market_reaction", "source_article_orders": [1], "facts": ["반응"]},
            ],
        },
    )

    gates, notes = evaluate_quality_gates(row)

    assert gates == {
        "output_quality": "FAIL",
        "prompt_quality": "FAIL",
        "beginner_difficulty": "FAIL",
        "central_article_reflection": "FAIL",
        "concision": "FAIL",
    }
    assert "teaser must include at most one number" in notes
    assert "content must not use article-hype wording" in notes
    assert "content must not use causal-support wording" in notes
    assert "summary must not include investment-benefit wording" in notes
    assert "summary must not include low-priority technical catalysts" in notes
    assert "selected_article_orders must stay on representative article only" in notes


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
