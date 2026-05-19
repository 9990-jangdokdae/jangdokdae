import pytest
from pydantic import ValidationError

from apps.src.schemas.issue_docent_llm import (
    ArticleBriefOutput,
    IssueDocentContentOutput,
    IssueDocentContentPlanOutput,
    IssueDocentPlanParagraph,
    QuizOutput,
)


def test_article_brief_output_keeps_structured_source_facts():
    output = ArticleBriefOutput.model_validate(
        {
            "article_pk": 1,
            "article_id": "a1",
            "article_order": 0,
            "brief": "한빛자산운용 ETF 순자산이 연초보다 늘었다.",
            "core_event": "한빛자산운용 ETF 순자산이 연초보다 늘었다.",
            "key_numbers": ["순자산 33조 3149억 원", "연초 대비 58.81% 증가"],
            "stated_background": ["반도체 ETF 상품 순자산이 함께 늘었다."],
            "stated_market_reactions": ["시장 점유율은 7.11%까지 올랐다."],
            "stated_interpretations": [],
            "low_priority_details": ["중심 사건과 직접 관련 없는 별도 금융상품 내용"],
        }
    )

    assert output.core_event == "한빛자산운용 ETF 순자산이 연초보다 늘었다."
    assert output.key_numbers == ["순자산 33조 3149억 원", "연초 대비 58.81% 증가"]
    assert output.stated_interpretations == []


def test_issue_docent_content_plan_output_accepts_paragraph_plan():
    output = IssueDocentContentPlanOutput.model_validate(
        {
            "central_article_order": 0,
            "central_issue": "한빛자산운용 ETF 순자산 증가",
            "selected_article_orders": [0, 1],
            "omitted_article_orders": [2],
            "paragraphs": [
                {
                    "section": "fact",
                    "source_article_orders": [0],
                    "facts": [
                        "한빛자산운용 ETF 순자산 총액은 33조 3149억 원이다.",
                        "연초보다 58.81% 늘었다.",
                    ],
                },
                {
                    "section": "market_reaction",
                    "source_article_orders": [0, 1],
                    "facts": [
                        "시장 점유율은 7.11%까지 올랐다.",
                        "삼성전자와 SK하이닉스 편입 ETF 거래대금 비중이 확인됐다.",
                    ],
                },
            ],
        }
    )

    assert output.central_article_order == 0
    assert output.selected_article_orders == [0, 1]
    assert [paragraph.section for paragraph in output.paragraphs] == ["fact", "market_reaction"]


def test_issue_docent_content_plan_accepts_performance_detail_section():
    output = IssueDocentContentPlanOutput.model_validate(
        {
            "central_article_order": 0,
            "central_issue": "펄어비스 1분기 영업이익 증가",
            "selected_article_orders": [0],
            "omitted_article_orders": [],
            "paragraphs": [
                {
                    "section": "performance_detail",
                    "source_article_orders": [0],
                    "facts": [
                        "전체 매출 중 해외 매출 비중은 94%다.",
                        "플랫폼별 매출은 콘솔과 PC가 각각 50%다.",
                    ],
                }
            ],
        }
    )

    assert output.paragraphs[0].section == "performance_detail"


def test_issue_docent_content_plan_accepts_policy_detail_section():
    output = IssueDocentContentPlanOutput.model_validate(
        {
            "central_article_order": 0,
            "central_issue": "한국거래소 상장폐지 기준 강화",
            "selected_article_orders": [0],
            "omitted_article_orders": [],
            "paragraphs": [
                {
                    "section": "policy_detail",
                    "source_article_orders": [0],
                    "facts": [
                        "관리종목 지정 후 90거래일 동안 주식병합으로 요건을 우회할 수 없다.",
                        "10대 1을 초과하는 주식병합은 상장폐지 실질심사 사유가 된다.",
                    ],
                }
            ],
        }
    )

    assert output.paragraphs[0].section == "policy_detail"


def test_issue_docent_content_plan_rejects_unknown_paragraph_section():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "한빛자산운용 ETF 순자산 증가",
                "selected_article_orders": [0],
                "paragraphs": [
                    {
                        "section": "outlook",
                        "source_article_orders": [0],
                        "facts": ["전망은 계획에 포함하지 않는다."],
                    }
                ],
            }
        )


def test_issue_docent_content_plan_rejects_paragraph_sources_outside_selected_articles():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "한국거래소 상장폐지 기준 강화",
                "selected_article_orders": [0, 1],
                "omitted_article_orders": [2],
                "paragraphs": [
                    {
                        "section": "background",
                        "source_article_orders": [0, 2],
                        "facts": ["2번 기사의 사실이 선택 목록 없이 들어갔다."],
                    }
                ],
            }
        )


def test_issue_docent_content_plan_rejects_selected_and_omitted_overlap():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "한국거래소 상장폐지 기준 강화",
                "selected_article_orders": [0, 1],
                "omitted_article_orders": [1, 2],
                "paragraphs": [
                    {
                        "section": "fact",
                        "source_article_orders": [0],
                        "facts": ["한국거래소가 상장폐지 기준을 강화한다."],
                    }
                ],
            }
        )


def test_issue_docent_content_plan_rejects_selected_article_without_available_brief_context():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "KB자산운용 ETF 순자산 증가",
                "selected_article_orders": [0, 1],
                "omitted_article_orders": [],
                "paragraphs": [
                    {
                        "section": "fact",
                        "source_article_orders": [0],
                        "facts": ["KB자산운용의 ETF 순자산이 늘었다."],
                    }
                ],
            },
            context={"available_article_orders": [0]},
        )


def test_issue_docent_content_plan_rejects_section_outside_allowed_context():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "KB자산운용 ETF 순자산 증가",
                "selected_article_orders": [0],
                "omitted_article_orders": [],
                "paragraphs": [
                    {
                        "section": "market_reaction",
                        "source_article_orders": [0],
                        "facts": ["외부 반응이 아닌 상품 구조 평가다."],
                    }
                ],
            },
            context={"allowed_plan_sections": ["fact", "background", "performance_detail"]},
        )


def test_issue_docent_content_plan_rejects_more_than_two_paragraphs():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "한국거래소 상장폐지 기준 강화",
                "selected_article_orders": [0],
                "omitted_article_orders": [],
                "paragraphs": [
                    {
                        "section": "fact",
                        "source_article_orders": [0],
                        "facts": ["한국거래소가 상장폐지 기준을 강화한다."],
                    },
                    {
                        "section": "policy_detail",
                        "source_article_orders": [0],
                        "facts": ["시가총액 기준이 높아진다."],
                    },
                    {
                        "section": "background",
                        "source_article_orders": [0],
                        "facts": ["부실기업 퇴출을 위한 조치다."],
                    },
                ],
            }
        )


def test_issue_docent_content_plan_limits_selected_articles_and_paragraph_facts():
    with pytest.raises(ValidationError):
        IssueDocentContentPlanOutput.model_validate(
            {
                "central_article_order": 0,
                "central_issue": "한빛자산운용 ETF 순자산 증가",
                "selected_article_orders": [0, 1, 2, 3],
                "paragraphs": [
                    {
                        "section": "fact",
                        "source_article_orders": [0],
                        "facts": ["a", "b", "c", "d"],
                    }
                ],
            }
        )


def test_issue_docent_content_output_accepts_title_teaser_and_summary_only():
    output = IssueDocentContentOutput.model_validate(
        {
            "title": "삼성전자, 반도체 투자 발표",
            "teaser": "삼성전자가 반도체 투자 계획을 밝혔다.",
            "summary": "삼성전자가 2026년 반도체 투자 계획을 발표했다.",
        }
    )

    assert output.title == "삼성전자, 반도체 투자 발표"
    assert "explanation" not in IssueDocentContentOutput.model_fields
    assert "summary_points" not in IssueDocentContentOutput.model_fields


def test_issue_docent_content_output_rejects_empty_summary():
    with pytest.raises(ValidationError):
        IssueDocentContentOutput.model_validate(
            {
                "title": "제목",
                "teaser": "티저",
                "summary": "",
            }
        )


def test_issue_docent_content_output_rejects_numeric_title():
    with pytest.raises(ValidationError):
        IssueDocentContentOutput.model_validate(
            {
                "title": "KB자산운용 ETF 순자산이 33조 원을 넘어섰습니다",
                "teaser": "KB자산운용의 ETF 순자산이 늘었습니다.",
                "summary": "KB자산운용의 ETF 순자산이 늘었습니다.",
            }
        )


def test_issue_docent_content_output_rejects_model_judgment_phrasing():
    with pytest.raises(ValidationError):
        IssueDocentContentOutput.model_validate(
            {
                "title": "GST 지분이 늘었습니다",
                "teaser": "피델리티가 GST 지분을 늘렸습니다.",
                "summary": "GST의 올해 실적은 역대 최대 규모를 기록할 것으로 보이며 추가 성장이 예상됩니다.",
            }
        )


def test_issue_docent_content_output_rejects_too_few_summary_paragraphs_from_context():
    with pytest.raises(ValidationError):
        IssueDocentContentOutput.model_validate(
            {
                "title": "GST 지분이 늘었습니다",
                "teaser": "피델리티가 GST 지분을 늘렸습니다.",
                "summary": "첫 문장입니다. 둘째 문장입니다.",
            },
            context={"min_summary_paragraphs": 2},
        )


def test_quiz_output_accepts_two_issue_quizzes_without_term_candidates():
    output = QuizOutput.model_validate_with_term_candidates(
        {
            "quizzes": [
                {
                    "kind": "issue",
                    "question": "첫 번째 질문",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "해설",
                },
                {
                    "kind": "issue",
                    "question": "두 번째 질문",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 1,
                    "explanation": "해설",
                },
            ]
        },
        has_term_candidates=False,
    )

    assert [quiz.kind for quiz in output.quizzes] == ["issue", "issue"]


def test_quiz_output_requires_term_quiz_when_term_candidates_exist():
    output = QuizOutput.model_validate_with_term_candidates(
        {
            "quizzes": [
                {
                    "kind": "term",
                    "question": "용어 질문",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 0,
                    "explanation": "해설",
                },
                {
                    "kind": "issue",
                    "question": "이슈 질문",
                    "options": ["A", "B", "C", "D"],
                    "answer_index": 1,
                    "explanation": "해설",
                },
            ]
        },
        has_term_candidates=True,
    )

    assert [quiz.kind for quiz in output.quizzes] == ["term", "issue"]


def test_quiz_output_rejects_wrong_quiz_count():
    with pytest.raises(ValidationError):
        QuizOutput.model_validate_with_term_candidates(
            {
                "quizzes": [
                    {
                        "kind": "issue",
                        "question": "질문",
                        "options": ["A", "B", "C", "D"],
                        "answer_index": 0,
                        "explanation": "해설",
                    }
                ]
            },
            has_term_candidates=False,
        )


def test_quiz_output_rejects_wrong_option_count():
    with pytest.raises(ValidationError):
        QuizOutput.model_validate_with_term_candidates(
            {
                "quizzes": [
                    {
                        "kind": "issue",
                        "question": "첫 번째 질문",
                        "options": ["A", "B", "C"],
                        "answer_index": 0,
                        "explanation": "해설",
                    },
                    {
                        "kind": "issue",
                        "question": "두 번째 질문",
                        "options": ["A", "B", "C", "D"],
                        "answer_index": 1,
                        "explanation": "해설",
                    },
                ]
            },
            has_term_candidates=False,
        )


def test_quiz_output_rejects_term_quiz_without_term_candidates():
    with pytest.raises(ValidationError):
        QuizOutput.model_validate_with_term_candidates(
            {
                "quizzes": [
                    {
                        "kind": "term",
                        "question": "용어 질문",
                        "options": ["A", "B", "C", "D"],
                        "answer_index": 0,
                        "explanation": "해설",
                    },
                    {
                        "kind": "issue",
                        "question": "이슈 질문",
                        "options": ["A", "B", "C", "D"],
                        "answer_index": 1,
                        "explanation": "해설",
                    },
                ]
            },
            has_term_candidates=False,
        )
