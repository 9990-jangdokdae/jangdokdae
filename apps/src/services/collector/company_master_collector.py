"""DART 기업 마스터 생성 모듈.

DART corp_code.xml에서 stock_code(KRX 종목코드)가 있는 상장 기업만 추출해
dart_code / dart_name / krx_code 매핑 테이블을 만든다.
결과는 data/company_master.json에 캐시(TTL 24시간)된다.
"""

import logging
import os
from datetime import datetime, timedelta
import OpenDartReader as ODR
import pandas as pd
import requests

from apps.src.utils.json_utils import dataframe_to_records, save_json

logger = logging.getLogger(__name__)

from apps.src.config.paths import DATA_DIR

_CACHE_PATH = DATA_DIR / "company_master.json"
_CACHE_TTL_HOURS = 24

_session = requests.Session()


def login_krx(login_id: str | None = None, login_pw: str | None = None) -> bool:
    """KRX data.krx.co.kr에 로그인하고 세션을 공유합니다.

    로그인 성공 시 pykrx의 투자자별 거래량 등 인증 필요 API를 사용할 수 있습니다.
    """
    login_id = login_id or os.getenv("KRX_ID")
    # pykrx 내부가 KRX_PW를 요구하므로 KRX_PASSWORD → KRX_PW 매핑
    if "KRX_PW" not in os.environ and "KRX_PASSWORD" in os.environ:
        os.environ["KRX_PW"] = os.environ["KRX_PASSWORD"]
    login_pw = login_pw or os.getenv("KRX_PW") or os.getenv("KRX_PASSWORD")
    if not (login_id and login_pw):
        logger.warning("[krx-master] KRX_ID/KRX_PASSWORD 미설정 — 로그인 건너뜀")
        return False

    _patch_pykrx_session()

    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    login_page = "https://data.krx.co.kr/contents/MDC/STAT/standard/MDCSTAT00001.cmd"
    login_jsp = "https://data.krx.co.kr/comm/bldAttendant/getFlashWithData.cmd"
    login_url = "https://data.krx.co.kr/comm/bldAttendant/executeLogin.cmd"

    _session.get(login_page, headers={"User-Agent": user_agent}, timeout=15)
    _session.get(login_jsp, headers={"User-Agent": user_agent, "Referer": login_page}, timeout=15)

    payload = {"userId": login_id, "userPwd": login_pw, "screenId": "MDCSTAT00001"}
    headers = {"User-Agent": user_agent, "Referer": login_page, "Content-Type": "application/x-www-form-urlencoded"}

    def _error_code(r: requests.Response) -> str:
        """응답 JSON에서 _error_code 값을 추출합니다. JSON이 아니면 빈 문자열을 반환합니다."""
        data = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {}
        return data.get("_error_code", "")

    resp = _session.post(login_url, data=payload, headers=headers, timeout=15)
    error_code = _error_code(resp)

    if error_code == "CD011":
        payload["skipDup"] = "Y"
        resp = _session.post(login_url, data=payload, headers=headers, timeout=15)
        error_code = _error_code(resp)

    if error_code:
        logger.warning("[krx-master] 로그인 실패 error_code=%s", error_code)
        return False

    logger.info("[krx-master] 로그인 성공")
    return True


def _patch_pykrx_session() -> None:
    """pykrx 내부 HTTP 클라이언트가 공유 세션을 사용하도록 패치합니다."""
    try:
        from pykrx.website import krx as webio

        def _post(self, **params):
            """공유 세션으로 POST 요청을 보내고 응답 텍스트를 반환합니다."""
            return _session.post(self.url, headers=self.headers, data=params, timeout=15).text

        def _get(self, **params):
            """공유 세션으로 GET 요청을 보내고 응답 텍스트를 반환합니다."""
            return _session.get(self.url, headers=self.headers, params=params, timeout=15).text

        webio.Post.read = _post
        webio.Get.read = _get
    except Exception as exc:
        logger.warning("[krx-master] pykrx 세션 패치 실패: %s", exc)


class CompanyMasterCollector:
    """DART·KRX 기업 마스터를 빌드하고 캐시합니다."""

    def load(self) -> pd.DataFrame:
        """캐시가 유효하면 로드, 만료됐으면 갱신 후 반환."""
        if self._is_cache_valid():
            logger.info("[master] loading from cache path=%s", _CACHE_PATH)
            df = pd.read_json(_CACHE_PATH, encoding="utf-8", dtype=str)
            return df

        logger.info("[master] cache expired or missing — rebuilding")
        df = self._build()
        save_json(dataframe_to_records(df), _CACHE_PATH)
        logger.info("[master] saved to cache rows=%d", len(df))
        return df

    def _is_cache_valid(self) -> bool:
        """캐시 파일이 존재하고 TTL(24시간) 이내인지 확인합니다."""
        if not _CACHE_PATH.exists():
            return False
        mtime = datetime.fromtimestamp(_CACHE_PATH.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=_CACHE_TTL_HOURS)

    def _build(self) -> pd.DataFrame:
        """DART corp_code.xml에서 상장 기업만 추출해 dart_code/dart_name/krx_code 매핑 DataFrame을 생성합니다."""
        dart = ODR(os.environ["OPENDART_API_KEY"])

        logger.info("[master] fetching DART corp_code.xml")
        df = dart.corp_codes
        master = (
            df.rename(columns={"corp_code": "dart_code", "corp_name": "dart_name", "stock_code": "krx_code"})
            [["dart_code", "dart_name", "krx_code"]]
            .pipe(lambda d: d[d["krx_code"].notna() & (d["krx_code"].str.strip() != "")])
            .reset_index(drop=True)
        )
        logger.info("[master] listed companies=%d", len(master))
        return master
