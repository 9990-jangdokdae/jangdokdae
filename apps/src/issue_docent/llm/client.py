import json
from dataclasses import asdict
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.src.config import getenv
from apps.src.repositories.issue_docent import ArticleForGeneration, ClusterGenerationContext
from apps.src.issue_docent.llm.prompt_loader import load_prompt
from apps.src.schemas.issue_docent_llm import (
    ArticleBriefOutput,
    IssueDocentContentOutput,
    QuizOutput,
)


def create_main_llm() -> ChatGoogleGenerativeAI:
    if not getenv.GOOGLE_CLOUD_PROJECT:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT 환경변수가 필요합니다.")

    return ChatGoogleGenerativeAI(
        model=getenv.MAIN_MODEL,
        vertexai=True,
        project=getenv.GOOGLE_CLOUD_PROJECT,
        location=getenv.GOOGLE_CLOUD_LOCATION,
        thinking_level=getenv.LLM_THINKING_LEVEL,
        request_timeout=getenv.LLM_TIMEOUT_SECONDS,
        retries=getenv.LLM_TRANSPORT_MAX_RETRIES,
    )


class IssueDocentLLMClient:
    def __init__(
        self,
        llm: Any | None = None,
        *,
        structured_output_max_attempts: int | None = None,
    ) -> None:
        self.llm = llm or create_main_llm()
        self.structured_output_max_attempts = max(
            1,
            structured_output_max_attempts or getenv.LLM_TRANSPORT_MAX_RETRIES + 1,
        )

    async def generate_article_brief(self, article: ArticleForGeneration) -> ArticleBriefOutput:
        return await self._structured_invoke(
            schema=ArticleBriefOutput,
            prompt_name="article_brief.md",
            payload={"article": _jsonable(asdict(article))},
        )

    async def generate_issue_docent_content(
        self,
        *,
        cluster: ClusterGenerationContext,
        article_briefs: list[ArticleBriefOutput],
    ) -> IssueDocentContentOutput:
        payload = {
            "cluster": {
                "cluster_id": cluster.cluster_id,
                "run_date": cluster.run_date.isoformat(),
                "cluster_seq": cluster.cluster_seq,
                "size": cluster.size,
                "is_singleton": cluster.is_singleton,
                "company_names": cluster.company_names,
                "sectors": cluster.sectors,
                "keywords": cluster.keywords,
            },
            "article_titles": [
                {
                    "article_pk": article.article_pk,
                    "article_id": article.article_id,
                    "article_order": article.article_order,
                    "title": article.title,
                    "press": article.press,
                    "published_date": article.published_date.isoformat(),
                }
                for article in cluster.articles
            ],
            "article_briefs": [brief.model_dump() for brief in article_briefs],
        }
        return await self._structured_invoke(
            schema=IssueDocentContentOutput,
            prompt_name="cluster_summary.md",
            payload=payload,
        )

    async def generate_quizzes(
        self,
        *,
        summary: str,
        term_candidates: list[dict[str, Any]],
    ) -> QuizOutput:
        return await self._structured_invoke(
            schema=QuizOutput,
            prompt_name="quiz.md",
            payload={
                "summary": summary,
                "term_candidates": term_candidates,
            },
            validation_context={"has_term_candidates": bool(term_candidates)},
        )

    async def _structured_invoke(
        self,
        *,
        schema: type,
        prompt_name: str,
        payload: dict,
        validation_context: dict[str, Any] | None = None,
    ) -> Any:
        runnable = self.llm.with_structured_output(schema)
        messages = [
            SystemMessage(content=load_prompt(prompt_name)),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str)),
        ]
        last_error: Exception | None = None
        for _ in range(self.structured_output_max_attempts):
            try:
                result = await runnable.ainvoke(messages)
                if isinstance(result, schema):
                    result = result.model_dump()
                return schema.model_validate(result, context=validation_context)
            except Exception as exc:
                last_error = exc
        raise last_error


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
