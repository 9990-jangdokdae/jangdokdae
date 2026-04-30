"""News preprocessing and standard column normalization."""

import hashlib
import re

import pandas as pd

NEWS_COLUMN_RENAME_MAP = {
    "title": "news_title",
    "body": "news_content",
    "article": "news_content",
    "url": "news_url",
    "sectors": "sector",
    "companies": "company",
    "keywords": "keyword",
}


def clean_news_content(text: str) -> str:
    """기사 본문에서 분석에 불필요한 메타 문자열과 공백을 정리합니다."""
    text = text.replace("\n", " ")
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    text = re.sub(r"\b\d{4}\.\d{2}\.\d{2}\.\b", " ", text)
    text = re.sub(r"[가-힣]{2,4}\s?기자\s?=\s?", " ", text)
    text = text.replace("．", ".")
    text = re.sub(r"[\"“”‘’]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_news_columns(df: pd.DataFrame) -> pd.DataFrame:
    """기존 POC 컬럼명을 표준 뉴스 컬럼명으로 변환합니다."""
    rename_map = {
        old: new
        for old, new in NEWS_COLUMN_RENAME_MAP.items()
        if old in df.columns and new not in df.columns
    }
    return df.rename(columns=rename_map)


def make_news_id(row: pd.Series) -> str:
    """news_url 기반 SHA-1 news_id를 만들고, URL이 없으면 제목+본문을 사용합니다."""
    news_url = row.get("news_url")
    if isinstance(news_url, str) and news_url.strip():
        key = news_url.strip()
    else:
        key = f"{row.get('news_title', '')}|{row.get('news_content', '')}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"news_{digest}"


def ensure_news_id(df: pd.DataFrame) -> pd.DataFrame:
    """news_id 컬럼이 없으면 생성하고 맨 앞으로 정렬합니다."""
    out = normalize_news_columns(df.copy())
    if "news_id" not in out.columns:
        out.insert(0, "news_id", out.apply(make_news_id, axis=1))
    else:
        cols = ["news_id"] + [col for col in out.columns if col != "news_id"]
        out = out[cols]
    return out


def preprocess_news_articles(df: pd.DataFrame, body_col: str = "news_content") -> pd.DataFrame:
    """기사 DataFrame 컬럼과 본문을 표준화하고 news_id를 보장합니다."""
    out = normalize_news_columns(df.copy())
    if body_col in out.columns:
        out[body_col] = out[body_col].fillna("").astype(str).apply(clean_news_content)
    return ensure_news_id(out)


preprocess_news = clean_news_content
