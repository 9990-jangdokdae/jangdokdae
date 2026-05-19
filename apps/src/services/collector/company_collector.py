"""기업 데이터 수집 오케스트레이터."""

import logging
from datetime import datetime

import OpenDartReader as ODR
import pandas as pd

from apps.src.config import getenv
from apps.src.exceptions.company_exceptions import CompanyMatchError, DARTDataError, KRXDataError
from apps.src.services.collector.company_master_collector import CompanyMasterCollector
from apps.src.services.collector.dart_collector import (
    fetch_disclosure_list,
    fetch_financial_statements,
    fetch_latest_business_report,
)
from apps.src.services.collector.krx_collector import fetch_ohlcv

logger = logging.getLogger(__name__)


def _pd_str(row: pd.Series, col: str) -> str | None:
    """pandas Series에서 컬럼 값을 가져오되 NaN·None·"None" 문자열은 None으로 반환합니다.

    dtype=str로 JSON 로드 시 null → 문자열 "None"이 되는 pandas 동작을 보정합니다.
    """
    val = row.get(col)
    if val is None or val == "None":
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return str(val)


class CompanyCollector:
    """클러스터 내 기업명으로 KRX·DART 데이터를 수집합니다.

    Args:
        market_days: 주가 수집 거래일 수.
        disclosure_months: 공시 수집 기간(월).
    """

    def __init__(self, market_days: int = 60, disclosure_months: int = 3) -> None:
        """수집 범위(거래일 수, 공시 기간)와 기준 날짜를 초기화합니다."""
        self.market_days = market_days
        self.disclosure_months = disclosure_months
        self._end_date = datetime.now().strftime("%Y%m%d")
        self._fs_year = datetime.now().year - 1

    def collect(self, clusters: list[dict]) -> list[dict]:
        """각 클러스터의 기업 데이터를 수집해 company_data 필드를 추가합니다."""
        master = CompanyMasterCollector().load()
        dart = ODR(getenv.OPENDART_API_KEY)

        # 전체 파이프라인에서 언급된 고유 기업명 수집 (중복 API 호출 방지)
        all_companies: set[str] = set()
        for cluster in clusters:
            all_companies.update(cluster.get("extraction", {}).get("companies", []))

        company_cache: dict[str, dict] = {}
        for name in all_companies:
            company_cache[name] = self._collect_one(name, master, dart)

        for cluster in clusters:
            names = cluster.get("extraction", {}).get("companies", [])
            cluster["company_data"] = [company_cache[name] for name in names if name in company_cache]

        return clusters

    def _collect_one(
        self,
        company_name: str,
        master: pd.DataFrame,
        dart: ODR,
    ) -> dict:
        """단일 기업명에 대해 KRX·DART 전 데이터를 수집하고 결과 dict를 반환합니다."""
        try:
            krx_code, dart_code, dart_name, sector, market = self._match(company_name, master)
        except CompanyMatchError as exc:
            logger.warning("[company] match failed company=%s reason=%s", company_name, exc)
            return {"company_name": company_name, "matched": False}

        result: dict = {
            "company_name": company_name,
            "matched": True,
            "krx_code": krx_code,
            "dart_code": dart_code,
            "dart_name": dart_name,
            "sector": sector,
            "market": market,       # "KOSPI" | "KOSDAQ" | None
            "market_data": {},      # {"ohlcv": [...]}
            "dart": {},
        }

        try:
            result["market_data"]["ohlcv"] = fetch_ohlcv(krx_code, self.market_days, self._end_date)
        except KRXDataError as exc:
            logger.warning("[company] ohlcv failed company=%s reason=%s", company_name, exc)

        try:
            result["dart"]["disclosures"] = fetch_disclosure_list(dart, dart_code, self.disclosure_months)
        except DARTDataError as exc:
            logger.warning("[company] disclosures failed company=%s reason=%s", company_name, exc)

        try:
            result["dart"]["business_report"] = fetch_latest_business_report(dart, dart_code)
        except DARTDataError as exc:
            logger.warning("[company] business_report failed company=%s reason=%s", company_name, exc)

        try:
            result["dart"]["financial_statements"] = fetch_financial_statements(dart, dart_code, self._fs_year)
        except DARTDataError as exc:
            logger.warning("[company] financial_statements failed company=%s reason=%s", company_name, exc)

        return result

    def _match(self, company_name: str, master: pd.DataFrame) -> tuple[str, str, str, str | None, str | None]:
        """기업명으로 (krx_code, dart_code, dart_name, sector, market)을 반환합니다."""
        # 정확 매칭 우선
        exact = master[master["dart_name"] == company_name]
        if not exact.empty:
            row = exact.iloc[0]
            return row["krx_code"], row["dart_code"], row["dart_name"], _pd_str(row, "sector"), _pd_str(row, "market")

        # 부분 매칭 — 길이 차이가 작은 순(가장 유사한 이름 우선)
        partial = master[master["dart_name"].str.contains(company_name, na=False, regex=False)]
        if not partial.empty:
            row = partial.loc[partial["dart_name"].str.len().sub(len(company_name)).abs().idxmin()]
            return row["krx_code"], row["dart_code"], row["dart_name"], _pd_str(row, "sector"), _pd_str(row, "market")

        raise CompanyMatchError(f"no match for '{company_name}'")
