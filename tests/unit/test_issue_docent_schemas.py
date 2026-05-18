import pytest
from pydantic import ValidationError

from apps.src.schemas.issue_docent_llm import ArticleBriefOutput, IssueDocentContentOutput, QuizOutput


def test_article_brief_output_keeps_only_identity_order_and_brief():
    output = ArticleBriefOutput.model_validate(
        {
            "article_pk": 1,
            "article_id": "a1",
            "article_order": 0,
            "brief": "기사 핵심 내용",
        }
    )

    assert set(output.model_fields_set) == {"article_pk", "article_id", "article_order", "brief"}
    assert "key_facts" not in ArticleBriefOutput.model_fields
    assert "source_views" not in ArticleBriefOutput.model_fields


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
