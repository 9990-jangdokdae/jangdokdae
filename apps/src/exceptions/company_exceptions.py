"""기업 데이터 수집 관련 커스텀 예외."""

from apps.src.exceptions.base import ErrorCode, PipelineError


class CompanyMatchError(PipelineError):
    """기업명 → 종목코드 매칭 실패."""

    def __init__(self, message: str, company_name: str | None = None) -> None:
        ctx = {"company_name": company_name} if company_name else {}
        super().__init__(message, code=ErrorCode.COMPANY_MATCH_FAILED, context=ctx)


class KRXDataError(PipelineError):
    """KRX 데이터 수집 실패."""

    def __init__(self, message: str, krx_code: str | None = None) -> None:
        ctx = {"krx_code": krx_code} if krx_code else {}
        super().__init__(message, code=ErrorCode.KRX_FETCH_FAILED, context=ctx)


class DARTDataError(PipelineError):
    """DART 데이터 수집 실패."""

    def __init__(self, message: str, dart_code: str | None = None) -> None:
        ctx = {"dart_code": dart_code} if dart_code else {}
        super().__init__(message, code=ErrorCode.DART_FETCH_FAILED, context=ctx)
