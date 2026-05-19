"""뉴스 클러스터 엔티티 추출 모듈."""

import logging

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, field_validator

from apps.src.config import getenv
from apps.src.config.paths import PROMPTS_DIR
from apps.src.config.sectors import SECTORS
from apps.src.exceptions.extraction_exceptions import (
    LLMEnvError,
    LLMExtractionError,
    LLMRateLimitError,
)

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (PROMPTS_DIR / "entity_extraction.txt").read_text(encoding="utf-8")

_SECTORS_SET = set(SECTORS)
_CONTENT_LIMIT = 1500  # chars — 이후 내용은 엔티티 추출에 불필요


class Extraction(BaseModel):
    companies: list[str]
    sectors: list[str]
    keywords: list[str]

    @field_validator("sectors")
    @classmethod
    def validate_sectors(cls, v: list[str]) -> list[str]:
        return [s for s in v if s in _SECTORS_SET]


class EntityExtractor:
    """LangChain + Gemini를 사용해 클러스터별 기업·섹터·키워드를 추출합니다."""

    _MAX_CONCURRENCY = 3

    def __init__(self) -> None:
        if not getenv.GOOGLE_CLOUD_PROJECT:
            raise LLMEnvError(
                "GOOGLE_CLOUD_PROJECT environment variable is not set",
                var_name="GOOGLE_CLOUD_PROJECT",
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model=getenv.VERTEX_MODEL,
            vertexai=True,
            project=getenv.GOOGLE_CLOUD_PROJECT,
            location=getenv.GOOGLE_CLOUD_LOCATION,
        )
        prompt = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)
        self._chain = prompt | llm.with_structured_output(Extraction)
        self._sectors_text = "\n".join(f"   - {s}" for s in SECTORS)

    def extract(self, clusters: list[dict]) -> list[dict]:
        """각 클러스터에 extraction 필드를 추가합니다."""
        inputs = [
            {
                "titles": "\n".join(f"- {a['title']}" for a in cluster["articles"]),
                "content": (cluster["articles"][0].get("content") or "")[:_CONTENT_LIMIT],
                "sectors": self._sectors_text,
            }
            for cluster in clusters
        ]

        results = self._chain.batch(
            inputs,
            config={"max_concurrency": self._MAX_CONCURRENCY},
            return_exceptions=True,
        )

        for cluster, result in zip(clusters, results):
            if isinstance(result, Exception):
                exc_str = str(result).lower()
                if "rate" in exc_str or "quota" in exc_str or "429" in exc_str or "exhausted" in exc_str:
                    err: LLMExtractionError = LLMRateLimitError(str(result), cluster_id=cluster["cluster_id"])
                else:
                    err = LLMExtractionError(str(result), cluster_id=cluster["cluster_id"])
                logger.warning("[extract] %s", err)
                cluster["extraction"] = {"companies": [], "sectors": [], "keywords": []}
            else:
                cluster["extraction"] = result.model_dump()

        return clusters
