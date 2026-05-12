"""pyKRX 시장 데이터 수집."""

import logging
import os
from datetime import datetime, timedelta

from pykrx import stock

from apps.src.exceptions.company_exceptions import KRXDataError
from apps.src.utils.json_utils import dataframe_to_records

logger = logging.getLogger(__name__)


def _date_range(days: int, end_date: str) -> tuple[str, str]:
    """end_date 기준으로 days 거래일을 커버하는 (start, end) 날짜 문자열 쌍을 반환합니다.

    영업일 기준 days를 확보하기 위해 달력일 기준 days * 2로 넉넉히 조회 범위를 잡습니다.
    """
    end = datetime.strptime(end_date, "%Y%m%d")
    start = end - timedelta(days=days * 2)
    return start.strftime("%Y%m%d"), end_date


def _trim_and_convert(df, days: int) -> list[dict]:
    """DataFrame 꼬리 days 행만 남기고, 날짜 내림차순 정렬 후 JSON 직렬화 가능한 records로 반환합니다."""
    df = df.tail(days).sort_index(ascending=False).reset_index()
    df.columns = ["date" if c == "날짜" else c for c in df.columns]
    return dataframe_to_records(df)


def fetch_ohlcv(krx_code: str, days: int = 60, end_date: str | None = None) -> list[dict]:
    """OHLCV를 최근 days 거래일 기준으로 수집합니다. 날짜 내림차순."""
    end_date = end_date or datetime.now().strftime("%Y%m%d")
    start, end = _date_range(days, end_date)
    try:
        df = stock.get_market_ohlcv(start, end, krx_code)
        if df is None or df.empty:
            raise KRXDataError(f"OHLCV empty krx_code={krx_code}")
        return _trim_and_convert(df, days)
    except KRXDataError:
        raise
    except Exception as exc:
        raise KRXDataError(f"OHLCV fetch failed krx_code={krx_code}") from exc


def fetch_investor_trading(krx_code: str, days: int = 60, end_date: str | None = None) -> list[dict]:
    """투자자별 거래량을 최근 days 거래일 기준으로 수집합니다. 날짜 내림차순.

    KRX 로그인 자격증명이 없으면 빈 리스트를 반환합니다.
    """
    if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PASSWORD")):
        logger.debug("[krx] KRX_ID/KRX_PASSWORD 미설정 — investor_trading 수집 건너뜀")
        return []
    end_date = end_date or datetime.now().strftime("%Y%m%d")
    start, end = _date_range(days, end_date)
    try:
        df = stock.get_market_trading_volume_by_investor(start, end, krx_code)
        if df is None or df.empty:
            raise KRXDataError(f"investor trading empty krx_code={krx_code}")
        return _trim_and_convert(df, days)
    except KRXDataError:
        raise
    except Exception as exc:
        raise KRXDataError(f"investor trading fetch failed krx_code={krx_code}") from exc
