"""DART raw data collection.

OpenDartReader client 생성, 공시 목록 조회, 사업보고서 XML 원문 조회,
재무제표 raw 조회만 담당합니다.
"""

import logging
import os
from datetime import datetime
from typing import Any

from apps.src.services.utils import retry_call

logger = logging.getLogger(__name__)


def create_dart_client(api_key: str | None = None):
    """OpenDartReader 클라이언트를 생성합니다.

    OpenDartReader가 설치되지 않은 환경에서도 다른 모듈 import가 가능하도록,
    실제 라이브러리 import는 이 함수 호출 시점에만 수행합니다.
    """
    import OpenDartReader

    api_key = api_key or os.environ["OPENDART_API_KEY"]
    logger.info("[dart] creating OpenDartReader client")
    return OpenDartReader(api_key)


def find_latest_business_report(
    dart,
    dart_code: str,
    start_date: str = "2026-01-01",
    end_date: str | None = None,
) -> dict[str, Any] | None:
    """조회 기간 내 최신 사업보고서 접수 정보를 찾습니다.

    우선 report_nm에 '사업보고서'가 포함된 문서를 고르고, 없으면 가장 최신 정기공시
    문서를 fallback으로 사용합니다.
    """
    end_date = end_date or datetime.now().strftime("%Y-%m-%d")
    logger.info("[dart] list dart_code=%s start=%s end=%s kind=A", dart_code, start_date, end_date)
    docs = retry_call(dart.list, dart_code, start=start_date, end=end_date, kind="A")

    if docs is None or len(docs) == 0:
        logger.info("[dart] no reports dart_code=%s", dart_code)
        return None

    candidates = docs[docs["report_nm"].str.contains("사업보고서", na=False)]
    if candidates.empty:
        candidates = docs

    doc = candidates.sort_values("rcept_dt", ascending=False).iloc[0]
    logger.info("[dart] selected report dart_code=%s report_nm=%s rcept_no=%s", dart_code, doc.get("report_nm"), doc.get("rcept_no"))
    return doc.to_dict()


def fetch_dart_document_xml(
    dart,
    rcept_no: str,
) -> dict[str, Any]:
    """DART 문서 XML 원문을 조회합니다."""
    logger.info("[dart] document rcept_no=%s", rcept_no)
    try:
        xml_text = retry_call(dart.document, rcept_no)
    except Exception as exc:
        logger.warning("[dart] document failed rcept_no=%s error=%s", rcept_no, exc)
        return {
            "rcept_no": rcept_no,
            "xml_text": None,
            "error": str(exc),
        }
    return {"rcept_no": rcept_no, "xml_text": xml_text, "error": None}


def fetch_raw_financial_statements(
    dart,
    dart_code: str,
    year: int = 2025,
    reprt_code: str = "11011",
) -> dict[str, Any]:
    """DART 재무제표 raw DataFrame을 조회합니다."""
    logger.info("[dart] finstate dart_code=%s year=%s reprt_code=%s", dart_code, year, reprt_code)
    try:
        fs = retry_call(dart.finstate, dart_code, year, reprt_code=reprt_code)
    except Exception as exc:
        logger.warning(
            "[dart] finstate failed dart_code=%s year=%s reprt_code=%s error=%s",
            dart_code,
            year,
            reprt_code,
            exc,
        )
        return {"data": None, "error": str(exc)}
    if fs is None or len(fs) == 0:
        logger.info("[dart] no finstate dart_code=%s year=%s", dart_code, year)
        return {"data": None, "error": None}
    return {"data": fs, "error": None}
