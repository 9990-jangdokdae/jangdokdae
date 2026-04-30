"""네이버 금융 주요뉴스 수집 모듈.

poc.ipynb의 "뉴스기사 수집" 셀을 함수화한 파일입니다.
흐름은 1) 날짜별 주요뉴스 목록에서 URL 수집, 2) 각 기사 본문 비동기 수집,
3) news_title/news_content/news_url DataFrame 반환 순서입니다.
"""

import logging
import asyncio
import re
from datetime import datetime

import aiohttp
import pandas as pd
import requests
from bs4 import BeautifulSoup

from apps.src.config.pipeline_config import DEFAULT_NEWS_DATE, DEFAULT_PAGE_LIMIT

logger = logging.getLogger(__name__)


BASE_URL = "https://finance.naver.com/news/mainnews.naver?"


def parse_link(link: str) -> str:
    """네이버 금융 목록 URL을 모바일 뉴스 본문 URL로 변환합니다."""
    article_id = re.findall(r"article_id=(.+?)&", link)[0]
    office_id = re.findall(r"office_id=(.+?)&", link)[0]
    return f"https://n.news.naver.com/mnews/article/{office_id}/{article_id}"


def collect_news_urls(
    news_date: str | None = DEFAULT_NEWS_DATE,
    page_limit: int = DEFAULT_PAGE_LIMIT,
) -> list[str]:
    """지정 날짜의 네이버 금융 주요뉴스 URL을 페이지 단위로 수집합니다.

    네이버 금융 목록은 마지막 페이지 이후에도 동일한 첫 기사가 반복될 수 있어서,
    이전 페이지의 첫 URL과 현재 페이지의 첫 URL이 같으면 수집을 중단합니다.
    """
    if news_date is None:
        news_date = datetime.now().strftime("%Y-%m-%d")

    params = {"date": news_date, "page": 1}
    previous_first = None
    news_urls: list[str] = []

    for page in range(1, page_limit + 1):
        params["page"] = page + 1
        logger.info("[news] collect urls page=%s date=%s", page + 1, news_date)
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        urls = [a.get("href") for a in soup.select("dd.articleSubject > a")]
        page_urls = [parse_link(url) for url in urls if url]

        if previous_first and page_urls and page_urls[0] == previous_first:
            logger.info("[news] duplicated first url at page=%s, stop", page + 1)
            break

        news_urls.extend(page_urls)
        logger.info("[news] page=%s urls=%s total=%s", page + 1, len(page_urls), len(news_urls))
        previous_first = page_urls[0] if page_urls else previous_first

    return news_urls


async def fetch_one_news(session: aiohttp.ClientSession, article_url: str) -> list[str] | None:
    """기사 URL 하나에서 제목/본문을 가져옵니다.

    파싱 실패나 요청 실패는 전체 수집을 중단하지 않도록 None으로 반환합니다.
    """
    try:
        async with session.get(article_url) as resp:
            html = await resp.text()

        soup = BeautifulSoup(html, "lxml")
        title_el = soup.select_one("#title_area > span")
        article_el = soup.select_one("#dic_area")

        if title_el is None or article_el is None:
            return None

        title = title_el.get_text(strip=True)
        article = article_el.get_text(" ", strip=True)
        return [title, article, article_url]
    except Exception as exc:
        logger.warning("[news] failed url=%s error=%s", article_url, exc)
        return None


async def fetch_all_news_async(
    news_urls: list[str],
    concurrency: int = 10,
) -> pd.DataFrame:
    """기사 URL 목록을 비동기로 수집해 news_title/news_content/news_url DataFrame으로 반환합니다."""
    connector = aiohttp.TCPConnector(limit=concurrency)
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        tasks = [fetch_one_news(session, article_url) for article_url in news_urls]
        results = await asyncio.gather(*tasks)

    docs = [row for row in results if row is not None]
    logger.info("[news] fetched articles success=%s failed=%s", len(docs), len(news_urls) - len(docs))
    return pd.DataFrame(docs, columns=["news_title", "news_content", "news_url"])


def fetch_all_news(news_urls: list[str], concurrency: int = 10) -> pd.DataFrame:
    """일반 Python 스크립트에서 비동기 기사 수집 함수를 호출하기 위한 래퍼입니다."""
    return asyncio.run(fetch_all_news_async(news_urls, concurrency=concurrency))


def collect_news_articles(
    news_date: str | None = DEFAULT_NEWS_DATE,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    concurrency: int = 10,
) -> pd.DataFrame:
    """URL 수집과 본문 수집을 한 번에 실행하는 상위 함수입니다."""
    news_urls = collect_news_urls(news_date=news_date, page_limit=page_limit)
    logger.info("[news] collected url count=%s", len(news_urls))
    return fetch_all_news(news_urls, concurrency=concurrency)
