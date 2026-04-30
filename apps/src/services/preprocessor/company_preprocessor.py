"""Company name filtering and code resolution."""

import logging
from typing import Any

import pandas as pd

from apps.src.services.preprocessor.news_preprocessor import normalize_news_columns
from apps.src.services.utils import coerce_list

logger = logging.getLogger(__name__)


def filter_kospi_companies(
    df: pd.DataFrame,
    kospi_master: pd.DataFrame,
    source_col: str = "company",
    target_col: str = "company",
) -> pd.DataFrame:
    """기사 company 값 중 KOSPI/DART 마스터에 존재하는 기업만 남깁니다."""
    out = normalize_news_columns(df.copy())
    valid_names = set(kospi_master["dart_name"]).union(set(kospi_master["krx_name"]))

    out[target_col] = [
        [company for company in coerce_list(companies) if company in valid_names]
        for companies in out[source_col]
    ]
    before = sum(len(coerce_list(v)) for v in df[source_col])
    after = sum(len(coerce_list(v)) for v in out[target_col])
    logger.info("[company] kospi filter companies before=%s after=%s", before, after)
    return out


def resolve_company_codes(company_name: str, kospi_master: pd.DataFrame) -> dict[str, Any] | None:
    """기업명을 KOSPI/DART 마스터의 dart_code/krx_code로 매핑합니다."""
    matched = kospi_master[
        (kospi_master["dart_name"] == company_name)
        | (kospi_master["krx_name"] == company_name)
    ]
    if matched.empty:
        return None

    row = matched.iloc[0]
    return {
        "company_name": company_name,
        "dart_code": row["dart_code"],
        "krx_code": row["krx_code"],
        "dart_name": row["dart_name"],
        "krx_name": row["krx_name"],
    }
