"""뉴스 수집 파이프라인 실행 스크립트."""

import argparse
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from apps.src.exceptions.pipeline_exceptions import (
    PipelineEnvError,
    PipelineIOError,
    PipelineStepError,
)
from apps.src.services.collector.company_collector import CompanyCollector
from apps.src.services.collector.macro_collector import fetch_macro_data
from apps.src.services.collector.news_collector import NewsCollector
from apps.src.services.preprocessor.company_preprocessor import CompanyPreprocessor
from apps.src.services.embedder.news_clusterer import NewsClusterer
from apps.src.services.embedder.news_embedder import NewsEmbedder
from apps.src.services.extractor.entity_extractor import EntityExtractor
from apps.src.services.preprocessor.news_preprocessor import NewsPreprocessor
from apps.src.utils.json_utils import save_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# step 함수 시그니처: (run_dir, 이전 단계 결과, args) → 다음 단계 입력
StepFn = Callable[[Path, Any, argparse.Namespace], Any]

from apps.src.config.paths import DATA_DIR as _DATA_DIR

# 스텝별 필수 환경변수
_REQUIRED_ENV: dict[str, list[str]] = {
    "embed":   ["EMBED_MODEL"],
    "extract": ["LLM_MODEL", "GEMINI_API_KEY"],
    "company": ["OPENDART_API_KEY"],
}


@dataclass
class StepResult:
    name: str
    success: bool
    data: Any = None
    error: BaseException | None = field(default=None, repr=False)


def _validate_env() -> None:
    """파이프라인 전체에 필요한 환경변수를 사전 검증합니다."""
    for _step, vars_ in _REQUIRED_ENV.items():
        for var in vars_:
            if not os.environ.get(var):
                raise PipelineEnvError(var)


def _run_step(
    name: str,
    fn: StepFn,
    run_dir: Path,
    data: Any,
    args: argparse.Namespace,
    *,
    fatal: bool,
) -> StepResult:
    """단일 스텝을 실행하고 StepResult를 반환합니다.

    fatal=True: 예외 시 PipelineStepError로 re-raise → 파이프라인 중단.
    fatal=False: 예외 로깅 후 StepResult(success=False) 반환 → 계속 진행.
    """
    logger.info("[pipeline] step=%s start", name)
    try:
        result = fn(run_dir, data, args)
        logger.info("[pipeline] step=%s done", name)
        return StepResult(name=name, success=True, data=result)
    except Exception as exc:
        logger.error("[pipeline] step=%s failed error=%s", name, exc, exc_info=True)
        if fatal:
            raise PipelineStepError(name, exc) from exc
        return StepResult(name=name, success=False, error=exc)


def step_collect(run_dir: Path, _data: None, args: argparse.Namespace) -> list[dict]:
    """네이버 금융 주요뉴스를 수집하고 news_crawled.json에 저장합니다."""
    import math
    # args.limit이 항상 설정되어 있으나, 추후 무제한 수집 허용 시를 대비해 분기 유지
    max_pages = math.ceil(args.limit / 20) if args.limit else 200
    articles = NewsCollector(max_pages=max_pages).collect(date=args.date)
    if args.limit:
        articles = articles[: args.limit]
    save_json(articles, run_dir / "news_crawled.json")
    logger.info("[collect] articles=%d", len(articles))
    return articles


def step_preprocess(_run_dir: Path, articles: list[dict], _args: argparse.Namespace) -> list[dict]:
    """수집된 기사 본문을 정제합니다 (중복 제거, 노이즈 텍스트 제거)."""
    result = NewsPreprocessor().preprocess(articles)
    logger.info("[preprocess] articles=%d", len(result))
    return result


def step_embed(_run_dir: Path, articles: list[dict], _args: argparse.Namespace) -> list[dict]:
    """각 기사에 sentence-transformer 임베딩 벡터를 생성합니다."""
    result = NewsEmbedder().embed(articles)
    dim = len(result[0]["embedding"]) if result else 0
    logger.info("[embed] articles=%d dim=%d", len(result), dim)
    return result


def step_cluster(run_dir: Path, articles: list[dict], _args: argparse.Namespace) -> list[dict]:
    """임베딩 기반 UMAP+HDBSCAN 클러스터링을 수행하고 news_clusters.json에 저장합니다."""
    clusters = NewsClusterer().cluster(articles)
    save_json(clusters, run_dir / "news_clusters.json")
    n_single = sum(1 for c in clusters if c["is_singleton"])
    logger.info("[cluster] clusters=%d singletons=%d", len(clusters), n_single)
    return clusters


def step_extract(run_dir: Path, clusters: list[dict], _args: argparse.Namespace) -> list[dict]:
    """Gemini LLM으로 각 클러스터에서 기업명·섹터·키워드를 추출합니다."""
    result = EntityExtractor().extract(clusters)
    save_json(result, run_dir / "clusters_extracted.json")
    logger.info("[extract] clusters=%d", len(result))
    return result


def step_company(run_dir: Path, clusters: list[dict], _args: argparse.Namespace) -> list[dict]:
    """클러스터에 언급된 기업의 KRX 주가·DART 공시·재무 데이터를 수집합니다."""
    result = CompanyCollector().collect(clusters)
    logger.info("[company] clusters=%d", len(result))
    return result


def step_preprocess_company(run_dir: Path, clusters: list[dict], _args: argparse.Namespace) -> list[dict]:
    """수집된 기업 데이터를 정제합니다 (컬럼명 영문화, 날짜 형식 통일)."""
    result = CompanyPreprocessor().preprocess(clusters)
    logger.info("[preprocess_company] clusters=%d", len(result))
    return result


def step_macro(run_dir: Path, clusters: list[dict], _args: argparse.Namespace) -> list[dict]:
    """Yahoo Finance에서 거시지표를 수집해 각 클러스터에 macro_data 필드를 추가합니다."""
    macro_data = fetch_macro_data()
    for cluster in clusters:
        cluster["macro_data"] = macro_data
    save_json(clusters, run_dir / "clusters_final.json")
    logger.info("[macro] indicators=%d rows=%d", len(macro_data[0]) - 1 if macro_data else 0, len(macro_data))
    return clusters


# 단계를 순서대로 등록합니다. 이후 단계 추가 시 이 목록에 append합니다.
# (name, fn, fatal) — fatal=False는 실패해도 다음 스텝 계속 진행
_PIPELINE: list[tuple[str, StepFn, bool]] = [
    ("collect",            step_collect,            True),
    ("preprocess",         step_preprocess,         True),
    ("embed",              step_embed,              True),
    ("cluster",            step_cluster,            True),
    ("extract",            step_extract,            False),
    ("company",            step_company,            False),
    ("preprocess_company", step_preprocess_company, False),
    ("macro",              step_macro,              False),
]


def main() -> None:
    """CLI 진입점 — 날짜 인자를 파싱하고 파이프라인 전 단계를 순서대로 실행합니다."""
    parser = argparse.ArgumentParser(description="뉴스 수집 파이프라인")
    parser.add_argument("--date", default=None, help="수집 날짜 (YYYYMMDD, 기본: 오늘)")
    # 로컬 CPU 임베딩 속도 문제로 50개 이하로 제한. GPU 환경 또는 API 임베딩 전환 시 상향 조정.
    parser.add_argument("--limit", type=int, default=50, help="최대 수집 기사 수 (기본: 50)")
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = _DATA_DIR / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PipelineIOError(f"Cannot create run dir", path=str(run_dir)) from exc

    logger.info("[pipeline] start run_id=%s", run_id)
    _validate_env()

    data: Any = None
    failed_steps: list[str] = []

    for name, step_fn, fatal in _PIPELINE:
        result = _run_step(name, step_fn, run_dir, data, args, fatal=fatal)
        if result.success:
            data = result.data
        else:
            failed_steps.append(name)

    if failed_steps:
        logger.warning("[pipeline] done with non-fatal failures steps=%s run_id=%s output=%s", failed_steps, run_id, run_dir)
    else:
        logger.info("[pipeline] done run_id=%s output=%s", run_id, run_dir)


if __name__ == "__main__":
    main()
