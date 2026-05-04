"""DART/KRX 기업 마스터 생성 모듈.

`script/dart.ipynb`, `script/krx.ipynb`, `script/krx_util.py`에 있던 기업코드 수집
흐름을 파이프라인용 함수로 옮긴 파일입니다.

생성되는 주요 산출물:
- dart_master: DART corp_code.xml에서 만든 dart_code/dart_name/krx_code 매핑
- krx_master: pykrx에서 조회한 KOSPI 종목코드/종목명
- kospi_master: DART와 KRX를 krx_code 기준으로 결합한 최종 기업 마스터
"""

import logging
import os
from datetime import datetime

# pykrx custom module requires KRX_PW, but the environment uses KRX_PASSWORD
if "KRX_PW" not in os.environ and "KRX_PASSWORD" in os.environ:
    os.environ["KRX_PW"] = os.environ["KRX_PASSWORD"]
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as elemTree

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_session = requests.Session()


def patch_pykrx_session() -> None:
    """pykrx 내부 webio가 공유 requests.Session을 쓰도록 패치합니다."""
    from pykrx.website.comm import webio

    def _session_post_read(self, **params):
        resp = _session.post(self.url, headers=self.headers, data=params, timeout=15)
        return resp

    def _session_get_read(self, **params):
        resp = _session.get(self.url, headers=self.headers, params=params, timeout=15)
        return resp

    webio.Post.read = _session_post_read
    webio.Get.read = _session_get_read


def login_krx(login_id: str | None = None, login_pw: str | None = None) -> bool:
    """KRX data.krx.co.kr에 로그인하고 공유 세션 쿠키를 갱신합니다."""
    login_id = login_id or os.getenv("KRX_ID")
    login_pw = login_pw or os.getenv("KRX_PASSWORD")
    if not login_id or not login_pw:
        logger.warning("[krx-master] KRX_ID/KRX_PASSWORD or KRX_PW not set; skip login")
        return False

    patch_pykrx_session()

    login_page = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001.cmd"
    login_jsp = "https://data.krx.co.kr/contents/MDC/COMS/client/view/login.jsp?site=mdc"
    login_url = "https://data.krx.co.kr/contents/MDC/COMS/client/MDCCOMS001D1.cmd"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    _session.get(login_page, headers={"User-Agent": user_agent}, timeout=15)
    _session.get(login_jsp, headers={"User-Agent": user_agent, "Referer": login_page}, timeout=15)

    payload = {
        "mbrNm": "",
        "telNo": "",
        "di": "",
        "certType": "",
        "mbrId": login_id,
        "pw": login_pw,
    }
    headers = {"User-Agent": user_agent, "Referer": login_page}

    resp = _session.post(login_url, data=payload, headers=headers, timeout=15)
    try:
        data = resp.json()
    except ValueError:
        logger.error("[krx-master] login response not JSON status=%s body=%s", resp.status_code, resp.text[:1000])
        return False
    error_code = data.get("_error_code", "")

    if error_code == "CD011":
        payload["skipDup"] = "Y"
        resp = _session.post(login_url, data=payload, headers=headers, timeout=15)
        try:
            data = resp.json()
        except ValueError:
            logger.error("[krx-master] login (skipDup) response not JSON status=%s body=%s", resp.status_code, resp.text[:1000])
            return False
        error_code = data.get("_error_code", "")

    ok = error_code == "CD001"
    logger.info("[krx-master] login result=%s error_code=%s", ok, error_code)
    return ok


def fetch_krx_master(
    market: str = "KOSPI",
    date: str | None = None,
    login: bool = True,
) -> pd.DataFrame:
    """pykrx로 KRX 종목 마스터를 조회합니다."""
    from pykrx import stock

    query_date = date or datetime.today().strftime("%Y%m%d")
    query_date = query_date.replace("-", "")
    logger.info("[krx-master] fetching market=%s date=%s", market, query_date)

    krx = pd.DataFrame({
        "krx_code": stock.get_market_ticker_list(query_date, market=market),
    })
    krx["market"] = market
    krx["krx_name"] = krx["krx_code"].map(stock.get_market_ticker_name)
    logger.info("[krx-master] fetched rows=%s market=%s", len(krx), market)
    return krx


def fetch_dart_master(api_key: str | None = None, extract_dir: str | Path | None = None) -> pd.DataFrame:
    """OpenDART corpCode.xml을 내려받아 DART 기업 마스터를 만듭니다."""
    api_key = api_key or os.environ["OPENDART_API_KEY"]
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={api_key}"
    logger.info("[dart-master] downloading corpCode.xml")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    zip_data = ZipFile(BytesIO(resp.content))
    xml_bytes = zip_data.read("CORPCODE.xml")

    if extract_dir:
        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)
        zip_data.extractall(extract_path)
        logger.info("[dart-master] extracted corpCode zip to %s", extract_path)

    root = elemTree.fromstring(xml_bytes)
    rows = [
        {
            "dart_code": item.findtext("corp_code"),
            "dart_name": item.findtext("corp_name"),
            "krx_code": item.findtext("stock_code"),
        }
        for item in root.findall("list")
    ]
    dart_master = pd.DataFrame(rows)
    dart_master = dart_master[dart_master["krx_code"].fillna("").str.strip() != ""].copy()
    logger.info("[dart-master] fetched listed rows=%s", len(dart_master))
    return dart_master


def build_kospi_master(
    dart_master: pd.DataFrame,
    krx_master: pd.DataFrame,
    market: str = "KOSPI",
) -> pd.DataFrame:
    """DART 마스터와 KRX 마스터를 결합해 KOSPI 기업 마스터를 만듭니다."""
    kospi_master = dart_master.merge(krx_master, how="left", on="krx_code")
    kospi_master = kospi_master[kospi_master["market"] == market].copy()
    cols = ["dart_code", "dart_name", "krx_code", "market", "krx_name"]
    kospi_master = kospi_master[[col for col in cols if col in kospi_master.columns]]
    logger.info("[kospi-master] built rows=%s market=%s", len(kospi_master), market)
    return kospi_master


def build_and_save_company_masters(
    dart_master_path: str | Path,
    krx_master_path: str | Path,
    kospi_master_path: str | Path,
    market: str = "KOSPI",
    date: str | None = None,
    login_krx_first: bool = True,
    extract_dir: str | Path | None = None,
) -> pd.DataFrame:
    """DART/KRX/KOSPI 마스터를 모두 생성하고 pickle로 저장합니다."""
    dart_master = fetch_dart_master(extract_dir=extract_dir)
    krx_master = fetch_krx_master(market=market, date=date, login=login_krx_first)
    kospi_master = build_kospi_master(dart_master, krx_master, market=market)

    Path(dart_master_path).parent.mkdir(parents=True, exist_ok=True)
    Path(krx_master_path).parent.mkdir(parents=True, exist_ok=True)
    Path(kospi_master_path).parent.mkdir(parents=True, exist_ok=True)

    dart_master.to_pickle(dart_master_path)
    krx_master.to_pickle(krx_master_path)
    kospi_master.to_pickle(kospi_master_path)

    logger.info("[master] saved dart=%s krx=%s kospi=%s", dart_master_path, krx_master_path, kospi_master_path)
    return kospi_master
