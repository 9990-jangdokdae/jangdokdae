"""DART document and financial statement preprocessing."""

import html
import re
from typing import Any, Dict, List

import pandas as pd

from apps.src.config.pipeline_config import TARGET_ACCOUNTS
from apps.src.services.utils import dataframe_to_records

TARGET_MAJOR_TITLES = {
    "II. 사업의 내용": "business",
    "IV. 이사의 경영진단 및 분석의견": "director_analysis",
    "V. 회계감사인의 감사의견 등": "audit_opinion",
}

def extract_major_titles(xml_text: str) -> List[Dict[str, int | str]]:
    """
    로마숫자(I., II., III. ...)로 시작하는 대분류 TITLE 목록 추출
    """
    title_pattern = re.compile(r"<TITLE[^>]*>(.*?)</TITLE>", re.IGNORECASE | re.DOTALL)
    roman_heading_pattern = re.compile(r"^\s*[IVXLCDM]+\.\s+.+$", re.IGNORECASE)

    matches = list(title_pattern.finditer(xml_text))
    major_candidates = []
    for match in matches:
        title_text = re.sub(r"\s+", " ", match.group(1)).strip()
        if roman_heading_pattern.match(title_text):
            major_candidates.append({"title_text": title_text, "start": match.start()})

    major_titles = []
    for i, item in enumerate(major_candidates):
        start = int(item["start"])
        end = (
            int(major_candidates[i + 1]["start"])
            if i + 1 < len(major_candidates)
            else len(xml_text)
        )
        major_titles.append(
            {
                "title_text": str(item["title_text"]),
                "start": start,
                "end": end,
            }
        )
    return major_titles


def extract_target_major_sections(
    xml_text: str, targets: Dict[str, str] = TARGET_MAJOR_TITLES
) -> Dict[str, str]:
    """
    원하는 대분류 섹션만 XML 원문으로 추출
    """
    major_titles = extract_major_titles(xml_text)
    by_title = {m["title_text"]: xml_text[m["start"] : m["end"]] for m in major_titles}
    return {alias: by_title.get(title, "") for title, alias in targets.items()}


def _xml_to_lines(section_xml: str) -> List[str]:
    """
    XML 문자열을 줄 단위 텍스트로 정규화:
    - 문단/테이블/행 단위 종료 태그를 줄바꿈으로 치환
    - 모든 태그 제거
    - 공백 정리
    """
    text = re.sub(
        r"</(P|TR|TBODY|TABLE|SECTION-[0-9]+|TITLE)>",
        "\n",
        section_xml,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<(PGBRK|BR)\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)

    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)

    lines = [ln.strip() for ln in text.split("\n")]
    return [ln for ln in lines if ln]


def _drop_common_noise(lines: List[str]) -> List[str]:
    """
    공통 노이즈 제거:
    - 참조 링크(☞ ...)
    - 상세표 안내
    - 이미지 파일명
    """
    noise_patterns = [
        r"^☞",
        r"^※\s*상세",
        r"\.jpg$|\.png$|\.jpeg$",
        r"^본문 위치로 이동$",
    ]
    compiled = [re.compile(p) for p in noise_patterns]

    cleaned = []
    for line in lines:
        if any(p.search(line) for p in compiled):
            continue
        cleaned.append(line)
    return cleaned


def preprocess_business_section(section_xml: str) -> str:
    """
    II. 사업의 내용 전처리:
    - 문장형 텍스트 중심으로 정리
    - 숫자/기호만 있는 라인 제거
    """
    lines = _drop_common_noise(_xml_to_lines(section_xml))

    out = []
    for line in lines:
        if re.fullmatch(r"[\d\W_]+", line):
            continue
        if len(line) < 2:
            continue
        out.append(line)
    return "\n".join(out)


def preprocess_director_analysis_section(section_xml: str) -> str:
    """
    IV. 이사의 경영진단 및 분석의견 전처리:
    - 문장형 내용 최대 보존
    """
    lines = _drop_common_noise(_xml_to_lines(section_xml))

    out = []
    for line in lines:
        line = re.sub(r"\s{2,}", " ", line).strip()
        if len(line) < 2:
            continue
        out.append(line)
    return "\n".join(out)


def preprocess_audit_opinion_section(section_xml: str) -> str:
    """
    V. 회계감사인의 감사의견 등 전처리:
    - 감사 관련 키워드 중심으로 선별
    - 선별 결과가 너무 적으면 전체 라인 반환
    """
    lines = _drop_common_noise(_xml_to_lines(section_xml))

    keep_kw = re.compile(
        r"감사의견|회계법인|감사인|적정|한정|부적정|의견거절|내부회계|검토결론|감사대상|감사기간|지정감사"
    )
    selected = [line for line in lines if keep_kw.search(line)]

    if len(selected) < 20:
        selected = lines
    return "\n".join(selected)


def preprocess_dart_sections(xml_text: str, targets: Dict[str, str] = TARGET_MAJOR_TITLES) -> Dict[str, str]:
    """
    전체 XML에서 지정한 3개 대분류를 추출 + 섹션별 전처리 수행
    """
    sections = extract_target_major_sections(xml_text)
    return {
        "II_business": preprocess_business_section(sections["business"]),
        "IV_director_analysis": preprocess_director_analysis_section(
            sections["director_analysis"]
        ),
        "V_audit_opinion": preprocess_audit_opinion_section(sections["audit_opinion"]),
    }


def _clean_amount(value: Any) -> float | None:
    """DART 금액 문자열의 쉼표/괄호/결측값을 숫자로 변환합니다."""
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    if text in {"", "-", "nan"}:
        return None
    text = text.replace("(", "-").replace(")", "")
    return pd.to_numeric(text, errors="coerce")


def normalize_financial_statements(
    raw_financial_statements: pd.DataFrame | None,
    fs_year: int = 2025,
    target_accounts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """DART 재무제표 wide format을 주요 계정 중심 long records로 변환합니다."""
    if raw_financial_statements is None or raw_financial_statements.empty:
        return []

    target_accounts = target_accounts or TARGET_ACCOUNTS
    fs = raw_financial_statements.copy()
    cols = [
        "corp_code",
        "stock_code",
        "fs_div",
        "fs_nm",
        "sj_div",
        "sj_nm",
        "account_id",
        "account_nm",
        "thstrm_nm",
        "thstrm_amount",
        "frmtrm_nm",
        "frmtrm_amount",
        "bfefrmtrm_nm",
        "bfefrmtrm_amount",
    ]
    fs = fs[[col for col in cols if col in fs.columns]].copy()
    if "account_nm" in fs.columns:
        fs = fs[fs["account_nm"].isin(target_accounts)]

    period_specs = [
        ("당기", "thstrm_nm", "thstrm_amount"),
        ("전기", "frmtrm_nm", "frmtrm_amount"),
        ("전전기", "bfefrmtrm_nm", "bfefrmtrm_amount"),
    ]
    period_year_map = {
        "당기": fs_year,
        "전기": fs_year - 1,
        "전전기": fs_year - 2,
    }

    records = []
    for _, row in fs.iterrows():
        base = {
            "corp_code": row.get("corp_code"),
            "stock_code": row.get("stock_code"),
            "fs_div": row.get("fs_div"),
            "fs_nm": row.get("fs_nm"),
            "sj_div": row.get("sj_div"),
            "sj_nm": row.get("sj_nm"),
            "account_id": row.get("account_id"),
            "account_nm": row.get("account_nm"),
        }

        for period_type, period_col, amount_col in period_specs:
            if amount_col not in fs.columns:
                continue
            amount = _clean_amount(row.get(amount_col))
            if amount is None or pd.isna(amount):
                continue

            records.append({
                **base,
                "period_type": period_type,
                "period_name": row.get(period_col),
                "year": period_year_map[period_type],
                "amount": float(amount),
                "currency": "KRW",
            })

    return dataframe_to_records(pd.DataFrame(records))


preprocess_target_sections = preprocess_dart_sections
preprocess_business = preprocess_business_section
preprocess_director_analysis = preprocess_director_analysis_section
preprocess_audit_opinion = preprocess_audit_opinion_section
