"""News article embedding generation."""

import logging

import numpy as np
import pandas as pd
from openai import OpenAI

from apps.src.config.pipeline_config import DEFAULT_EMBEDDING_MODEL
from apps.src.services.preprocessor.news_preprocessor import normalize_news_columns

logger = logging.getLogger(__name__)


def build_embedding_texts(
    df: pd.DataFrame,
    title_col: str = "news_title",
    body_col: str = "news_content",
    max_text_chars: int = 3000,
) -> list[str]:
    """news_title + news_content를 embedding 입력 텍스트로 구성합니다."""
    df = normalize_news_columns(df)
    return (
        df[title_col].fillna("").astype(str)
        + " "
        + df[body_col].fillna("").astype(str)
    ).str.slice(0, max_text_chars).tolist()


def embed_news_articles(
    df: pd.DataFrame,
    client: OpenAI | None = None,
    model: str = DEFAULT_EMBEDDING_MODEL,
    title_col: str = "news_title",
    body_col: str = "news_content",
    batch_size: int = 50,
    max_text_chars: int = 3000,
) -> np.ndarray:
    """기사 제목과 본문을 합친 텍스트를 OpenAI embedding 벡터로 변환합니다."""
    client = client or OpenAI()
    texts = build_embedding_texts(df, title_col=title_col, body_col=body_col, max_text_chars=max_text_chars)

    embeddings = []
    logger.info(
        "[embedding] start rows=%s model=%s batch_size=%s max_text_chars=%s",
        len(texts),
        model,
        batch_size,
        max_text_chars,
    )
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        logger.info(
            "[embedding] request batch_start=%s batch_end=%s batch_size=%s",
            start,
            min(start + batch_size, len(texts)),
            len(batch),
        )
        response = client.embeddings.create(input=batch, model=model)
        embeddings.extend(data.embedding for data in response.data)
        logger.info("[embedding] progress %s/%s articles", min(start + batch_size, len(texts)), len(texts))

    logger.info("[embedding] done rows=%s", len(embeddings))
    return np.array(embeddings)


embed_articles = embed_news_articles
