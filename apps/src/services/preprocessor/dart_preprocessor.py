"""DART 사업보고서 XML 파싱 및 재무제표 정규화 모듈."""

import html
import logging
import re
from typing import Any

import pandas as pd

from apps.src.config.dart_accounts import TARGET_ACCOUNTS
from apps.src.utils.json_utils import dataframe_to_records, to_json_safe

logger = logging.getLogger(__name__)

# 추출 대상 대분류 섹션 (로마 숫자 TITLE 기준)
_TARGET_SECTIONS = {
    "II. 사업의 내용": "II_business",
    "IV. 이사의 경영진단 및 분석의견": "IV_director_analysis",
    "V. 회계감사인의 감사의견 등": "V_audit_opinion",
}

_NOISE_PATTERNS = [
    re.compile(r"^☞"),
    re.compile(r"^※\s*상세"),
    re.compile(r"\.jpg$|\.png$|\.jpeg$"),
    re.compile(r"^본문 위치로 이동$"),
]


def _extract_major_sections(xml_text: str) -> dict[str, str]:
    """로마 숫자 대분류 TITLE 기준으로 XML을 섹션별로 분리합니다."""
    title_pat = re.compile(r"<TITLE[^>]*>(.*?)</TITLE>", re.IGNORECASE | re.DOTALL)
    roman_pat = re.compile(r"^\s*[IVXLCDM]+\.\s+.+$", re.IGNORECASE)

    matches = list(title_pat.finditer(xml_text))
    candidates = []
    for m in matches:
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        if roman_pat.match(text):
            candidates.append({"title": text, "start": m.start()})

    sections: dict[str, str] = {}
    for i, item in enumerate(candidates):
        end = candidates[i + 1]["start"] if i + 1 < len(candidates) else len(xml_text)
        sections[item["title"]] = xml_text[item["start"]:end]
    return sections


def _xml_to_lines(section_xml: str) -> list[str]:
    """XML 섹션을 정제된 줄 목록으로 변환합니다."""
    text = re.sub(r"</(P|TR|TBODY|TABLE|SECTION-\d+|TITLE)>", "\n", section_xml, flags=re.IGNORECASE)
    text = re.sub(r"<(PGBRK|BR)\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[\t\r\f\v ]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _drop_noise(lines: list[str]) -> list[str]:
    """_NOISE_PATTERNS에 매칭되는 줄을 제거합니다."""
    return [ln for ln in lines if not any(p.search(ln) for p in _NOISE_PATTERNS)]


def _base_lines(xml: str) -> list[str]:
    """XML을 줄 목록으로 변환한 뒤 노이즈 줄을 제거합니다."""
    return _drop_noise(_xml_to_lines(xml))


def _preprocess_business(xml: str) -> str:
    """사업의 내용 섹션 XML에서 숫자·기호만 있는 줄을 제거하고 본문 텍스트를 반환합니다."""
    lines = _base_lines(xml)
    return "\n".join(ln for ln in lines if not re.fullmatch(r"[\d\W_]+", ln) and len(ln) >= 2)


def _preprocess_director_analysis(xml: str) -> str:
    """이사의 경영진단 섹션 XML에서 불필요한 공백을 제거하고 2자 이상 줄만 반환합니다."""
    lines = _base_lines(xml)
    return "\n".join(re.sub(r"\s{2,}", " ", ln).strip() for ln in lines if len(ln) >= 2)


def _preprocess_audit_opinion(xml: str) -> str:
    """감사의견 섹션 XML에서 감사 관련 핵심 키워드가 포함된 줄만 선별해 반환합니다."""
    lines = _base_lines(xml)
    keep_kw = re.compile(r"감사의견|회계법인|감사인|적정|한정|부적정|의견거절|내부회계|검토결론|감사기간|지정감사")
    selected = [ln for ln in lines if keep_kw.search(ln)]
    return "\n".join(selected if len(selected) >= 20 else lines)


def preprocess_dart_sections(xml_text: str) -> dict[str, str]:
    """사업보고서 XML에서 3개 대분류 섹션을 추출·정제합니다.

    Returns:
        {"II_business": ..., "IV_director_analysis": ..., "V_audit_opinion": ...}
    """
    raw_sections = _extract_major_sections(xml_text)
    result: dict[str, str] = {}

    preprocessors = {
        "II. 사업의 내용": ("II_business", _preprocess_business),
        "IV. 이사의 경영진단 및 분석의견": ("IV_director_analysis", _preprocess_director_analysis),
        "V. 회계감사인의 감사의견 등": ("V_audit_opinion", _preprocess_audit_opinion),
    }
    for title, (key, fn) in preprocessors.items():
        xml = raw_sections.get(title, "")
        result[key] = fn(xml) if xml else ""

    return result


def _clean_amount(value: Any) -> float | None:
    """DART 금액 문자열을 숫자로 변환합니다."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).replace(",", "").strip()
    if text in {"", "-", "nan"}:
        return None
    text = text.replace("(", "-").replace(")", "")
    result = pd.to_numeric(text, errors="coerce")
    return None if pd.isna(result) else float(result)


def normalize_financial_statements(
    df: pd.DataFrame | None,
    fs_year: int | None = None,
    target_accounts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """DART 재무제표를 핵심 계정 중심 long format records로 변환합니다.

    - TARGET_ACCOUNTS 기준으로 계정 필터링
    - wide(당기·전기·전전기 컬럼) → long(행) 변환
    - 금액 문자열 → float
    """
    if df is None or df.empty:
        return []

    from datetime import datetime
    fs_year = fs_year or (datetime.now().year - 1)
    target = target_accounts or TARGET_ACCOUNTS

    fs = df.copy()
    if "account_nm" in fs.columns:
        fs = fs[fs["account_nm"].isin(target)]

    period_specs = [
        ("당기", "thstrm_nm", "thstrm_amount", fs_year),
        ("전기", "frmtrm_nm", "frmtrm_amount", fs_year - 1),
        ("전전기", "bfefrmtrm_nm", "bfefrmtrm_amount", fs_year - 2),
    ]

    records = []
    for row in fs.to_dict(orient="records"):
        base = {k: to_json_safe(row.get(k)) for k in ("corp_code", "stock_code", "fs_div", "fs_nm", "sj_div", "sj_nm", "account_nm")}
        for period_type, period_col, amount_col, year in period_specs:
            if amount_col not in fs.columns:
                continue
            amount = _clean_amount(row.get(amount_col))
            if amount is None:
                continue
            records.append({**base, "period_type": period_type, "period_name": to_json_safe(row.get(period_col)), "year": year, "amount": amount, "currency": "KRW"})

    return records
