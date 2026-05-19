from datetime import datetime

import pytest

from apps.src.issue_docent.llm.client import IssueDocentLLMClient
from apps.src.repositories.issue_docent import ArticleForGeneration


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
