"""뉴스 본문 전처리 모듈."""

import logging
import re

from apps.src.utils.list_utils import unique_by

logger = logging.getLogger(__name__)

# 임베딩 품질 저하를 막기 위해 기사 본문과 무관한 메타 텍스트를 제거한다.
_LINE_PATTERN = re.compile(r"^(?:▶|발로 뛰는|/\S)")
_INLINE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\[.*?기자\]"),
    re.compile(r"\((?:사진|이미지|그래픽|자료)=.*?\)"),
    re.compile(r"그래픽=\S+"),
    re.compile(r"\S+@\S+\.\S+"),
]


class NewsPreprocessor:
    """수집된 뉴스 기사 본문을 정제합니다."""

    def preprocess(self, articles: list[dict]) -> list[dict]:
        """article_id 기준 중복 제거 후 본문을 정제하고 빈 기사를 제거합니다."""
        before = len(articles)
        articles = unique_by(articles, key=lambda a: a["article_id"])

        result = []
        for article in articles:
            if not article.get("content"):
                continue
            article["content"] = self._clean(article["content"])
            if article["content"]:
                result.append(article)

        return result

    def _clean(self, text: str) -> str:
        """기자명·이메일·이미지 캡션 등 노이즈 텍스트를 제거하고 정제된 본문을 반환합니다."""
        lines = []
        for line in text.splitlines():
            if _LINE_PATTERN.search(line):
                continue
            for pattern in _INLINE_PATTERNS:
                line = pattern.sub("", line)
            line = line.strip()
            if line:
                lines.append(line)
        return "\n".join(lines)
