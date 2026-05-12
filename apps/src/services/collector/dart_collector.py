"""DART 공시·사업보고서·재무제표 수집."""

import logging
from datetime import datetime, timedelta

import OpenDartReader as ODR

from apps.src.exceptions.company_exceptions import DARTDataError
from apps.src.services.preprocessor.dart_preprocessor import (
    normalize_financial_statements,
    preprocess_dart_sections,
)
from apps.src.utils.json_utils import dataframe_to_records

logger = logging.getLogger(__name__)


def fetch_disclosure_list(dart: ODR, dart_code: str, months: int = 3) -> list[dict]:
    """최근 months개월 공시 목록을 수집합니다."""
    now = datetime.now()
    start = now - timedelta(days=months * 31)
    try:
        df = dart.list(dart_code, start.strftime("%Y%m%d"), now.strftime("%Y%m%d"))
        if df is None or df.empty:
            return []
        return dataframe_to_records(df[["rcept_no", "rcept_dt", "report_nm"]].head(50))
    except Exception as exc:
        raise DARTDataError(f"disclosure list failed dart_code={dart_code}") from exc


def fetch_latest_business_report(dart: ODR, dart_code: str) -> dict | None:
    """최신 사업보고서를 수집하고 XML을 파싱해 핵심 섹션을 반환합니다."""
    now = datetime.now()
    end = now.strftime("%Y%m%d")
    start = (now - timedelta(days=365)).strftime("%Y%m%d")
    try:
        reports = dart.list(dart_code, start, end, kind="A")  # A: 사업보고서
        if reports is None or reports.empty:
            return None
        latest = reports.sort_values("rcept_dt", ascending=False).iloc[0]
        rcept_no = latest["rcept_no"]

        try:
            document = dart.document(rcept_no)
            sections = preprocess_dart_sections(document) if document else {}
        except Exception as exc:
            logger.warning("[dart] xml parse failed rcept_no=%s error=%s", rcept_no, exc)
            sections = {}

        return {
            "rcept_no": rcept_no,
            "rcept_dt": latest.get("rcept_dt"),
            "report_nm": latest.get("report_nm"),
            "sections": sections,
        }
    except DARTDataError:
        raise
    except Exception as exc:
        raise DARTDataError(f"business report failed dart_code={dart_code}") from exc


def fetch_financial_statements(dart: ODR, dart_code: str, year: int | None = None) -> list[dict]:
    """최근 연도 재무제표를 수집하고 핵심 계정으로 정규화해 반환합니다."""
    year = year or (datetime.now().year - 1)
    try:
        df = dart.finstate(dart_code, year, reprt_code="11011")  # 11011: 사업보고서
        return normalize_financial_statements(df, fs_year=year)
    except Exception as exc:
        raise DARTDataError(f"financial statements failed dart_code={dart_code} year={year}") from exc
