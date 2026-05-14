"""파이프라인 예외 베이스 클래스 및 에러 코드 체계."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    # ── 1000번대: 수집 (Collector) ─────────────────────────────
    KRX_FETCH_FAILED        = 1001
    KRX_DATA_EMPTY          = 1002
    DART_FETCH_FAILED       = 1011
    DART_XML_PARSE_FAILED   = 1012
    NEWS_LIST_FAILED        = 1021
    NEWS_BODY_FAILED        = 1022
    MACRO_FETCH_FAILED      = 1031
    COMPANY_MATCH_FAILED    = 1041

    # ── 2000번대: 전처리 (Preprocessor) ───────────────────────
    NEWS_PREPROCESS_FAILED      = 2001
    COMPANY_PREPROCESS_FAILED   = 2002

    # ── 3000번대: 임베딩 (Embedder) ────────────────────────────
    EMBED_MODEL_LOAD_FAILED = 3001
    EMBED_ENCODE_FAILED     = 3002

    # ── 4000번대: 클러스터링 (Clusterer) ──────────────────────
    CLUSTER_UMAP_FAILED     = 4001
    CLUSTER_HDBSCAN_FAILED  = 4002

    # ── 5000번대: LLM 추출 (Extractor) ────────────────────────
    LLM_API_FAILED          = 5001
    LLM_PARSE_FAILED        = 5002
    LLM_RATE_LIMITED        = 5003
    LLM_ENV_MISSING         = 5004

    # ── 9000번대: 파이프라인 전역 ─────────────────────────────
    PIPELINE_STEP_FAILED    = 9001
    PIPELINE_ENV_MISSING    = 9002
    PIPELINE_IO_FAILED      = 9003


class PipelineError(Exception):
    """모든 파이프라인 예외의 베이스 클래스.

    Args:
        message: 사람이 읽는 에러 설명.
        code: ErrorCode enum 값.
        context: 진단에 필요한 추가 정보 (company_name, cluster_id 등).
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context: dict[str, Any] = context or {}

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.code is not None:
            parts.append(f"[{self.code.name}={self.code.value}]")
        if self.context:
            ctx_str = " ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"context=({ctx_str})")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """로깅·직렬화용 dict 반환."""
        return {
            "error": type(self).__name__,
            "message": super().__str__(),
            "code": self.code.value if self.code else None,
            "code_name": self.code.name if self.code else None,
            "context": self.context,
        }
