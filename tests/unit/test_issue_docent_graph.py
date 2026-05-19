import asyncio
from datetime import date, datetime

import pytest

from apps.src.issue_docent.graphs.graph import build_issue_docent_graph
from apps.src.repositories.issue_docent import ArticleForGeneration, ClusterGenerationContext
from apps.src.schemas.issue_docent_llm import (
    ArticleBriefOutput,
    IssueDocentContentPlanOutput,
    IssueDocentContentOutput,
    IssueDocentPlanParagraph,
    QuizOutput,
)
from apps.src.services.issue_docent.term_matcher import StockTermForMatch


class FakeLLMClient:
    def __init__(self) -> None:
        self.content_input_orders: list[int] = []
        self.quiz_summary: str | None = None
        self.quiz_term_candidates: list[dict] = []
        self.active_article_brief_calls = 0
        self.max_article_brief_concurrency = 0

    async def generate_article_brief(self, article: ArticleForGeneration) -> ArticleBriefOutput:
        self.active_article_brief_calls += 1
        self.max_article_brief_concurrency = max(
            self.max_article_brief_concurrency,
            self.active_article_brief_calls,
        )
        await asyncio.sleep(0)
        self.active_article_brief_calls -= 1
        return ArticleBriefOutput(
            article_pk=article.article_pk,
            article_id=article.article_id,
            article_order=article.article_order,
            brief=f"{article.title} 요약",
            core_event=f"{article.title} 중심 사건",
            key_numbers=[],
            stated_background=[],
            stated_market_reactions=[],
            stated_interpretations=[],
            low_priority_details=[],
        )

    async def generate_content_plan(
        self,
        *,
        cluster: ClusterGenerationContext,
        article_briefs: list[ArticleBriefOutput],
    ) -> IssueDocentContentPlanOutput:
        self.content_input_orders = [brief.article_order for brief in article_briefs]
        return IssueDocentContentPlanOutput(
            central_article_order=0,
            central_issue="첫 기사 중심 이슈",
            selected_article_orders=[0, 1],
            omitted_article_orders=[],
            paragraphs=[
                IssueDocentPlanParagraph(
                    section="fact",
                    source_article_orders=[0],
                    facts=["첫 기사 중심 사실"],
                )
            ],
        )

    async def generate_issue_docent_content(
        self,
        *,
        cluster: ClusterGenerationContext,
        article_briefs: list[ArticleBriefOutput],
        content_plan: IssueDocentContentPlanOutput,
    ) -> IssueDocentContentOutput:
        self.content_plan_issue = content_plan.central_issue
        return IssueDocentContentOutput(
            title="클러스터 제목",
            teaser="간결한 티저 문장이다. 정보가 명확하다.",
            summary="핵심 사건이 있었다.",
        )

    async def generate_quizzes(
        self,
        *,
        summary: str,
        term_candidates: list[dict],
    ) -> QuizOutput:
        self.quiz_summary = summary
        self.quiz_term_candidates = term_candidates
        if term_candidates:
            return QuizOutput.model_validate_with_term_candidates(
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
        return QuizOutput.model_validate_with_term_candidates(
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
            has_term_candidates=bool(term_candidates),
        )


@pytest.mark.asyncio
async def test_issue_docent_graph_uses_representative_article_brief_and_builds_payload():
    fake_llm = FakeLLMClient()
    graph = build_issue_docent_graph(fake_llm)
    result = await graph.ainvoke({"cluster": _cluster_context()})

    assert fake_llm.content_input_orders == [0]
    assert fake_llm.max_article_brief_concurrency == 1
    assert fake_llm.content_plan_issue == "첫 기사 중심 이슈"
    assert fake_llm.quiz_summary == "핵심 사건이 있었다."
    assert result["persist_payload"].cluster_id == 10
    assert result["persist_payload"].title == "클러스터 제목"
    assert result["persist_payload"].summary == "핵심 사건이 있었다."
    assert not hasattr(result["persist_payload"], "explanation")
    assert [quiz["quiz_id"] for quiz in result["persist_payload"].quizzes] == [
        "quiz-1",
        "quiz-2",
    ]
    assert [quiz["kind"] for quiz in result["persist_payload"].quizzes] == ["issue", "issue"]


@pytest.mark.asyncio
async def test_issue_docent_graph_uses_summary_terms_as_quiz_candidates():
    fake_llm = FakeLLMClient()
    graph = build_issue_docent_graph(fake_llm)
    result = await graph.ainvoke(
        {
            "cluster": _cluster_context(),
            "stock_terms": [
                StockTermForMatch(
                    id=1,
                    term="핵심",
                    aliases=[],
                    category="테스트",
                    definition="중요한 부분",
                )
            ],
        }
    )

    assert fake_llm.quiz_term_candidates == [
        {
            "term_id": 1,
            "term": "핵심",
            "category": "테스트",
            "definition": "중요한 부분",
        }
    ]
    assert [quiz["kind"] for quiz in result["persist_payload"].quizzes] == ["term", "issue"]


@pytest.mark.asyncio
async def test_issue_docent_graph_limits_article_briefs_to_representative_article():
    fake_llm = FakeLLMClient()
    graph = build_issue_docent_graph(fake_llm)

    await graph.ainvoke({"cluster": _cluster_context(article_count=6)})

    assert fake_llm.content_input_orders == [0]


def _cluster_context(article_count: int = 2) -> ClusterGenerationContext:
    articles = [
        ArticleForGeneration(
            article_pk=index + 1,
            article_id=f"a{index + 1}",
            article_order=index,
            title="첫 기사" if index == 0 else f"{index + 1}번째 기사",
            url=f"https://example.com/{index + 1}",
            press="신문",
            published_date=datetime(2026, 5, 14, 8, index),
            content="기사 본문",
            similarity_to_centroid=0.9 - (index * 0.05),
        )
        for index in range(article_count)
    ]
    return ClusterGenerationContext(
        cluster_id=10,
        run_date=date(2026, 5, 14),
        cluster_seq=1,
        size=2,
        is_singleton=False,
        created_at=datetime(2026, 5, 14, 9, 0, 0),
        company_names=["삼성전자"],
        sectors=["반도체"],
        keywords=["투자"],
        articles=articles,
    )
