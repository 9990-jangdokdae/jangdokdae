"""Yahoo Finance 거시지표 수집 모듈."""

import logging
from typing import Any

import pandas as pd

from apps.src.config.macro_tickers import MACRO_TICKERS
from apps.src.exceptions.collector_exceptions import MacroDataError
from apps.src.utils.json_utils import dataframe_to_records

logger = logging.getLogger(__name__)


def fetch_macro_data(
    period: str = "7d",
    interval: str = "1d",
    tickers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Yahoo Finance에서 주요 거시지표 종가를 wide records 형태로 조회합니다.

    Args:
        period: 조회 기간 (예: "7d", "1mo").
        interval: 봉 단위 (예: "1d").
        tickers: ticker 매핑. None이면 MACRO_TICKERS 사용.

    Returns:
        날짜별 거시지표 종가 dict 목록.
    """
    import yfinance as yf

    tickers = tickers or MACRO_TICKERS
    logger.info("[macro] download period=%s interval=%s tickers=%d", period, interval, len(tickers))

    raw = yf.download(
        tickers=list(tickers.values()),
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
    )

    level1 = set(raw.columns.get_level_values(1)) if hasattr(raw.columns, "levels") else set()
    cols: dict[str, Any] = {}
    for name, ticker in tickers.items():
        try:
            if ticker in level1:
                cols[name] = raw["Close"][ticker]
            elif "Close" in raw.columns:
                cols[name] = raw["Close"]
        except Exception as exc:
            err = MacroDataError(str(exc), ticker=ticker, indicator_name=name)
            logger.warning("[macro] failed %s", err)
    close_df = pd.DataFrame(cols)

    result = dataframe_to_records(close_df.reset_index())
    logger.info("[macro] done rows=%d columns=%d", len(result), len(close_df.columns))
    return result
