"""LLM 엔티티 추출 예외."""

from apps.src.exceptions.base import ErrorCode, PipelineError


class LLMExtractionError(PipelineError):
    """LLM API 호출 실패 (일반)."""

    def __init__(
        self,
        message: str,
        cluster_id: int | None = None,
        model: str | None = None,
    ) -> None:
        ctx: dict = {}
        if cluster_id is not None:
            ctx["cluster_id"] = cluster_id
        if model:
            ctx["model"] = model
        super().__init__(message, code=ErrorCode.LLM_API_FAILED, context=ctx)


class LLMRateLimitError(LLMExtractionError):
    """LLM Rate Limit 초과."""

    def __init__(self, message: str, cluster_id: int | None = None) -> None:
        super().__init__(message, cluster_id=cluster_id)
        self.code = ErrorCode.LLM_RATE_LIMITED


class LLMParseError(PipelineError):
    """LLM 응답 구조화 파싱 실패 (Pydantic validation 포함)."""

    def __init__(self, message: str, cluster_id: int | None = None) -> None:
        ctx = {"cluster_id": cluster_id} if cluster_id is not None else {}
        super().__init__(message, code=ErrorCode.LLM_PARSE_FAILED, context=ctx)


class LLMEnvError(PipelineError):
    """LLM 관련 환경변수 누락."""

    def __init__(self, message: str, var_name: str | None = None) -> None:
        ctx = {"var_name": var_name} if var_name else {}
        super().__init__(message, code=ErrorCode.LLM_ENV_MISSING, context=ctx)
