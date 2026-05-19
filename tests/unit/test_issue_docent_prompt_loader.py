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
    assert "title과 teaser에서도 기사식 표현을 되살리지 않는다" in prompt
    assert "힘입어, 덕분에, 견인했다" in prompt
    assert "서로 다른 문단의 facts가 같은 사실을 말하면 한 번만 쓴다" in prompt
    assert "모호한 상품 표현보다 구체 상품명을 우선한다" in prompt
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
    assert "`central_issue`에는 탈환, 흥행, 급증, 대박" in prompt
    assert "market_reaction은 외부 투자자, 거래, 자금, 업계 조치처럼 기사에 명시된 외부 반응" in prompt
    assert "외부 반응이 없으면 `market_reaction` 문단을 만들지 않는다" in prompt
    assert "회사 계획이나 상품 구조 평가는 `market_reaction`에 넣지 않는다" in prompt
    assert "한 자산운용사의 ETF 순자산 이슈를 시장 전체 반도체 ETF 편입 비중으로 넓히지 않는다" in prompt
    assert "대표 기사만으로 중심 이슈가 충분하면 `selected_article_orders`는 대표 기사 하나만 둔다" in prompt
