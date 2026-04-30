"""Collector pipeline 단계별 실행 CLI.

각 서브커맨드는 노트북의 큰 셀 묶음 하나에 대응합니다. 전체 파이프라인을 한 번에
강제 실행하지 않고 단계별 파일을 남기도록 해, API 실패나 중간 결과 확인이 쉬운
형태로 구성했습니다.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.src.config.pipeline_config import (
    CLUSTER_PAYLOAD_PATH,
    DART_MASTER_PATH,
    DEFAULT_NEWS_DATE,
    KRX_MASTER_PATH,
    KOSPI_MASTER_PATH,
    NEWS_ARTICLES_PATH,
    NEWS_METADATA_KOSPI_PATH,
    NEWS_WITH_METADATA_PATH,
)
from apps.src.services.collector.company_master_collector import build_and_save_company_masters
from apps.src.services.collector.dart_collector import create_dart_client
from apps.src.services.collector.news_collector import collect_news_articles
from apps.src.services.embedder.news_clusterer import cluster_news_embeddings
from apps.src.services.embedder.news_embedder import embed_news_articles
from apps.src.services.preprocessor.company_preprocessor import filter_kospi_companies
from apps.src.services.preprocessor.metadata_preprocessor import extract_metadata_from_news
from apps.src.services.preprocessor.news_preprocessor import normalize_news_columns, preprocess_news_articles
from apps.src.services.preprocessor.payload_preprocessor import build_cluster_context_payload
from apps.src.services.utils import coerce_list

logger = logging.getLogger(__name__)


def save_pickle(data, path: str | Path) -> None:
    """MVP 중간 산출물을 apps/data 아래 pickle로 저장합니다."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(data, output_path)


def load_sector_articles(path: str | Path, primary_sector: str) -> pd.DataFrame:
    """primary_sector 기준으로 pickle 기사 데이터를 필터링합니다."""
    df = normalize_news_columns(pd.read_pickle(path))
    if "primary_sector" not in df.columns:
        return df.iloc[0:0].copy()
    return df[df["primary_sector"] == primary_sector].copy()


def configure_logging(level: int = logging.INFO) -> None:
    """콘솔에서 파이프라인 진행상황이 보이도록 기본 로그 포맷을 설정합니다."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def collect_articles(args: argparse.Namespace) -> None:
    """뉴스 URL 수집과 본문 수집을 실행하고 pickle로 저장합니다."""
    started = time.perf_counter()
    logger.info(
        "[collect-articles] start date=%s page_limit=%s concurrency=%s output=%s",
        args.news_date,
        args.page_limit,
        args.concurrency,
        args.output,
    )
    df = collect_news_articles(
        news_date=args.news_date,
        page_limit=args.page_limit,
        concurrency=args.concurrency,
    )
    df = preprocess_news_articles(df)
    save_pickle(df, args.output)
    logger.info(
        "[collect-articles] done rows=%s output=%s elapsed=%.1fs",
        len(df),
        args.output,
        time.perf_counter() - started,
    )


def build_masters(args: argparse.Namespace) -> None:
    """DART/KRX 기업 마스터를 생성하고 pickle로 저장합니다."""
    started = time.perf_counter()
    logger.info(
        "[build-masters] start market=%s date=%s login_krx=%s dart=%s krx=%s kospi=%s",
        args.market,
        args.date,
        args.login_krx,
        args.dart_master_output,
        args.krx_master_output,
        args.kospi_master_output,
    )
    kospi_master = build_and_save_company_masters(
        dart_master_path=args.dart_master_output,
        krx_master_path=args.krx_master_output,
        kospi_master_path=args.kospi_master_output,
        market=args.market,
        date=args.date,
        login_krx_first=args.login_krx,
        extract_dir=args.extract_dir,
    )
    logger.info(
        "[build-masters] done kospi_rows=%s output=%s elapsed=%.1fs",
        len(kospi_master),
        args.kospi_master_output,
        time.perf_counter() - started,
    )


def extract_metadata(args: argparse.Namespace) -> None:
    """기사 pickle을 읽어 OpenAI 메타데이터 추출 결과를 저장합니다."""
    started = time.perf_counter()
    logger.info("[extract-metadata] start input=%s output=%s model=%s", args.input, args.output, args.model)
    articles_df = pd.read_pickle(args.input)
    logger.info("[extract-metadata] loaded rows=%s columns=%s", len(articles_df), list(articles_df.columns))
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    result_df = extract_metadata_from_news(
        articles_df,
        client=client,
        model=args.model,
        sleep_sec=args.sleep_sec,
    )
    save_pickle(result_df, args.output)
    errors = int(result_df["error"].notna().sum()) if "error" in result_df else 0
    logger.info(
        "[extract-metadata] done rows=%s errors=%s output=%s elapsed=%.1fs",
        len(result_df),
        errors,
        args.output,
        time.perf_counter() - started,
    )


def filter_kospi(args: argparse.Namespace) -> None:
    """LLM 추출 기업명 중 KOSPI/DART 마스터에 존재하는 기업만 남깁니다."""
    started = time.perf_counter()
    logger.info("[filter-kospi] start input=%s kospi_master=%s output=%s", args.input, args.kospi_master, args.output)
    df = normalize_news_columns(pd.read_pickle(args.input))
    kospi_master = pd.read_pickle(args.kospi_master)
    before = sum(len(coerce_list(v)) for v in df["company"]) if "company" in df else 0
    result_df = filter_kospi_companies(df, kospi_master)
    after = sum(len(coerce_list(v)) for v in result_df["company"]) if "company" in result_df else 0
    save_pickle(result_df, args.output)
    logger.info(
        "[filter-kospi] done rows=%s companies_before=%s companies_after=%s output=%s elapsed=%.1fs",
        len(result_df),
        before,
        after,
        args.output,
        time.perf_counter() - started,
    )


def cluster(args: argparse.Namespace) -> None:
    """기사 임베딩을 생성하고 이슈 클러스터 및 대표기사 순위를 계산합니다."""
    started = time.perf_counter()
    logger.info(
        "[cluster] start input=%s sector=%s output=%s model=%s batch_size=%s max_chars=%s threshold=%s",
        args.input,
        args.sector,
        args.output,
        args.embedding_model,
        args.embedding_batch_size,
        args.embedding_max_text_chars,
        args.distance_threshold,
    )
    if args.sector:
        df = load_sector_articles(args.input, args.sector)
    else:
        df = pd.read_pickle(args.input)
    logger.info("[cluster] loaded rows=%s columns=%s", len(df), list(df.columns))

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    embeddings = embed_news_articles(
        df,
        client=client,
        model=args.embedding_model,
        batch_size=args.embedding_batch_size,
        max_text_chars=args.embedding_max_text_chars,
    )
    logger.info("[cluster] embeddings shape=%s", embeddings.shape)
    clustered_df = cluster_news_embeddings(
        df,
        embeddings,
        distance_threshold=args.distance_threshold,
    )
    save_pickle(clustered_df, args.output)
    logger.info(
        "[cluster] done rows=%s clusters=%s output=%s elapsed=%.1fs",
        len(clustered_df),
        clustered_df["cluster_id"].nunique(),
        args.output,
        time.perf_counter() - started,
    )


def build_payload(args: argparse.Namespace) -> None:
    """클러스터 결과에 DART/시장/거시 데이터를 붙여 최종 payload pickle을 만듭니다."""
    started = time.perf_counter()
    logger.info(
        "[build-payload] start input=%s kospi_master=%s output=%s top_n=%s top_k=%s fs_year=%s market_days=%s macro_period=%s",
        args.input,
        args.kospi_master,
        args.output,
        args.top_n_clusters,
        args.top_k_articles,
        args.fs_year,
        args.market_days,
        args.macro_period,
    )
    clustered_df = pd.read_pickle(args.input)
    kospi_master = pd.read_pickle(args.kospi_master)
    logger.info(
        "[build-payload] loaded clustered_rows=%s clusters=%s kospi_master_rows=%s",
        len(clustered_df),
        clustered_df["cluster_id"].nunique() if "cluster_id" in clustered_df else None,
        len(kospi_master),
    )
    dart = create_dart_client()
    payload = build_cluster_context_payload(
        clustered_df=clustered_df,
        kospi_master=kospi_master,
        dart=dart,
        top_n_clusters=args.top_n_clusters,
        top_k_articles=args.top_k_articles,
        fs_year=args.fs_year,
        market_days=args.market_days,
        macro_period=args.macro_period,
    )
    save_pickle(payload, args.output)
    logger.info(
        "[build-payload] done clusters=%s output=%s elapsed=%.1fs",
        len(payload["clusters"]),
        args.output,
        time.perf_counter() - started,
    )


def build_parser() -> argparse.ArgumentParser:
    """argparse 서브커맨드와 기본 입출력 경로를 정의합니다."""
    parser = argparse.ArgumentParser(description="Run collector data pipeline.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("collect-articles")
    p.add_argument("--news-date", default=DEFAULT_NEWS_DATE)
    p.add_argument("--page-limit", type=int, default=20)
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--output", default=NEWS_ARTICLES_PATH)
    p.set_defaults(func=collect_articles)

    p = sub.add_parser("build-masters")
    p.add_argument("--market", default="KOSPI")
    p.add_argument("--date", default=None)
    p.add_argument("--login-krx", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--extract-dir", default=None)
    p.add_argument("--dart-master-output", default=DART_MASTER_PATH)
    p.add_argument("--krx-master-output", default=KRX_MASTER_PATH)
    p.add_argument("--kospi-master-output", default=KOSPI_MASTER_PATH)
    p.set_defaults(func=build_masters)

    p = sub.add_parser("extract-metadata")
    p.add_argument("--input", default=NEWS_ARTICLES_PATH)
    p.add_argument("--output", default=NEWS_WITH_METADATA_PATH)
    p.add_argument("--model", default="gpt-5.4-nano")
    p.add_argument("--sleep-sec", type=float, default=0.2)
    p.set_defaults(func=extract_metadata)

    p = sub.add_parser("filter-kospi")
    p.add_argument("--input", default=NEWS_WITH_METADATA_PATH)
    p.add_argument("--kospi-master", default=KOSPI_MASTER_PATH)
    p.add_argument("--output", default=NEWS_METADATA_KOSPI_PATH)
    p.set_defaults(func=filter_kospi)

    p = sub.add_parser("cluster")
    p.add_argument("--input", default=NEWS_METADATA_KOSPI_PATH)
    p.add_argument("--sector", default=None)
    p.add_argument("--output", default=NEWS_METADATA_KOSPI_PATH.parent / "news_clustered.pkl")
    p.add_argument("--embedding-model", default="text-embedding-3-small")
    p.add_argument("--embedding-batch-size", type=int, default=50)
    p.add_argument("--embedding-max-text-chars", type=int, default=3000)
    p.add_argument("--distance-threshold", type=float, default=0.35)
    p.set_defaults(func=cluster)

    p = sub.add_parser("build-payload")
    p.add_argument("--input", default=NEWS_METADATA_KOSPI_PATH.parent / "news_clustered.pkl")
    p.add_argument("--kospi-master", default=KOSPI_MASTER_PATH)
    p.add_argument("--output", default=CLUSTER_PAYLOAD_PATH)
    p.add_argument("--top-n-clusters", type=int, default=5)
    p.add_argument("--top-k-articles", type=int, default=5)
    p.add_argument("--fs-year", type=int, default=2025)
    p.add_argument("--market-days", type=int, default=5)
    p.add_argument("--macro-period", default="7d")
    p.set_defaults(func=build_payload)

    return parser


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


def run_pipeline_from_code() -> None:
    """터미널 CLI 없이 이 파일을 직접 실행할 때 사용하는 실행 코드입니다.

    아래 RUN_* 값을 True/False로 바꿔 원하는 단계만 실행합니다.
    """
    configure_logging()

    RUN_BUILD_MASTERS = False
    RUN_COLLECT_ARTICLES = False
    RUN_EXTRACT_METADATA = False
    RUN_FILTER_KOSPI = False
    RUN_CLUSTER = False
    RUN_BUILD_PAYLOAD = True

    NEWS_DATE = "2026-04-28"
    MASTER_DATE = None  # 예: "20260430". None이면 오늘 날짜 기준.
    CLUSTERED_OUTPUT = NEWS_METADATA_KOSPI_PATH.parent / "news_clustered.pkl"
    SECTOR = '반도체'  # 특정 섹터만 클러스터링하려면 예: "반도체"
    logger.info(
        "[pipeline] selected steps masters=%s collect=%s metadata=%s filter=%s cluster=%s payload=%s sector=%s",
        RUN_BUILD_MASTERS,
        RUN_COLLECT_ARTICLES,
        RUN_EXTRACT_METADATA,
        RUN_FILTER_KOSPI,
        RUN_CLUSTER,
        RUN_BUILD_PAYLOAD,
        SECTOR,
    )

    if RUN_BUILD_MASTERS:
        build_masters(SimpleNamespace(
            market="KOSPI",
            date=MASTER_DATE,
            login_krx=True,
            extract_dir=None,
            dart_master_output=DART_MASTER_PATH,
            krx_master_output=KRX_MASTER_PATH,
            kospi_master_output=KOSPI_MASTER_PATH,
        ))

    if RUN_COLLECT_ARTICLES:
        collect_articles(SimpleNamespace(
            news_date=NEWS_DATE,
            page_limit=20,
            concurrency=10,
            output=NEWS_ARTICLES_PATH,
        ))

    if RUN_EXTRACT_METADATA:
        extract_metadata(SimpleNamespace(
            input=NEWS_ARTICLES_PATH,
            output=NEWS_WITH_METADATA_PATH,
            model="gpt-5.4-nano",
            sleep_sec=0.2,
        ))

    if RUN_FILTER_KOSPI:
        filter_kospi(SimpleNamespace(
            input=NEWS_WITH_METADATA_PATH,
            kospi_master=KOSPI_MASTER_PATH,
            output=NEWS_METADATA_KOSPI_PATH,
        ))

    if RUN_CLUSTER:
        cluster(SimpleNamespace(
            input=NEWS_METADATA_KOSPI_PATH,
            sector=SECTOR,
            output=CLUSTERED_OUTPUT,
            embedding_model="text-embedding-3-small",
            embedding_batch_size=20,
            embedding_max_text_chars=1500,
            distance_threshold=0.35,
        ))

    if RUN_BUILD_PAYLOAD:
        build_payload(SimpleNamespace(
            input=CLUSTERED_OUTPUT,
            kospi_master=KOSPI_MASTER_PATH,
            output=CLUSTER_PAYLOAD_PATH,
            top_n_clusters=5,
            top_k_articles=5,
            fs_year=2025,
            market_days=5,
            macro_period="7d",
        ))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        run_pipeline_from_code()
