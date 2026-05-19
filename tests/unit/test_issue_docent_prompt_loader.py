from apps.src.issue_docent.llm.prompt_loader import load_prompt


def test_load_prompt_reads_prompt_file():
    prompt = load_prompt("article_brief.md")

    assert "기사 하나를 읽고" in prompt
    assert "`core_event`" in prompt
    assert "`key_numbers`" in prompt
    assert "`low_priority_details`" in prompt


def test_load_prompt_reads_quiz_prompt_file():
    prompt = load_prompt("quiz.md")

    assert "객관식 퀴즈 출제자" in prompt


def test_cluster_summary_prompt_generates_summary_content_only():
    prompt = load_prompt("cluster_summary.md")

    assert "content_plan" in prompt
    assert "설계도에 없는 기사" in prompt
    assert "탈환, 흥행, 급증, 눈앞" in prompt
    assert "`title`: 중심 기사에서 다루는 회사나 상품과 핵심 변화를 바탕으로" in prompt
    assert "`teaser`: 목록 카드용 짧은 소개" in prompt
    assert "`summary`: 상세 본문" in prompt
    assert "새 원인 분석, 시장 해석, 전망, 파급 효과, 학습 포인트, 투자 판단은 쓰지 않는다" in prompt
    assert "summary_points" not in prompt
    assert "explanation" not in prompt


def test_content_plan_prompt_names_representative_article():
    prompt = load_prompt("content_plan.md")

    assert "`article_order=0`을 대표 기사" in prompt
    assert "omitted_article_orders" in prompt
    assert "같은 회사 기사라도 대표 기사와 다른 논점이면 제외한다" in prompt
    assert "순위 경쟁이나 시장 전체 흐름으로 넓히지 않는다" in prompt
