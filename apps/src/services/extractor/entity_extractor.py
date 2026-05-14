"""뉴스 클러스터 엔티티 추출 모듈."""

import logging
import os
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, field_validator

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


class Extraction(BaseModel):
    companies: list[str]
    sectors: list[str]
    keywords: list[str]

    @field_validator("sectors")
    @classmethod
    def validate_sectors(cls, v: list[str]) -> list[str]:
        return [s for s in v if s in _SECTORS_SET]


class EntityExtractor:
    """LangChain + Gemini를 사용해 클러스터별 기업·섹터·키워드를 추출합니다.

    Args:
        delay_sec: 클러스터 간 API 호출 딜레이(초). Rate limit 방지.
    """

    def __init__(self, delay_sec: float = 1.0) -> None:
        llm_model = os.environ.get("LLM_MODEL")
        if not llm_model:
            raise LLMEnvError("LLM_MODEL environment variable is not set", var_name="LLM_MODEL")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            raise LLMEnvError("GEMINI_API_KEY environment variable is not set", var_name="GEMINI_API_KEY")
        llm = ChatGoogleGenerativeAI(
            model=llm_model,
            google_api_key=gemini_key,
        )
        prompt = ChatPromptTemplate.from_template(_PROMPT_TEMPLATE)
        self._chain = prompt | llm.with_structured_output(Extraction)
        self._sectors_text = "\n".join(f"   - {s}" for s in SECTORS)
        self.delay_sec = delay_sec

    def extract(self, clusters: list[dict]) -> list[dict]:
        """각 클러스터에 extraction 필드를 추가합니다."""
        for i, cluster in enumerate(clusters):
            if i > 0:
                time.sleep(self.delay_sec)

            representative = cluster["articles"][0]
            titles = "\n".join(f"- {a['title']}" for a in cluster["articles"])

            try:
                result: Extraction = self._chain.invoke({
                    "titles": titles,
                    "content": representative.get("content") or "",
                    "sectors": self._sectors_text,
                })
                cluster["extraction"] = result.model_dump()
            except Exception as exc:
                exc_str = str(exc).lower()
                if "rate" in exc_str or "quota" in exc_str or "429" in exc_str or "exhausted" in exc_str:
                    err: LLMExtractionError = LLMRateLimitError(str(exc), cluster_id=cluster["cluster_id"])
                else:
                    err = LLMExtractionError(str(exc), cluster_id=cluster["cluster_id"])
                logger.warning("[extract] %s", err)
                cluster["extraction"] = {"companies": [], "sectors": [], "keywords": []}

        return clusters
