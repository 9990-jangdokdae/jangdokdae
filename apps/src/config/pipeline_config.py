"""POC 파이프라인 전역 설정값.

경로, 기본 모델명, 섹터 taxonomy, DART 재무제표 대상 계정, 거시지표 ticker를 한곳에
모아 단계별 모듈이 같은 기준을 쓰도록 합니다.
"""

from pathlib import Path


# PROJECT_ROOT는 이 파일(apps/src/config/pipeline_config.py) 기준 repo root입니다.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = PROJECT_ROOT / "apps"
DATA_DIR = APP_DIR / "data"

# 노트북 POC에서 사용하던 기본 수집일입니다. 운영에서는 CLI 인자로 바꿔 실행할 수 있습니다.
DEFAULT_NEWS_DATE = "2026-04-28"
DEFAULT_PAGE_LIMIT = 20

# OpenAI API 기본 모델명입니다. CLI 옵션으로 교체 가능합니다.
DEFAULT_METADATA_MODEL = "gpt-5.4-nano"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# 파이프라인 단계별 기본 입출력 파일입니다.
NEWS_ARTICLES_PATH = DATA_DIR / "news_articles.pkl"
NEWS_WITH_METADATA_PATH = DATA_DIR / "news_with_metadata.pkl"
NEWS_METADATA_KOSPI_PATH = DATA_DIR / "news_metadata_kospi.pkl"
DART_MASTER_PATH = DATA_DIR / "dart_master.pkl"
KRX_MASTER_PATH = DATA_DIR / "krx_master.pkl"
KOSPI_MASTER_PATH = DATA_DIR / "kospi_master.pkl"
CLUSTER_PAYLOAD_PATH = DATA_DIR / "cluster_context_payload.pkl"


# LLM이 임의 섹터명을 만들지 않도록 고정 taxonomy로 사용합니다.
SECTOR_LIST = [
    "반도체",
    "AI·소프트웨어",
    "2차전지·전기차",
    "자동차·모빌리티",
    "조선·방산·우주항공",
    "바이오·헬스케어",
    "전력·에너지",
    "소재·화학·철강",
    "건설·인프라·부동산",
    "금융·증권·보험",
    "소비재·유통",
    "미디어·엔터·게임",
]


# DART finstate에서 최종 payload에 포함할 핵심 재무 계정입니다.
TARGET_ACCOUNTS = [
    "자산총계",
    "유동자산",
    "비유동자산",
    "부채총계",
    "유동부채",
    "비유동부채",
    "자본총계",
    "매출액",
    "영업이익",
    "당기순이익(손실)",
    "영업활동현금흐름",
    "투자활동현금흐름",
    "재무활동현금흐름",
]


# Yahoo Finance ticker 매핑입니다. 값은 각 지표의 일별 Close만 사용합니다.
MACRO_TICKERS = {
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
