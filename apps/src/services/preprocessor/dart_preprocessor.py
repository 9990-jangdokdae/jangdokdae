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


def _extract_subsections(section_xml: str) -> list[tuple[str, str]]:
    """섹션 XML을 아라비아 숫자 소제목(TITLE 태그) 기준으로 분할합니다.

    Returns:
        [(subsection_title, xml_fragment), ...] — 소제목 없으면 [("", section_xml)]
    """
    title_pat = re.compile(r"<TITLE[^>]*>(.*?)</TITLE>", re.IGNORECASE | re.DOTALL)
    sub_pat = re.compile(r"^\s*\d+\.\s+.+$")

    matches = list(title_pat.finditer(section_xml))
    candidates = []
    for m in matches:
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        if sub_pat.match(text):
            candidates.append({"title": text, "start": m.start()})

    if not candidates:
        return [("", section_xml)]

    result = []
    for i, item in enumerate(candidates):
        end = candidates[i + 1]["start"] if i + 1 < len(candidates) else len(section_xml)
        result.append((item["title"], section_xml[item["start"]:end]))
    return result


def preprocess_dart_sections(xml_text: str) -> dict[str, list[dict]]:
    """사업보고서 XML에서 3개 대분류 섹션을 추출·정제합니다.

    Returns:
        {"II_business": [{"subsection": "1. ...", "content": "..."}, ...], ...}
        소제목이 없으면 subsection=""
    """
    raw_sections = _extract_major_sections(xml_text)
    result: dict[str, list[dict]] = {}

    preprocessors = {
        "II. 사업의 내용": ("II_business", _preprocess_business),
        "IV. 이사의 경영진단 및 분석의견": ("IV_director_analysis", _preprocess_director_analysis),
        "V. 회계감사인의 감사의견 등": ("V_audit_opinion", _preprocess_audit_opinion),
    }
    for title, (key, fn) in preprocessors.items():
        xml = raw_sections.get(title, "")
        if not xml:
            result[key] = []
            continue
        chunks = []
        for subsection, sub_xml in _extract_subsections(xml):
            content = fn(sub_xml)
            if content.strip():
                chunks.append({"subsection": subsection, "content": content})
        result[key] = chunks if chunks else []

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
        base = {k: to_json_safe(row.get(k)) for k in ("corp_code", "stock_code", "fs_div", "fs_nm", "sj_div", "sj_nm", "account_nm", "rcept_no")}
        for period_type, period_col, amount_col, year in period_specs:
            if amount_col not in fs.columns:
                continue
            amount = _clean_amount(row.get(amount_col))
            if amount is None:
                continue
            records.append({**base, "period_type": period_type, "period_name": to_json_safe(row.get(period_col)), "year": year, "amount": amount, "currency": "KRW"})

    return records


# 한글 계정명 → dart_financial_statements 컬럼명 매핑
_ACCOUNT_TO_COL: dict[str, str] = {
    "매출액":                          "revenue",
    "영업이익":                        "operating_income",
    "영업이익(손실)":                  "operating_income",
    "법인세차감전순이익(손실)":        "income_before_tax",
    "법인세차감전계속사업이익(손실)":  "income_before_tax",
    "법인세차감전 순이익":             "income_before_tax",
    "당기순이익":                      "net_income",
    "당기순이익(손실)":                "net_income",
    "유동자산":                        "current_assets",
    "자산총계":                        "total_assets",
    "유동부채":                        "current_liabilities",
    "부채총계":                        "total_liabilities",
    "자본금":                          "capital_stock",
    "이익잉여금":                      "retained_earnings",
    "자본총계":                        "total_equity",
}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def pivot_financial_to_wide(records: list[dict]) -> list[dict]:
    """long-format 재무 레코드를 wide-format 행으로 피벗.

    normalize_financial_statements() 결과를 받아
    (fs_div, year) 단위로 묶고 DB INSERT에 바로 사용 가능한 dict 목록을 반환.
    """
    groups: dict[tuple, dict] = {}
    last_rec: dict = {}
    for rec in records:
        if rec.get("period_type") != "당기":
            continue
        col = _ACCOUNT_TO_COL.get(rec.get("account_nm", ""))
        if col is None:
            continue
        key = (rec["fs_div"], rec["year"])
        if key not in groups:
            groups[key] = {"fs_div": rec["fs_div"], "year": rec["year"]}
        groups[key][col] = _safe_int(rec.get("amount"))
        last_rec = rec

    rows = []
    for (fs_div, year), vals in groups.items():
        rows.append({
            "fiscal_year":         year,
            "fs_div":              fs_div,
            "rcept_no":            last_rec.get("rcept_no") or "",
            "reprt_code":          "11011",
            "revenue":             vals.get("revenue"),
            "operating_income":    vals.get("operating_income"),
            "income_before_tax":   vals.get("income_before_tax"),
            "net_income":          vals.get("net_income"),
            "current_assets":      vals.get("current_assets"),
            "total_assets":        vals.get("total_assets"),
            "current_liabilities": vals.get("current_liabilities"),
            "total_liabilities":   vals.get("total_liabilities"),
            "capital_stock":       vals.get("capital_stock"),
            "retained_earnings":   vals.get("retained_earnings"),
            "total_equity":        vals.get("total_equity"),
            "currency":            "KRW",
        })
    return rows
