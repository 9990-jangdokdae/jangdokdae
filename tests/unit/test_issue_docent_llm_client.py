from datetime import datetime

import pytest

from apps.src.issue_docent.llm import client as client_module
from apps.src.issue_docent.llm.client import IssueDocentLLMClient, create_main_llm
from apps.src.repositories.issue_docent import ArticleForGeneration, ClusterGenerationContext
from apps.src.schemas.issue_docent_llm import ArticleBriefOutput, IssueDocentContentPlanOutput


class FakeChatGoogleGenerativeAI:
    kwargs: dict | None = None

    def __init__(self, **kwargs) -> None:
        type(self).kwargs = kwargs


class FlakyStructuredLLM:
    def __init__(self) -> None:
        self.calls = 0

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("empty structured output")
        return {
            "article_pk": 1,
            "article_id": "article-1",
            "article_order": 0,
            "brief": "기사 핵심 내용",
            "core_event": "기사 중심 사건",
            "key_numbers": [],
            "stated_background": [],
            "stated_market_reactions": [],
            "stated_interpretations": [],
            "low_priority_details": [],
        }


class RetryFeedbackStructuredLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.message_history = []

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        self.message_history.append(messages)
        if self.calls == 1:
            raise ValueError("paragraph source_article_orders must be selected articles")
        return {
            "article_pk": 1,
            "article_id": "article-1",
            "article_order": 0,
            "brief": "기사 핵심 내용",
            "core_event": "기사 중심 사건",
            "key_numbers": [],
            "stated_background": [],
            "stated_market_reactions": [],
            "stated_interpretations": [],
            "low_priority_details": [],
        }


class CapturingStructuredLLM:
    def __init__(self, response: dict | None = None) -> None:
        self.schema = None
        self.messages = []
        self.response = response

    def with_structured_output(self, schema):
        self.schema = schema
        return self

    async def ainvoke(self, messages):
        self.messages = messages
        if self.response is not None:
            return self.response
        return {
            "central_article_order": 0,
            "central_issue": "첫 기사 중심 이슈",
            "selected_article_orders": [0],
            "omitted_article_orders": [1],
            "paragraphs": [
                {
                    "section": "fact",
                    "source_article_orders": [0],
                    "facts": ["첫 기사 중심 사실"],
                }
            ],
        }


@pytest.mark.asyncio
async def test_structured_invoke_retries_empty_output_failure():
    llm = FlakyStructuredLLM()
    client = IssueDocentLLMClient(llm=llm, structured_output_max_attempts=2)

    result = await client.generate_article_brief(
        ArticleForGeneration(
            article_pk=1,
            article_id="article-1",
            article_order=0,
            title="테스트 기사",
            url="https://example.com",
            press="신문",
            published_date=datetime(2026, 5, 19),
            content="본문",
            similarity_to_centroid=1.0,
        )
    )

    assert llm.calls == 2
    assert result.brief == "기사 핵심 내용"
    assert result.core_event == "기사 중심 사건"


@pytest.mark.asyncio
async def test_structured_invoke_sends_validation_feedback_on_retry():
    llm = RetryFeedbackStructuredLLM()
    client = IssueDocentLLMClient(llm=llm, structured_output_max_attempts=2)

    await client.generate_article_brief(
        ArticleForGeneration(
            article_pk=1,
            article_id="article-1",
            article_order=0,
            title="테스트 기사",
            url="https://example.com",
            press="신문",
            published_date=datetime(2026, 5, 19),
            content="본문",
            similarity_to_centroid=1.0,
        )
    )

    assert llm.calls == 2
    assert "이전 출력은 구조 검증에 실패했습니다" in llm.message_history[1][-1].content
    assert "paragraph source_article_orders must be selected articles" in llm.message_history[1][-1].content


@pytest.mark.asyncio
async def test_generate_content_plan_uses_structured_plan_schema_and_article_payload():
    llm = CapturingStructuredLLM()
    client = IssueDocentLLMClient(llm=llm, structured_output_max_attempts=1)

    result = await client.generate_content_plan(
        cluster=_cluster_context(),
        article_briefs=[
            ArticleBriefOutput(
                article_pk=1,
                article_id="article-1",
                article_order=0,
                brief="첫 기사 요약",
                core_event="첫 기사 중심 사건",
                key_numbers=["10억 원"],
                stated_background=[],
                stated_market_reactions=[],
                stated_interpretations=[],
                low_priority_details=[],
            )
        ],
    )

    assert llm.schema is IssueDocentContentPlanOutput
    assert result.central_issue == "첫 기사 중심 이슈"
    assert '"article_order": 0' in llm.messages[1].content
    assert '"core_event": "첫 기사 중심 사건"' in llm.messages[1].content


@pytest.mark.asyncio
async def test_generate_issue_docent_content_sends_only_content_plan_without_briefs():
    llm = CapturingStructuredLLM(
        response={
            "title": "첫 기사 제목",
            "teaser": "첫 기사 티저",
            "summary": "첫 기사 본문",
        }
    )
    client = IssueDocentLLMClient(llm=llm, structured_output_max_attempts=1)
    selected_brief = ArticleBriefOutput(
        article_pk=1,
        article_id="article-1",
        article_order=0,
        brief="첫 기사 요약",
        core_event="첫 기사 중심 사건",
        key_numbers=[],
        stated_background=[],
        stated_market_reactions=[],
        stated_interpretations=[],
        low_priority_details=[],
    )
    omitted_brief = ArticleBriefOutput(
        article_pk=2,
        article_id="article-2",
        article_order=1,
        brief="둘째 기사 요약",
        core_event="둘째 기사 중심 사건",
        key_numbers=[],
        stated_background=[],
        stated_market_reactions=[],
        stated_interpretations=[],
        low_priority_details=[],
    )

    await client.generate_issue_docent_content(
        cluster=_cluster_context(),
        article_briefs=[selected_brief, omitted_brief],
        content_plan=IssueDocentContentPlanOutput(
            central_article_order=0,
            central_issue="첫 기사 중심 이슈",
            selected_article_orders=[0],
            omitted_article_orders=[1],
            paragraphs=[
                {
                    "section": "fact",
                    "source_article_orders": [0],
                    "facts": ["첫 기사 중심 사실"],
                }
            ],
        ),
    )

    assert '"content_plan"' in llm.messages[1].content
    assert '"central_issue": "첫 기사 중심 이슈"' in llm.messages[1].content
    assert '"article_briefs"' not in llm.messages[1].content
    assert '"첫 기사 중심 사건"' not in llm.messages[1].content
    assert '"article_order": 1' not in llm.messages[1].content
    assert "둘째 기사 중심 사건" not in llm.messages[1].content


def test_create_main_llm_uses_vertex_with_main_model(monkeypatch):
    monkeypatch.setattr(client_module, "ChatGoogleGenerativeAI", FakeChatGoogleGenerativeAI)
    monkeypatch.setattr(client_module.getenv, "MAIN_MODEL", "gemini-main")
    monkeypatch.setattr(client_module.getenv, "GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setattr(client_module.getenv, "GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.setattr(client_module.getenv, "LLM_THINKING_LEVEL", "medium")
    monkeypatch.setattr(client_module.getenv, "LLM_TIMEOUT_SECONDS", 600)
    monkeypatch.setattr(client_module.getenv, "LLM_TRANSPORT_MAX_RETRIES", 2)

    create_main_llm()

    assert FakeChatGoogleGenerativeAI.kwargs == {
        "model": "gemini-main",
        "vertexai": True,
        "project": "test-project",
        "location": "global",
        "thinking_level": "medium",
        "request_timeout": 600,
        "retries": 2,
    }


def test_create_main_llm_requires_google_cloud_project(monkeypatch):
    monkeypatch.setattr(client_module.getenv, "GOOGLE_CLOUD_PROJECT", "")

    with pytest.raises(RuntimeError, match="GOOGLE_CLOUD_PROJECT"):
        create_main_llm()


def _cluster_context() -> ClusterGenerationContext:
    return ClusterGenerationContext(
        cluster_id=10,
        run_date=datetime(2026, 5, 19).date(),
        cluster_seq=1,
        size=2,
        is_singleton=False,
        created_at=datetime(2026, 5, 19),
        company_names=["삼성전자"],
        sectors=["반도체"],
        keywords=["투자"],
        articles=[
            ArticleForGeneration(
                article_pk=1,
                article_id="article-1",
                article_order=0,
                title="첫 기사",
                url="https://example.com/1",
                press="신문",
                published_date=datetime(2026, 5, 19),
                content="첫 기사 본문",
                similarity_to_centroid=0.9,
            ),
            ArticleForGeneration(
                article_pk=2,
                article_id="article-2",
                article_order=1,
                title="둘째 기사",
                url="https://example.com/2",
                press="신문",
                published_date=datetime(2026, 5, 19),
                content="둘째 기사 본문",
                similarity_to_centroid=0.8,
            ),
        ],
    )
