"""뉴스 기사 메타데이터 추출 모듈.

poc.ipynb의 "메타데이터 추출" 및 "코스피 종목 기준으로 2차 정제" 셀을
함수화했습니다. OpenAI API로 기사별 primary_sector/sector/company/keyword를
추출하고, 후처리 단계에서 섹터 값과 기업명을 보정합니다.
"""

import json
import logging
import time
from typing import Any

import pandas as pd
from openai import OpenAI

from apps.src.config.pipeline_config import DEFAULT_METADATA_MODEL, SECTOR_LIST
from apps.src.services.preprocessor.news_preprocessor import normalize_news_columns
from apps.src.services.utils import coerce_list, dedupe_strings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
당신은 한국어 경제·금융 뉴스 기사 분류기입니다.

하나의 뉴스 기사 제목과 본문을 읽고 아래 정보를 추출하세요.

1. primary_sector
- 기사의 가장 중심 섹터 하나를 선택합니다.
- 반드시 SECTOR_LIST 중 하나만 선택합니다.

2. sector
- 기사와 직접 관련 있는 섹터를 최대 3개까지 선택합니다.
- 반드시 SECTOR_LIST 안에서만 선택합니다.
- primary_sector는 sector에 반드시 포함합니다.
- 단순 언급, 예시성 언급, 비교를 위한 언급은 제외합니다.
- 기사의 핵심 이슈와 직접 관련된 섹터만 선택합니다.

3. company
- 기사 제목 또는 본문에 명시적으로 언급된 기업명만 추출합니다.
- 직접 언급되지 않은 기업은 추측하지 않습니다.
- 가능하면 국내 상장사 종목명 형태를 우선해서 추출합니다.
- 기사에 등장한 표현이 약칭이면, 널리 쓰이는 정식 종목명으로 정규화할 수 있습니다.
  예: 하이닉스 → SK하이닉스, LG엔솔 → LG에너지솔루션, 포스코홀딩스 → POSCO홀딩스
- 해외 기업, 비상장 기업, ETF명, 펀드명, 지수명, 정부기관명, 연구기관명, 국가명은 제외하세요.
- 증권사, 운용사, 은행, 보험사가 분석 주체나 판매사로만 언급된 경우는 제외하세요.
- 다만 해당 금융회사가 뉴스의 핵심 대상이면 company에 포함할 수 있습니다.
- 최대 10개까지 반환합니다.

4. keyword
- 뉴스의 핵심 이슈 키워드를 최대 10개까지 추출합니다.
- 뉴스 클러스터링과 해설 생성에 사용할 수 있도록 구체적인 표현을 사용합니다.

출력 규칙:
- 반드시 유효한 JSON만 반환하세요.
- 설명, 해설, 마크다운, 코드블록은 포함하지 마세요.
- 새로운 섹터명을 만들지 마세요.
- primary_sector와 sector는 반드시 SECTOR_LIST 중 하나여야 합니다.
- company에는 ETF명, 펀드명, 지수명, 기관명, 정부기관명, 국가명을 넣지 마세요.
- 배열 값은 중복 없이 반환하세요.
- 관련 항목이 없으면 빈 배열 []로 반환하세요.
""".strip()


def build_metadata_prompt(title: str, body: str, max_body_chars: int = 1500) -> str:
    """단일 기사 입력 프롬프트를 만듭니다.

    비용과 토큰 사용량을 줄이기 위해 본문은 앞부분 max_body_chars까지만 사용합니다.
    """
    body_short = body[:max_body_chars] if isinstance(body, str) else ""
    return f"""
SECTOR_LIST:
{json.dumps(SECTOR_LIST, ensure_ascii=False, indent=2)}

섹터 기준:
- 반도체: HBM, D램, 낸드, 파운드리, 반도체 장비, 반도체 공급망
- AI·소프트웨어: AI, 클라우드, 데이터센터, SaaS, 빅테크, 소프트웨어
- 2차전지·전기차: 배터리, 전기차, 양극재, 음극재, ESS
- 자동차·모빌리티: 완성차, 자동차 부품, 자율주행, 차량 소프트웨어
- 조선·방산·우주항공: 조선, LNG선, 방산, 항공우주, 위성, 로켓
- 바이오·헬스케어: 제약, 바이오, 신약, 임상, 의료기기
- 전력·에너지: 전력기기, 변압기, 전선, 전력망, 원전, 정유, 가스
- 소재·화학·철강: 철강, 화학, 석유화학, 비철금속, 원자재
- 건설·인프라·부동산: 건설, 플랜트, 인프라, 주택, 리츠, 부동산
- 금융·증권·보험: 은행, 증권, 보험, ETF, 펀드, 연금, 금리, 자본시장
- 소비재·유통: 음식료, 화장품, 패션, 유통, 면세, 생활소비재
- 미디어·엔터·게임: 콘텐츠, 엔터테인먼트, 게임, 웹툰, 광고, 방송

반환 형식:
{{
  "primary_sector": "",
  "sector": [],
  "company": [],
  "keyword": []
}}

뉴스 기사:

제목:
{title or ""}

본문:
{body_short}
""".strip()


def normalize_metadata_result(result: dict[str, Any]) -> dict[str, Any]:
    """모델 응답을 파이프라인에서 기대하는 스키마로 보정합니다.

    모델이 잘못된 섹터명을 만들거나 리스트가 아닌 값을 반환해도, 이후 단계가
    깨지지 않도록 기본값/중복 제거/개수 제한을 적용합니다.
    """
    primary_sector = result.get("primary_sector", "")
    sectors = result.get("sector", result.get("sectors", []))
    companies = result.get("company", result.get("companies", []))
    keywords = result.get("keyword", result.get("keywords", []))

    sectors = sectors if isinstance(sectors, list) else []
    companies = companies if isinstance(companies, list) else []
    keywords = keywords if isinstance(keywords, list) else []

    sectors = [sector for sector in sectors if sector in SECTOR_LIST]
    if primary_sector not in SECTOR_LIST:
        primary_sector = sectors[0] if sectors else "금융·증권·보험"
    if primary_sector not in sectors:
        sectors = [primary_sector] + sectors

    return {
        "primary_sector": primary_sector,
        "sector": list(dict.fromkeys(sectors))[:3],
        "company": dedupe_strings(companies, limit=10),
        "keyword": dedupe_strings(keywords, limit=10),
    }


def extract_news_metadata_with_llm(
    title: str,
    body: str,
    client: OpenAI | None = None,
    model: str = DEFAULT_METADATA_MODEL,
    max_body_chars: int = 1500,
) -> dict[str, Any]:
    """기사 하나에서 primary_sector/sector/company/keyword를 추출합니다."""
    client = client or OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_metadata_prompt(title, body, max_body_chars)},
        ],
        text={"format": {"type": "json_object"}},
    )
    return normalize_metadata_result(json.loads(response.output_text))


def extract_metadata_from_news(
    articles_df: pd.DataFrame,
    client: OpenAI | None = None,
    model: str = DEFAULT_METADATA_MODEL,
    sleep_sec: float = 0.2,
) -> pd.DataFrame:
    """여러 기사 DataFrame에 대해 메타데이터 추출을 반복 실행합니다.

    실패한 기사는 error 컬럼에 예외 메시지를 남기고 빈 메타데이터로 계속 진행합니다.
    """
    client = client or OpenAI()
    rows = []
    articles_df = normalize_news_columns(articles_df)
    total = len(articles_df)
    logger.info("[metadata] start rows=%s model=%s sleep_sec=%s", total, model, sleep_sec)

    for idx, row in articles_df.reset_index(drop=True).iterrows():
        title = row.get("news_title", "")
        body = row.get("news_content", "")
        url = row.get("news_url")
        news_id = row.get("news_id")
        logger.info("[metadata] extracting %s/%s title=%s", idx + 1, total, str(title)[:80])

        try:
            metadata = extract_news_metadata_with_llm(
                title=title,
                body=body,
                client=client,
                model=model,
            )
            rows.append({
                "idx": idx,
                "news_id": news_id,
                "news_title": title,
                "news_content": body,
                "news_url": url,
                **metadata,
                "error": None,
            })
        except Exception as exc:
            rows.append({
                "idx": idx,
                "news_id": news_id,
                "news_title": title,
                "news_content": body,
                "news_url": url,
                "primary_sector": None,
                "sector": [],
                "company": [],
                "keyword": [],
                "error": str(exc),
            })
            logger.exception("[metadata] failed %s/%s title=%s", idx + 1, total, str(title)[:80])

        if (idx + 1) % 10 == 0 or idx + 1 == total:
            errors = sum(1 for row in rows if row.get("error"))
            logger.info("[metadata] progress %s/%s errors=%s", idx + 1, total, errors)

        time.sleep(sleep_sec)

    logger.info("[metadata] done rows=%s", len(rows))
    return pd.DataFrame(rows)


def coerce_list_columns(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """지정한 컬럼의 list-like 값을 Python list로 보정합니다."""
    out = df.copy()
    columns = columns or ["sector", "company", "keyword"]
    for col in columns:
        if col in out.columns:
            out[col] = out[col].apply(coerce_list)
    return out


normalize_metadata = normalize_metadata_result
extract_news_metadata = extract_news_metadata_with_llm
extract_metadata_from_articles = extract_metadata_from_news
