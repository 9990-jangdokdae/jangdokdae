import json
from dataclasses import asdict
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from apps.src.issue_docent.config import Settings, get_settings
from apps.src.repositories.issue_docent import ArticleForGeneration, ClusterGenerationContext
from apps.src.issue_docent.llm.prompt_loader import load_prompt
from apps.src.schemas.issue_docent_llm import (
    ArticleBriefOutput,
    ClusterSummaryOutput,
    IssueDocentOutput,
    QuizOutput,
)


def create_main_llm(settings: Settings | None = None) -> ChatGoogleGenerativeAI:
    settings = settings or get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.main_model,
        api_key=settings.google_genai_api_key,
        thinking_level=settings.llm_thinking_level,
        request_timeout=settings.llm_timeout_seconds,
        retries=settings.llm_transport_max_retries,
    )


class IssueDocentLLMClient:
    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm or create_main_llm()

    async def generate_article_brief(self, article: ArticleForGeneration) -> ArticleBriefOutput:
        return await self._structured_invoke(
            schema=ArticleBriefOutput,
            prompt_name="article_brief.md",
            payload={"article": _jsonable(asdict(article))},
        )

    async def generate_cluster_summary(
        self,
        *,
        cluster: ClusterGenerationContext,
        article_briefs: list[ArticleBriefOutput],
    ) -> ClusterSummaryOutput:
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
            schema=ClusterSummaryOutput,
            prompt_name="cluster_summary.md",
            payload=payload,
        )

    async def generate_issue_docent(
        self,
        cluster_summary: ClusterSummaryOutput,
    ) -> IssueDocentOutput:
        return await self._structured_invoke(
            schema=IssueDocentOutput,
            prompt_name="issue_docent.md",
            payload={"cluster_summary": cluster_summary.model_dump()},
        )

    async def generate_quizzes(
        self,
        *,
        issue_docent: IssueDocentOutput,
        term_candidates: list[dict[str, Any]],
    ) -> QuizOutput:
        return await self._structured_invoke(
            schema=QuizOutput,
            prompt_name="quiz.md",
            payload={
                "explanation": issue_docent.model_dump()["explanation"],
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
        result = await runnable.ainvoke(
            [
                SystemMessage(content=load_prompt(prompt_name)),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False, default=str)),
            ]
        )
        if isinstance(result, schema):
            result = result.model_dump()
        return schema.model_validate(result, context=validation_context)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
