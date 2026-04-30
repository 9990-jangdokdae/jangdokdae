"""Smoke tests for collector modules.

This file intentionally performs live external calls. Use it to check whether
collector modules can reach their upstream sources and return minimally valid
data.
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    if load_dotenv is not None:
        load_dotenv(path)
        return
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(PROJECT_ROOT / ".env")

from apps.src.config.pipeline_config import DEFAULT_NEWS_DATE
from apps.src.services.collector.company_master_collector import (
    build_kospi_master,
    fetch_dart_master,
    fetch_krx_master,
)
from apps.src.services.collector.dart_collector import (
    create_dart_client,
    fetch_dart_document_xml,
    fetch_raw_financial_statements,
    find_latest_business_report,
)
from apps.src.services.collector.krx_collector import fetch_stock_market_data
from apps.src.services.collector.macro_collector import fetch_macro_data
from apps.src.services.collector.news_collector import collect_news_articles, collect_news_urls


SAMSUNG_DART_CODE = "00126380"
SAMSUNG_KRX_CODE = "005930"


def print_section(title: str) -> None:
    print(f"\n[{title}]")


def smoke_news(news_date: str, page_limit: int) -> None:
    print_section("news_collector")
    urls = collect_news_urls(news_date=news_date, page_limit=page_limit)
    print(f"urls={len(urls)} sample={urls[:2]}")
    articles = collect_news_articles(news_date=news_date, page_limit=page_limit, concurrency=3)
    print(f"articles_shape={articles.shape} columns={list(articles.columns)}")
    if not articles.empty:
        print(f"first_title={articles.iloc[0].get('news_title')}")


def smoke_macro(period: str) -> None:
    print_section("macro_collector")
    data = fetch_macro_data(period=period)
    print(f"rows={len(data)}")
    if data:
        print(f"first_row_keys={list(data[0].keys())}")


def smoke_krx(start_date: str, end_date: str, krx_code: str) -> None:
    print_section("krx_collector")
    print(
        "env "
        f"KRX_ID={bool(os.getenv('KRX_ID'))} "
        f"KRX_PASSWORD={bool(os.getenv('KRX_PASSWORD'))} "
        f"KRX_PW={bool(os.getenv('KRX_PW'))}"
    )
    data = fetch_stock_market_data(krx_code=krx_code, start_date=start_date, end_date=end_date)
    print(f"ohlcv_rows={len(data['ohlcv'])}")
    print(f"trading_volume_rows={len(data['trading_volume_by_investor'])}")
    if data["ohlcv"]:
        print(f"first_ohlcv={data['ohlcv'][0]}")


def smoke_dart(dart_code: str, fs_year: int) -> None:
    print_section("dart_collector")
    if not os.getenv("OPENDART_API_KEY"):
        print("SKIP: OPENDART_API_KEY is not set")
        return

    dart = create_dart_client()
    report = find_latest_business_report(dart, dart_code)
    print(f"report={report}")
    if report:
        document = fetch_dart_document_xml(dart, report["rcept_no"])
        print(f"document_error={document['error']} xml_len={len(document.get('xml_text') or '')}")

    financials = fetch_raw_financial_statements(dart, dart_code, year=fs_year)
    data = financials.get("data")
    print(f"financials_error={financials['error']} shape={None if data is None else data.shape}")


def smoke_company_master() -> None:
    print_section("company_master_collector")
    print(
        "env "
        f"OPENDART_API_KEY={bool(os.getenv('OPENDART_API_KEY'))} "
        f"KRX_ID={bool(os.getenv('KRX_ID'))} "
        f"KRX_PASSWORD={bool(os.getenv('KRX_PASSWORD'))} "
        f"KRX_PW={bool(os.getenv('KRX_PW'))}"
    )
    if not os.getenv("OPENDART_API_KEY"):
        print("SKIP: OPENDART_API_KEY is not set")
        return

    krx = fetch_krx_master(market="KOSPI", login=False)
    dart = fetch_dart_master()
    kospi = build_kospi_master(dart, krx)
    print(f"krx_shape={krx.shape} dart_shape={dart.shape} kospi_shape={kospi.shape}")
    print(kospi.head(3).to_string(index=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live collector smoke tests.")
    parser.add_argument(
        "--collector",
        choices=["news", "macro", "krx", "dart", "master", "all"],
        default="news",
    )
    parser.add_argument("--news-date", default=DEFAULT_NEWS_DATE)
    parser.add_argument("--page-limit", type=int, default=1)
    parser.add_argument("--macro-period", default="5d")
    parser.add_argument("--krx-code", default=SAMSUNG_KRX_CODE)
    parser.add_argument("--dart-code", default=SAMSUNG_DART_CODE)
    parser.add_argument("--start-date", default="2026-04-20")
    parser.add_argument("--end-date", default="2026-04-30")
    parser.add_argument("--fs-year", type=int, default=2025)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    selected = ["news", "macro", "krx", "dart", "master"] if args.collector == "all" else [args.collector]

    if "news" in selected:
        smoke_news(args.news_date, args.page_limit)
    if "macro" in selected:
        smoke_macro(args.macro_period)
    if "krx" in selected:
        smoke_krx(args.start_date, args.end_date, args.krx_code)
    if "dart" in selected:
        smoke_dart(args.dart_code, args.fs_year)
    if "master" in selected:
        smoke_company_master()


if __name__ == "__main__":
    main()
