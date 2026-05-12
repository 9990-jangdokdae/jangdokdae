"""Yahoo Finance 거시지표 ticker 매핑. 지표 추가·수정 시 이 파일만 편집합니다."""

MACRO_TICKERS: dict[str, str] = {
    "USD_KRW": "KRW=X",
    "WTI_OIL": "CL=F",
    "BRENT_OIL": "BZ=F",
    "GOLD": "GC=F",
    "COPPER": "HG=F",
    "SNP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "VIX": "^VIX",
    "US_10Y_YIELD": "^TNX",
    "DOLLAR_INDEX": "DX-Y.NYB",
}
