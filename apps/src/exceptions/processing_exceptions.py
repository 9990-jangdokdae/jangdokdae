"""전처리·임베딩·클러스터링 예외."""

from apps.src.exceptions.base import ErrorCode, PipelineError


class NewsPreprocessError(PipelineError):
    """뉴스 전처리 실패."""

    def __init__(self, message: str, article_id: str | None = None) -> None:
        ctx = {"article_id": article_id} if article_id else {}
        super().__init__(message, code=ErrorCode.NEWS_PREPROCESS_FAILED, context=ctx)


class CompanyPreprocessError(PipelineError):
    """기업 데이터 전처리 실패."""

    def __init__(self, message: str, company_name: str | None = None) -> None:
        ctx = {"company_name": company_name} if company_name else {}
        super().__init__(message, code=ErrorCode.COMPANY_PREPROCESS_FAILED, context=ctx)


class EmbedModelError(PipelineError):
    """임베딩 모델 로드 실패 또는 환경변수 누락."""

    def __init__(self, message: str, model_name: str | None = None) -> None:
        ctx = {"model_name": model_name} if model_name else {}
        super().__init__(message, code=ErrorCode.EMBED_MODEL_LOAD_FAILED, context=ctx)


class EmbedEncodeError(PipelineError):
    """임베딩 인코딩 실패 (CUDA OOM, 입력 이상 등)."""

    def __init__(self, message: str, articles_count: int | None = None) -> None:
        ctx = {"articles_count": articles_count} if articles_count is not None else {}
        super().__init__(message, code=ErrorCode.EMBED_ENCODE_FAILED, context=ctx)


class ClusterError(PipelineError):
    """UMAP/HDBSCAN 클러스터링 실패."""

    def __init__(
        self,
        message: str,
        articles_count: int | None = None,
        stage: str | None = None,
    ) -> None:
        ctx: dict = {}
        if articles_count is not None:
            ctx["articles_count"] = articles_count
        if stage:
            ctx["stage"] = stage
        code = ErrorCode.CLUSTER_UMAP_FAILED if stage == "umap" else ErrorCode.CLUSTER_HDBSCAN_FAILED
        super().__init__(message, code=code, context=ctx)
