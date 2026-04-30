"""최종 클러스터 context JSON payload 생성 모듈.

클러스터링된 기사 DataFrame을 다음 단계 LLM/분석기로 넘길 수 있는 JSON 구조로
조립합니다. 클러스터별 기사 묶음, 대표기사, 언급 기업의 DART/재무/시장 데이터,
공통 거시지표를 한 객체 안에 넣습니다.
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd

from apps.src.services.collector.dart_collector import (
    fetch_dart_document_xml,
    fetch_raw_financial_statements,
    find_latest_business_report,
)
from apps.src.services.collector.krx_collector import fetch_recent_stock_market_data
from apps.src.services.collector.macro_collector import fetch_macro_data
from apps.src.services.preprocessor.company_preprocessor import resolve_company_codes
from apps.src.services.preprocessor.dart_preprocessor import (
    normalize_financial_statements,
    preprocess_dart_sections,
)
from apps.src.services.preprocessor.news_preprocessor import normalize_news_columns
from apps.src.services.utils import coerce_list, dedupe_strings

logger = logging.getLogger(__name__)


def collect_cluster_companies(cluster_articles: pd.DataFrame) -> list[str]:
    """클러스터 내 주요 기사들의 company 리스트를 합치고 중복 제거합니다."""
    companies = []
    for values in cluster_articles["company"].dropna():
        companies.extend(coerce_list(values))
    return dedupe_strings(companies)


def collect_cluster_list_values(cluster_articles: pd.DataFrame, col: str) -> list[str]:
    """sector/keyword처럼 리스트형 컬럼 값을 클러스터 단위로 합칩니다."""
    values = []
    for items in cluster_articles[col].dropna():
        values.extend(coerce_list(items))
    return dedupe_strings(values)


def build_company_context(
    company_name: str,
    kospi_master: pd.DataFrame,
    dart,
    fs_year: int,
    market_days: int,
    as_of: str,
    report_start_date: str = "2026-01-01",
) -> dict[str, Any]:
    """기업별 DART/재무/시장 context를 만들고 실패는 errors에 기록합니다."""
    resolved = resolve_company_codes(company_name, kospi_master)
    if resolved is None:
        return {
            "company_name": company_name,
            "matched": False,
            "business_report": None,
            "financial_statements": [],
            "market": {"ohlcv": [], "trading_volume_by_investor": []},
            "errors": [{"source": "company_master", "error": "KOSPI/DART master에서 매칭 실패"}],
        }

    context = {
        **resolved,
        "matched": True,
        "business_report": None,
        "financial_statements": [],
        "market": {"ohlcv": [], "trading_volume_by_investor": []},
        "errors": [],
    }

    try:
        report = find_latest_business_report(
            dart,
            resolved["dart_code"],
            start_date=report_start_date,
            end_date=as_of,
        )
        if report is None:
            context["business_report"] = None
        else:
            document = fetch_dart_document_xml(dart, report["rcept_no"])
            sections = {}
            if document.get("xml_text"):
                sections = preprocess_dart_sections(document["xml_text"])
            if document.get("error"):
                context["errors"].append({"source": "business_report", "error": document["error"]})
            context["business_report"] = {
                "report_nm": report.get("report_nm"),
                "rcept_no": report.get("rcept_no"),
                "rcept_dt": report.get("rcept_dt"),
                "sections": sections,
                "error": document.get("error"),
            }
    except Exception as exc:
        logger.warning("[payload] business report failed company=%s error=%s", company_name, exc)
        context["business_report"] = {
            "sections": {},
            "error": str(exc),
        }
        context["errors"].append({"source": "business_report", "error": str(exc)})

    raw_fs = fetch_raw_financial_statements(dart, resolved["dart_code"], year=fs_year)
    if raw_fs.get("error"):
        context["errors"].append({"source": "financial_statements", "error": raw_fs["error"]})
    context["financial_statements"] = normalize_financial_statements(raw_fs.get("data"), fs_year=fs_year)

    try:
        context["market"] = fetch_recent_stock_market_data(
            resolved["krx_code"],
            days=market_days,
            end_date=as_of,
        )
    except Exception as exc:
        logger.warning("[payload] market failed company=%s krx_code=%s error=%s", company_name, resolved["krx_code"], exc)
        context["market"] = {
            "ohlcv": [],
            "trading_volume_by_investor": [],
            "error": str(exc),
        }
        context["errors"].append({"source": "market", "error": str(exc)})

    return context


def build_cluster_context_payload(
    clustered_df: pd.DataFrame,
    kospi_master: pd.DataFrame,
    dart,
    top_n_clusters: int = 5,
    top_k_articles: int = 5,
    min_cluster_size: int = 2,
    fs_year: int = 2025,
    market_days: int = 5,
    macro_period: str = "7d",
    as_of: str | None = None,
) -> dict[str, Any]:
    """클러스터별 기사/기업/시장/거시 데이터를 JSON 직렬화 가능한 dict로 만듭니다.

    입력 clustered_df는 cluster_id, cluster_size, rank_in_cluster,
    similarity_to_centroid 컬럼이 이미 계산되어 있어야 합니다.
    """
    clustered_df = normalize_news_columns(clustered_df)
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    # 거시지표는 특정 기업이 아니라 클러스터 전체 분석 공통 context로 사용합니다.
    logger.info("[payload] fetching macro period=%s", macro_period)
    macro = fetch_macro_data(period=macro_period)
    logger.info("[payload] macro rows=%s", len(macro))

    top_cluster_ids = (
        clustered_df[["cluster_id", "cluster_size"]]
        .drop_duplicates()
        .query("cluster_size >= @min_cluster_size")
        .sort_values("cluster_size", ascending=False)
        .head(top_n_clusters)["cluster_id"]
        .tolist()
    )
    logger.info("[payload] selected top clusters=%s", top_cluster_ids)

    clusters = []
    for cluster_pos, cluster_id in enumerate(top_cluster_ids, start=1):
        cluster_articles = (
            clustered_df[clustered_df["cluster_id"] == cluster_id]
            .sort_values("rank_in_cluster")
            .head(top_k_articles)
            .copy()
        )
        representative = cluster_articles.iloc[0]
        # 대표기사는 representative_article에 별도 보관하므로, articles에는 나머지
        # 보조 기사만 넣어 같은 본문이 payload에 두 번 들어가지 않게 합니다.
        supporting_articles = cluster_articles[
            cluster_articles["rank_in_cluster"] != representative["rank_in_cluster"]
        ]
        cluster_companies = collect_cluster_companies(cluster_articles)
        logger.info(
            "[payload] cluster %s/%s id=%s articles=%s companies=%s representative=%s",
            cluster_pos,
            len(top_cluster_ids),
            cluster_id,
            len(cluster_articles),
            cluster_companies,
            str(representative.get("news_title"))[:80],
        )

        companies_context = []
        for company_pos, company in enumerate(cluster_companies, start=1):
            # 기업별로 DART context를 먼저 붙이고, KRX 코드 매핑이 된 경우에만 시장
            # 데이터를 추가합니다. 매핑 실패 기업은 JSON에 실패 사유를 남깁니다.
            logger.info(
                "[payload] cluster_id=%s company %s/%s fetching dart company=%s",
                cluster_id,
                company_pos,
                len(cluster_companies),
                company,
            )
            company_context = build_company_context(
                company_name=company,
                kospi_master=kospi_master,
                dart=dart,
                fs_year=fs_year,
                market_days=market_days,
                as_of=as_of,
            )
            companies_context.append(company_context)
            logger.info(
                "[payload] cluster_id=%s company=%s done matched=%s fs_rows=%s",
                cluster_id,
                company,
                company_context.get("matched"),
                len(company_context.get("financial_statements", [])),
            )

        clusters.append({
            "cluster_id": int(cluster_id),
            "cluster_size": int(representative["cluster_size"]),
            "sector": collect_cluster_list_values(cluster_articles, "sector"),
            "keyword": collect_cluster_list_values(cluster_articles, "keyword"),
            "representative_article": {
                "article_idx": int(representative.name),
                "news_title": representative.get("news_title"),
                "news_url": representative.get("news_url"),
                "news_content": representative.get("news_content"),
                "company": coerce_list(representative.get("company", [])),
            },
            "articles": [
                {
                    "article_idx": int(idx),
                    "rank_in_cluster": int(row.get("rank_in_cluster")),
                    "similarity_to_centroid": float(row.get("similarity_to_centroid")),
                    "news_title": row.get("news_title"),
                    "news_url": row.get("news_url"),
                    "news_content": row.get("news_content"),
                    "company": coerce_list(row.get("company", [])),
                }
                for idx, row in supporting_articles.iterrows()
            ],
            "company": companies_context,
            "macro": macro,
        })
        logger.info("[payload] cluster_id=%s done", cluster_id)

    return {
        "as_of": as_of,
        "cluster_selection": {
            "top_n_clusters": top_n_clusters,
            "top_k_articles_per_cluster": top_k_articles,
            "min_cluster_size": min_cluster_size,
        },
        "clusters": clusters,
    }
