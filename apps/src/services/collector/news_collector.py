"""네이버 금융 주요뉴스 수집 모듈."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from apps.src.exceptions.collector_exceptions import NewsBodyFetchError
from apps.src.utils.date_utils import parse_datetime
from apps.src.utils.http_utils import with_retry

logger = logging.getLogger(__name__)


class NewsCollector:
    """네이버 금융 주요뉴스 수집기.

    Args:
        max_pages: 안전 상한 페이지 수.
        concurrency: 본문 동시 크롤링 수.
        delay_ms: 페이지 목록 요청 간 딜레이(ms).
    """

    _LIST_URL = "https://stock.naver.com/api/domestic/news/list"
    _ARTICLE_URL = "https://n.news.naver.com/mnews/article/{oid}/{aid}"
    _PAGE_SIZE = 20
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://stock.naver.com",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    def __init__(
        self,
        max_pages: int = 200,
        concurrency: int = 10,
        delay_ms: int = 200,
    ) -> None:
        """최대 페이지 수, 동시 크롤링 수, 요청 딜레이를 설정하고 세션을 초기화합니다."""
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.delay_ms = delay_ms
        self._session = requests.Session()
        self._session.headers.update(self._HEADERS)

    def collect(self, date: str | None = None) -> list[dict]:
        """지정 날짜의 네이버 금융 주요뉴스 전체를 수집합니다.

        Args:
            date: 수집 날짜 (YYYYMMDD). None이면 오늘.

        Returns:
            기사 dict 리스트. 각 항목은 article_id, office_id, title, url,
            press, published_date, content 필드를 가집니다.
        """
        date = date or datetime.now().strftime("%Y%m%d")

        raw_items = self._fetch_all_pages(date)
        articles = self._build_articles(raw_items)
        naver_parsed = self._fetch_bodies(articles)
        total_fetched = len(articles)
        articles = [a for a in articles if a["content"]]
        articles.sort(key=lambda a: a["published_date"] or "")

        return articles

    def _fetch_all_pages(self, date: str) -> list[dict]:
        """빈 페이지가 나올 때까지 목록 API를 순차 호출해 전체 raw 기사 목록을 반환합니다."""
        raw_items: list[dict] = []
        for page in range(1, self.max_pages + 1):
            if page > 1:
                time.sleep(self.delay_ms / 1000)
            items = self._fetch_page(date, page)
            if not items:
                break
            raw_items.extend(items)
        return raw_items

    def _fetch_page(self, date: str, page: int) -> list[dict]:
        """지정 날짜·페이지의 목록 API를 호출하고 articles 배열을 반환합니다."""
        def _get():
            """목록 API에 GET 요청을 보내고 JSON 응답을 반환합니다."""
            resp = self._session.get(
                self._LIST_URL,
                params={"category": "mainnews", "date": date, "page": page, "pageSize": self._PAGE_SIZE},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

        return with_retry(_get).get("articles", [])

    def _build_articles(self, raw_items: list[dict]) -> list[dict]:
        """API 응답 raw 항목을 파이프라인 표준 기사 dict 형태로 변환합니다."""
        articles = []
        for item in raw_items:
            oid = str(item.get("officeId") or "")
            aid = str(item.get("articleId") or "")
            url = self._ARTICLE_URL.format(oid=oid, aid=aid) if oid and aid else ""
            articles.append({
                "article_id": aid,
                "office_id": oid,
                "title": item.get("title", ""),
                "url": url,
                "press": item.get("officeHname") or "",
                "published_date": parse_datetime(item.get("datetime")),
                "content": None,
            })
        return articles

    def _fetch_bodies(self, articles: list[dict]) -> int:
        """본문을 병렬로 수집하고 성공 건수를 반환합니다."""
        count = 0
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_idx = {
                executor.submit(self._fetch_body, art["url"]): i
                for i, art in enumerate(articles)
                if art["url"]
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    content = future.result()
                    articles[idx]["content"] = content
                    if content is not None:
                        count += 1
                except Exception as exc:
                    err = NewsBodyFetchError(str(exc), article_id=articles[idx]["article_id"])
                    logger.warning("[news] body failed %s", err)
        return count

    def _fetch_body(self, url: str) -> str | None:
        """단일 기사 URL의 본문 텍스트를 BeautifulSoup으로 파싱해 반환합니다."""
        def _get():
            """기사 URL에 GET 요청을 보내고 HTML 텍스트를 반환합니다."""
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.text

        soup = BeautifulSoup(with_retry(_get), "lxml")
        article = soup.select_one("#newsct_article")
        return article.get_text(separator="\n", strip=True) if article else None
