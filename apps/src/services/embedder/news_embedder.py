"""뉴스 기사 임베딩 모듈."""

import logging
import os

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from apps.src.exceptions.processing_exceptions import EmbedEncodeError, EmbedModelError

logger = logging.getLogger(__name__)


class NewsEmbedder:
    """뉴스 기사 임베딩 생성기.

    토큰 제한이 있는 모델을 위해 기사를 청크로 분할하고 평균 풀링합니다.

    Args:
        batch_size: 한 번에 인코딩할 청크 수.
        overlap: 청크 간 겹치는 토큰 수 (문맥 단절 방지).
    """

    def __init__(self, batch_size: int = 32, overlap: int = 20) -> None:
        """EMBED_MODEL 환경변수의 모델을 로드하고 MPS/CPU 디바이스를 선택합니다."""
        model_name = os.environ.get("EMBED_MODEL")
        if not model_name:
            raise EmbedModelError("EMBED_MODEL environment variable is not set")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        try:
            self._model = SentenceTransformer(model_name, device=device)
        except Exception as exc:
            raise EmbedModelError(f"Failed to load model '{model_name}'", model_name=model_name) from exc
        self._tokenizer = self._model.tokenizer
        self._max_len = self._model.max_seq_length - 2  # [CLS], [SEP] 제외
        self.batch_size = batch_size
        self.overlap = overlap

    def embed(self, articles: list[dict]) -> list[dict]:
        """각 기사에 embedding 필드를 추가해 반환합니다. 입력 순서 보존."""
        # 모든 기사의 청크를 한 배치로 묶어 인코딩 효율을 높임
        chunk_index: list[int] = []
        chunk_texts: list[str] = []

        for i, article in enumerate(articles):
            text = f"{article['title']} {article['content'] or ''}"
            for chunk in self._chunk(text):
                chunk_index.append(i)
                chunk_texts.append(chunk)
        try:
            chunk_embeddings = self._model.encode(
                chunk_texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=True,
            )
        except Exception as exc:
            raise EmbedEncodeError(str(exc), articles_count=len(articles)) from exc

        article_chunks: list[list[np.ndarray]] = [[] for _ in articles]
        for idx, emb in zip(chunk_index, chunk_embeddings):
            article_chunks[idx].append(emb)

        for article, chunks in zip(articles, article_chunks):
            article["embedding"] = np.mean(chunks, axis=0).tolist()

        return articles

    def embed_text(self, text: str) -> list[float]:
        """단일 텍스트 임베딩. 청크 분할 후 평균 풀링."""
        chunks = self._chunk(text)
        embeddings = self._model.encode(
            chunks,
            batch_size=self.batch_size,
            normalize_embeddings=True,
        )
        return np.mean(embeddings, axis=0).tolist()

    def _chunk(self, text: str) -> list[str]:
        """텍스트를 모델 최대 토큰 길이 기준으로 겹치는 청크로 분할합니다."""
        stride = max(1, self._max_len - self.overlap)
        ids = self._tokenizer.encode(text, add_special_tokens=False)
        if not ids:
            return [text]

        chunks = []
        for start in range(0, len(ids), stride):
            end = min(start + self._max_len, len(ids))
            chunks.append(self._tokenizer.decode(ids[start:end], skip_special_tokens=True))
            if end == len(ids):
                break
        return chunks
