"""뉴스·매크로 수집 예외."""

from apps.src.exceptions.base import ErrorCode, PipelineError


class NewsCollectionError(PipelineError):
    """뉴스 목록 수집 실패."""

    def __init__(
        self,
        message: str,
        date: str | None = None,
        page: int | None = None,
    ) -> None:
        ctx: dict = {}
        if date:
            ctx["date"] = date
        if page is not None:
            ctx["page"] = page
        super().__init__(message, code=ErrorCode.NEWS_LIST_FAILED, context=ctx)


class NewsBodyFetchError(PipelineError):
    """뉴스 본문 크롤링 실패 (단일 기사)."""

    def __init__(self, message: str, article_id: str | None = None) -> None:
        ctx = {"article_id": article_id} if article_id else {}
        super().__init__(message, code=ErrorCode.NEWS_BODY_FAILED, context=ctx)


class MacroDataError(PipelineError):
    """거시지표 데이터 수집 실패."""

    def __init__(
        self,
        message: str,
        ticker: str | None = None,
        indicator_name: str | None = None,
    ) -> None:
        ctx: dict = {}
        if ticker:
            ctx["ticker"] = ticker
        if indicator_name:
            ctx["indicator_name"] = indicator_name
        super().__init__(message, code=ErrorCode.MACRO_FETCH_FAILED, context=ctx)
