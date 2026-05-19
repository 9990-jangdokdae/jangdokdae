from apps.src.issue_docent.llm.prompt_loader import load_prompt


def test_load_prompt_reads_prompt_file():
    prompt = load_prompt("article_brief.md")

    assert "기사 하나를 읽고" in prompt
    assert "`brief`: 기사 핵심 내용 요약" in prompt
    assert "`key_facts`" not in prompt
    assert "`source_views`" not in prompt


def test_load_prompt_reads_quiz_prompt_file():
    prompt = load_prompt("quiz.md")

    assert "객관식 퀴즈 출제자" in prompt


def test_cluster_summary_prompt_generates_summary_content_only():
    prompt = load_prompt("cluster_summary.md")

    assert "`title`: 중심 기사에서 다루는 회사나 상품과 핵심 변화를 바탕으로" in prompt
    assert "`teaser`: 목록 카드용 짧은 소개" in prompt
    assert "`summary`: 상세 본문" in prompt
    assert "새 원인 분석, 시장 해석, 전망, 파급 효과, 학습 포인트, 투자 판단은 쓰지 않는다" in prompt
    assert "summary_points" not in prompt
    assert "explanation" not in prompt
