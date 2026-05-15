import pytest
from pydantic import ValidationError

from apps.src.schemas.issue_docent_llm import IssueDocentOutput, QuizOutput


def test_issue_docent_output_accepts_required_sections():
    output = IssueDocentOutput.model_validate(
        {
            "explanation": [
                {
                    "section_type": "what_happened",
                    "title": "무슨 일이 있었나",
                    "paragraphs": ["첫 번째 문단"],
                },
                {
                    "section_type": "why_it_matters",
                    "title": "왜 중요한가",
                    "paragraphs": ["두 번째 문단"],
                },
                {
                    "section_type": "wrap_up",
                    "title": "마무리",
                    "paragraphs": ["세 번째 문단"],
                },
            ]
        }
    )

    assert len(output.explanation) == 3


def test_issue_docent_output_rejects_missing_required_section():
    with pytest.raises(ValidationError):
        IssueDocentOutput.model_validate(
            {
                "explanation": [
                    {
                        "section_type": "what_happened",
                        "title": "무슨 일이 있었나",
                        "paragraphs": ["첫 번째 문단"],
                    },
                    {
                        "section_type": "expert_view",
                        "title": "전문가 관점",
                        "paragraphs": ["두 번째 문단"],
                    },
                    {
                        "section_type": "wrap_up",
                        "title": "마무리",
                        "paragraphs": ["세 번째 문단"],
                    },
                ]
            }
        )


def test_issue_docent_output_rejects_more_than_two_paragraphs_per_section():
    with pytest.raises(ValidationError):
        IssueDocentOutput.model_validate(
            {
                "explanation": [
                    {
                        "section_type": "what_happened",
                        "title": "무슨 일이 있었나",
                        "paragraphs": ["1", "2", "3"],
                    },
                    {
                        "section_type": "why_it_matters",
                        "title": "왜 중요한가",
                        "paragraphs": ["두 번째 문단"],
                    },
                    {
                        "section_type": "wrap_up",
                        "title": "마무리",
                        "paragraphs": ["세 번째 문단"],
                    },
                ]
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
