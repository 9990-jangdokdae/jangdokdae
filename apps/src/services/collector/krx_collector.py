"""pyKRX market data collection."""

import logging
from datetime import datetime, timedelta
from typing import Any

from apps.src.services.utils import dataframe_to_records, retry_call
from apps.src.services.collector.company_master_collector import fetch_krx_master, login_krx

logger = logging.getLogger(__name__)


def fetch_stock_market_data(
    krx_code: str,
    start_date: str,
    end_date: str,
    login: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """KRX 종목코드 기준으로 OHLCV와 투자자별 거래량을 조회합니다."""
    from pykrx import stock

    if login:
        login_krx()

    start_date = start_date.replace("-", "")
    end_date = end_date.replace("-", "")
    logger.info("[krx] ohlcv/trading krx_code=%s start=%s end=%s", krx_code, start_date, end_date)
    ohlcv = retry_call(stock.get_market_ohlcv, start_date, end_date, krx_code)
    trading_volume = retry_call(
        stock.get_market_trading_volume_by_date,
        start_date,
        end_date,
        krx_code,
    )

    result = {
        "ohlcv": dataframe_to_records(ohlcv.reset_index()),
        "trading_volume_by_investor": dataframe_to_records(trading_volume.reset_index()),
    }
    logger.info(
        "[krx] done krx_code=%s ohlcv_rows=%s trading_rows=%s",
        krx_code,
        len(result["ohlcv"]),
        len(result["trading_volume_by_investor"]),
    )
    return result


def fetch_stock_ohlcv(krx_code: str, start_date: str, end_date: str):
    """KRX 종목 OHLCV raw DataFrame을 조회합니다."""
    from pykrx import stock

    return retry_call(
        stock.get_market_ohlcv,
        start_date.replace("-", ""),
        end_date.replace("-", ""),
        krx_code,
    )


def fetch_trading_volume_by_investor(krx_code: str, start_date: str, end_date: str, login: bool = True):
    """KRX 종목 투자자별 거래량 raw DataFrame을 조회합니다."""
    from pykrx import stock

    if login:
        login_krx()

    return retry_call(
        stock.get_market_trading_volume_by_date,
        start_date.replace("-", ""),
        end_date.replace("-", ""),
        krx_code,
    )


def fetch_recent_stock_market_data(
    krx_code: str,
    days: int = 5,
    end_date: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """종료일 기준 최근 N일의 KRX 시장 데이터를 조회합니다."""
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    start = end - timedelta(days=days)
    return fetch_stock_market_data(
        krx_code=krx_code,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
    )
