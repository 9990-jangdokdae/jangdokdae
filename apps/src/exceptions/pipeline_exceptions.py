"""파이프라인 오케스트레이션 레벨 예외."""

from __future__ import annotations

from typing import Any

from apps.src.exceptions.base import ErrorCode, PipelineError


class PipelineStepError(PipelineError):
    """단일 파이프라인 스텝 실패를 래핑하는 예외."""

    def __init__(
        self,
        step_name: str,
        cause: BaseException,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {"step": step_name, **(context or {})}
        super().__init__(
            f"Pipeline step '{step_name}' failed: {cause}",
            code=ErrorCode.PIPELINE_STEP_FAILED,
            context=ctx,
        )
        self.step_name = step_name
        self.original_cause = cause


class PipelineEnvError(PipelineError):
    """파이프라인 실행에 필요한 환경변수 누락."""

    def __init__(self, var_name: str) -> None:
        super().__init__(
            f"Required environment variable '{var_name}' is not set",
            code=ErrorCode.PIPELINE_ENV_MISSING,
            context={"var_name": var_name},
        )


class PipelineIOError(PipelineError):
    """파이프라인 입출력 실패 (JSON 저장, 디렉터리 생성 등)."""

    def __init__(self, message: str, path: str | None = None) -> None:
        ctx = {"path": path} if path else {}
        super().__init__(message, code=ErrorCode.PIPELINE_IO_FAILED, context=ctx)
