"""DART 기업 마스터 생성 모듈.

DART corp_code.xml에서 stock_code(KRX 종목코드)가 있는 상장 기업만 추출해
dart_code / dart_name / krx_code 매핑 테이블을 만든다.
결과는 data/company_master.json에 캐시(TTL 24시간)된다.
"""

import logging
from datetime import datetime, timedelta
import OpenDartReader as ODR

from apps.src.config import getenv
import pandas as pd

from apps.src.utils.json_utils import dataframe_to_records, save_json
from apps.src.services.collector.krx_collector import fetch_sector_and_market

logger = logging.getLogger(__name__)

from apps.src.config.paths import DATA_DIR

_CACHE_PATH = DATA_DIR / "company_master.json"
_CACHE_TTL_HOURS = 24


class CompanyMasterCollector:
    """DART·KRX 기업 마스터를 빌드하고 캐시합니다."""

    def load(self) -> pd.DataFrame:
        """캐시가 유효하면 로드, 만료됐으면 갱신 후 반환."""
        if self._is_cache_valid():
            df = pd.read_json(_CACHE_PATH, encoding="utf-8", dtype=str)
            return df

        df = self._build()
        save_json(dataframe_to_records(df), _CACHE_PATH)
        return df

    def _is_cache_valid(self) -> bool:
        """캐시 파일이 존재하고 TTL(24시간) 이내인지 확인합니다."""
        if not _CACHE_PATH.exists():
            return False
        mtime = datetime.fromtimestamp(_CACHE_PATH.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=_CACHE_TTL_HOURS)

    def _build(self) -> pd.DataFrame:
        """DART corp_code.xml에서 상장 기업만 추출하고 PyKRX sector/market을 병합합니다."""
        dart = ODR(getenv.OPENDART_API_KEY)

        df = dart.corp_codes
        master = (
            df.rename(columns={"corp_code": "dart_code", "corp_name": "dart_name", "stock_code": "krx_code"})
            [["dart_code", "dart_name", "krx_code"]]
            .pipe(lambda d: d[d["krx_code"].notna() & (d["krx_code"].str.strip() != "")])
            .reset_index(drop=True)
        )

        today = datetime.now().strftime("%Y%m%d")
        sector_map = fetch_sector_and_market(today)
        master["market"] = master["krx_code"].map(lambda c: sector_map.get(c, (None, None))[0])
        master["sector"] = master["krx_code"].map(lambda c: sector_map.get(c, (None, None))[1])
        return master
