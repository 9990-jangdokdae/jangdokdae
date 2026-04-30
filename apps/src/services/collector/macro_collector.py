"""Macro market context used by analysis payloads."""

import logging
from typing import Any

import pandas as pd

from apps.src.config.pipeline_config import MACRO_TICKERS
from apps.src.services.utils import dataframe_to_records

logger = logging.getLogger(__name__)


def fetch_macro_data(
    period: str = "7d",
    interval: str = "1d",
    tickers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Yahoo Finance에서 주요 거시지표 종가를 wide records 형태로 조회합니다."""
    import yfinance as yf

    tickers = tickers or MACRO_TICKERS
    logger.info("[macro] download period=%s interval=%s tickers=%s", period, interval, list(tickers.keys()))
    raw = yf.download(
        tickers=list(tickers.values()),
        period=period,
        interval=interval,
        auto_adjust=False,
        group_by="ticker",
        progress=False,
    )

    close_df = pd.DataFrame()
    for name, ticker in tickers.items():
        try:
            close_df[name] = raw[ticker]["Close"]
        except Exception as exc:
            logger.warning("[macro] failed name=%s ticker=%s error=%s", name, ticker, exc)

    result = dataframe_to_records(close_df.reset_index())
    logger.info("[macro] done rows=%s columns=%s", len(result), list(close_df.reset_index().columns))
    return result
