"""기업 데이터 전처리 모듈."""

import logging

from apps.src.utils.date_utils import compact_to_iso_date

logger = logging.getLogger(__name__)

_OHLCV_RENAME = {
    "시가": "open",
    "고가": "high",
    "저가": "low",
    "종가": "close",
    "거래량": "volume",
    "등락률": "change_rate",
}


class CompanyPreprocessor:
    """CompanyCollector가 수집한 기업 데이터를 정제합니다.

    수행 작업:
    - OHLCV 컬럼명 영문화 (시가→open 등)
    - 공시 날짜 형식 통일 (20260511 → 2026-05-11)

    재무제표 정규화는 dart_preprocessor.normalize_financial_statements에서 수집 시 처리됨.
    """

    def preprocess(self, clusters: list[dict]) -> list[dict]:
        """클러스터 목록의 모든 기업 데이터를 정제하고 반환합니다."""
        for cluster in clusters:
            cluster["company_data"] = [
                self._process(co) for co in cluster.get("company_data", [])
            ]
        logger.info("[preprocess_company] done clusters=%d", len(clusters))
        return clusters

    def _process(self, co: dict) -> dict:
        """단일 기업 dict의 OHLCV 컬럼명과 공시 날짜를 정규화합니다."""
        if not co.get("matched", False):
            return co

        market = co.get("market", {})
        if market.get("ohlcv"):
            market["ohlcv"] = [self._rename_ohlcv(row) for row in market["ohlcv"]]

        dart = co.get("dart", {})
        if dart.get("disclosures"):
            dart["disclosures"] = [self._normalize_disclosure(d) for d in dart["disclosures"]]

        return co

    def _rename_ohlcv(self, row: dict) -> dict:
        """OHLCV 한글 컬럼명을 영문으로 변환합니다."""
        return {_OHLCV_RENAME.get(k, k): v for k, v in row.items()}

    def _normalize_disclosure(self, d: dict) -> dict:
        """공시 접수일(rcept_dt)을 YYYYMMDD에서 YYYY-MM-DD 형식으로 변환합니다."""
        d["rcept_dt"] = compact_to_iso_date(d.get("rcept_dt"))
        return d
