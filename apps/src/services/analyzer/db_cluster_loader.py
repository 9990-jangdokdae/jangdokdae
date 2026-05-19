from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from apps.src.config import getenv


def _get_engine():
    """analyzer가 직접 DB를 읽을 때 쓰는 최소 SQLAlchemy engine을 만든다."""
    if not getenv.DATABASE_URL:
        raise RuntimeError("DATABASE_URL 환경변수가 필요합니다.")

    url = getenv.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    return create_engine(url, future=True)


def load_cluster_payload_from_db(cluster_id: str) -> dict:
    """DB cluster/article/entity 데이터를 analyzer용 payload 1개로 조립한다."""
    with _get_engine().connect() as conn:
        # 프론트/상세에서 들어오는 식별자를 실제 cluster_id로 정규화한다.
        resolved_cluster_id = _resolve_cluster_id(conn, cluster_id)

        cluster_row = conn.execute(
            text(
                """
                SELECT *
                FROM clusters
                WHERE id = :cluster_id
                """
            ),
            {"cluster_id": resolved_cluster_id},
        ).mappings().first()

        if not cluster_row:
            raise ValueError(f"cluster not found: {cluster_id}")

        news_rows = conn.execute(
            text(
                """
                SELECT a.*, ca.similarity_to_centroid
                FROM cluster_articles ca
                JOIN articles a ON a.id = ca.article_id
                WHERE ca.cluster_id = :cluster_id
                ORDER BY ca.similarity_to_centroid DESC NULLS LAST, a.id
                """
            ),
            {"cluster_id": resolved_cluster_id},
        ).mappings().all()

        entity_rows = conn.execute(
            text(
                """
                SELECT *
                FROM entity_extraction
                WHERE cluster_id = :cluster_id
                ORDER BY id
                """
            ),
            {"cluster_id": resolved_cluster_id},
        ).mappings().all()

        market_rows = _load_market_rows(conn, resolved_cluster_id)

    company_names = _collect_names(entity_rows, "company_names")
    sectors = _collect_names(entity_rows, "sectors")
    keywords = _collect_names(entity_rows, "keywords")

    company_master_map = _load_company_master_map(company_names)
    financial_snapshots = _load_financial_snapshots(company_master_map)
    stock_quotes = _fetch_pykrx_stock_quotes(company_master_map)
    kospi_quote = _fetch_pykrx_kospi_quote()

    news_items: list[dict[str, Any]] = []
    representative_article: dict[str, Any] | None = None

    for index, row in enumerate(news_rows):
        article = {
            "id": _first_text(row.get("article_id"), row.get("id")),
            "article_id": _first_text(row.get("article_id"), row.get("id")),
            "news_id": _first_text(row.get("article_id"), row.get("id")),
            "title": _first_text(row.get("title"), row.get("news_title")),
            "content": _first_text(row.get("content"), row.get("news_content")) or "",
            "article_role": "representative" if index == 0 else "member",
            "company_names": company_names,
            "companies": company_names,
            "sectors": sectors,
            "keywords": keywords,
        }
        news_items.append(article)
        if index == 0:
            representative_article = article

    payload = {
        "cluster": {
            "id": _first_text(cluster_row.get("id"), resolved_cluster_id),
            "cluster_id": _first_text(cluster_row.get("id"), resolved_cluster_id),
            "cluster_seq": _first_text(cluster_row.get("cluster_seq")),
            "size": _first_text(cluster_row.get("size")),
            "sectors": sectors,
            "keywords": keywords,
        },
        "representative_article": representative_article or {},
        "news": news_items,
        "company": _build_company_payloads(company_names, company_master_map, stock_quotes, financial_snapshots),
        "market_context": _build_market_context(market_rows, kospi_quote),
        "sectors": sectors,
        "keywords": keywords,
    }

    return payload



def _resolve_cluster_id(conn, lookup_id: str) -> str:
    """들어온 식별자를 DB exact id 관계로 따라 실제 cluster_id로 정규화한다."""
    # 유사한 기사를 찾는 게 아니라, DB에 저장된 exact id 관계만 따라간다.
    normalized_lookup_id = str(lookup_id).strip()
    if not normalized_lookup_id:
        raise ValueError("cluster lookup id is required")

    direct_cluster = conn.execute(
        text(
            """
            SELECT id
            FROM clusters
            WHERE CAST(id AS TEXT) = :lookup_id
            LIMIT 1
            """
        ),
        {"lookup_id": normalized_lookup_id},
    ).scalar()
    if direct_cluster is not None:
        return str(direct_cluster)

    representative_cluster = conn.execute(
        text(
            """
            SELECT id
            FROM clusters
            WHERE CAST(representative_news_id AS TEXT) = :lookup_id
            LIMIT 1
            """
        ),
        {"lookup_id": normalized_lookup_id},
    ).scalar()
    if representative_cluster is not None:
        return str(representative_cluster)

    article_cluster = conn.execute(
        text(
            """
            SELECT ca.cluster_id
            FROM cluster_articles ca
            JOIN articles a ON a.id = ca.article_id
            WHERE CAST(ca.article_id AS TEXT) = :lookup_id
               OR CAST(a.id AS TEXT) = :lookup_id
               OR CAST(a.article_id AS TEXT) = :lookup_id
            ORDER BY ca.similarity_to_centroid DESC NULLS LAST, ca.cluster_id
            LIMIT 1
            """
        ),
        {"lookup_id": normalized_lookup_id},
    ).scalar()
    if article_cluster is not None:
        return str(article_cluster)

    raise ValueError(f"cluster not found for lookup id: {lookup_id}")


def _load_market_rows(conn, cluster_id: str) -> list[dict[str, Any]]:
    """cluster에 연결된 market_indicators 행들을 읽는다."""
    try:
        rows = conn.execute(
            text(
                """
                SELECT *
                FROM market_indicators
                WHERE cluster_id = :cluster_id
                """
            ),
            {"cluster_id": cluster_id},
        ).mappings().all()
        return list(rows)
    except SQLAlchemyError:
        return []


def _load_company_master_map(company_names: list[str]) -> dict[str, dict[str, str]]:
    """회사명 목록을 company_master 기본 정보와 연결한다."""
    company_map: dict[str, dict[str, str]] = {}
    if not company_names:
        return company_map

    with _get_engine().connect() as conn:
        for name in company_names:
            row = conn.execute(
                text(
                    """
                    SELECT id, krx_name, krx_code, sector, market
                    FROM company_master
                    WHERE krx_name = :name
                    LIMIT 1
                    """
                ),
                {"name": name},
            ).mappings().first()

            if not row:
                continue

            company_map[name] = {
                "company_id": str(row.get("id") or "").strip(),
                "ticker": _first_text(row.get("krx_code")) or "",
                "sector": _first_text(row.get("sector")) or "",
                "market": _first_text(row.get("market")) or "",
            }

    return company_map


def _load_financial_snapshots(company_master_map: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """company_id 기준 최근 연간 재무 스냅샷을 가져온다."""
    company_ids = [item.get("company_id") for item in company_master_map.values() if item.get("company_id")]
    if not company_ids:
        return {}

    snapshot_by_company_id: dict[str, dict[str, str]] = {}

    with _get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT company_id, fiscal_year, revenue, operating_income, net_income
                FROM dart_financial_statements
                WHERE company_id = ANY(:company_ids)
                  AND fs_div = 'CFS'
                ORDER BY company_id, fiscal_year DESC
                """
            ),
            {"company_ids": company_ids},
        ).mappings().all()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        company_id = str(row.get("company_id") or "").strip()
        if not company_id:
            continue
        grouped.setdefault(company_id, []).append(dict(row))

    for company_id, company_rows in grouped.items():
        latest = company_rows[0]
        previous = company_rows[1] if len(company_rows) > 1 else None

        latest_revenue = latest.get("revenue")
        latest_operating_income = latest.get("operating_income")
        latest_net_income = latest.get("net_income")

        snapshot: dict[str, str] = {
            "financial_year": str(latest.get("fiscal_year")),
        }

        revenue_text = _format_korean_amount(latest_revenue)
        if revenue_text:
            snapshot["revenue"] = revenue_text
        operating_income_text = _format_korean_amount(latest_operating_income)
        if operating_income_text:
            snapshot["operating_income"] = operating_income_text
        net_income_text = _format_korean_amount(latest_net_income)
        if net_income_text:
            snapshot["net_income"] = net_income_text

        if previous:
            revenue_yoy = _format_yoy_pct(latest_revenue, previous.get("revenue"))
            operating_income_yoy = _format_yoy_pct(latest_operating_income, previous.get("operating_income"))
            net_income_yoy = _format_yoy_pct(latest_net_income, previous.get("net_income"))
            if revenue_yoy:
                snapshot["revenue_yoy_pct"] = revenue_yoy
            if operating_income_yoy:
                snapshot["operating_income_yoy_pct"] = operating_income_yoy
            if net_income_yoy:
                snapshot["net_income_yoy_pct"] = net_income_yoy

        snapshot_by_company_id[company_id] = snapshot

    return snapshot_by_company_id


def _build_company_payloads(
    company_names: list[str],
    company_master_map: dict[str, dict[str, str]],
    stock_quotes: dict[str, dict[str, str]],
    financial_snapshots: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """회사명 -> 기본 정보/시세/재무를 한 번에 묶어 company payload를 만든다."""
    payloads: list[dict[str, Any]] = []

    for name in company_names:
        base = company_master_map.get(name, {})
        company_id = base.get("company_id") or ""
        ticker = base.get("ticker") or None
        quote = stock_quotes.get(ticker or "", {})
        financials = financial_snapshots.get(company_id, {})

        item: dict[str, Any] = {
            "name": name,
            "ticker": ticker,
            "sector": base.get("sector") or None,
        }

        if quote.get("current_price"):
            item["current_price"] = quote["current_price"]
        if quote.get("price_change_pct"):
            item["price_change_pct"] = quote["price_change_pct"]
        if quote.get("volume"):
            item["volume"] = quote["volume"]
        item.update(financials)

        payloads.append(item)

    return payloads


def _fetch_pykrx_stock_quotes(company_master_map: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """관련 기업 현재가/등락률을 pykrx 최근 거래일 기준으로 보강한다."""
    if not company_master_map:
        return {}

    quotes: dict[str, dict[str, str]] = {}
    for item in company_master_map.values():
        ticker = (item.get("ticker") or "").strip()
        if not ticker:
            continue
        quote = _get_recent_ticker_quote(ticker)
        if quote:
            quotes[ticker] = quote

    return quotes


def _fetch_pykrx_kospi_quote() -> dict[str, str] | None:
    """KOSPI 현재 지수와 등락률을 sidebar 비교 기준으로 가져온다."""
    try:
        from pykrx import stock
    except ImportError:
        return None

    recent_dates = _recent_business_dates(lookback_days=7)
    if not recent_dates:
        return None

    start = recent_dates[0]
    end = recent_dates[-1]

    try:
        frame = stock.get_index_ohlcv(start, end, "1001")
    except Exception:
        return None

    if frame is None or getattr(frame, "empty", True):
        return None

    latest = frame.iloc[-1]
    latest_close = latest.get("종가")
    change_pct = None
    if len(frame.index) >= 2:
        prev_close = frame.iloc[-2].get("종가")
        try:
            if prev_close not in (None, 0):
                change_pct = ((float(latest_close) - float(prev_close)) / float(prev_close)) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            change_pct = None

    return {
        "name": "KOSPI",
        "value": _format_index(latest_close),
        "change_pct": _format_pct(change_pct),
    }


def _build_market_context(market_rows: list[dict[str, Any]], kospi_quote: dict[str, Any] | None) -> list[dict[str, Any]]:
    """DB market_indicators가 있으면 우선 사용하고, 없으면 KOSPI 보강값으로 채운다."""
    db_items = []
    for row in market_rows:
        item = _build_market_payload(row)
        if item is not None:
            db_items.append(item)
    if db_items:
        return db_items
    return [kospi_quote] if kospi_quote else []


def _get_recent_market_ohlcv_frame(market: str):
    try:
        from pykrx import stock
    except ImportError:
        return None

    for target_date in reversed(_recent_business_dates(lookback_days=7)):
        try:
            frame = stock.get_market_ohlcv_by_ticker(target_date, market=market)
        except Exception:
            continue
        if frame is not None and not getattr(frame, "empty", True):
            return frame
    return None


def _get_recent_ticker_quote(ticker: str) -> dict[str, str] | None:
    try:
        from pykrx import stock
    except ImportError:
        return None

    for target_date in reversed(_recent_business_dates(lookback_days=7)):
        try:
            frame = stock.get_market_ohlcv(target_date, target_date, ticker)
        except Exception:
            continue
        if frame is None or getattr(frame, "empty", True):
            continue
        row = frame.iloc[-1]
        return {
            "current_price": _format_price(row.get("종가")),
            "price_change_pct": _format_pct(row.get("등락률")),
            "volume": _format_number(row.get("거래량")),
        }
    return None


def _recent_business_dates(lookback_days: int = 7) -> list[str]:
    today = date.today()
    dates: list[str] = []
    for offset in range(lookback_days, -1, -1):
        target = today - timedelta(days=offset)
        dates.append(target.strftime("%Y%m%d"))
    return dates


def _normalize_pykrx_market(value: str | None) -> str:
    market = (value or "").strip().upper()
    if "KOSDAQ" in market:
        return "KOSDAQ"
    if "KONEX" in market:
        return "KONEX"
    return "KOSPI"


def _build_market_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    name = _first_text(row.get("name"), row.get("indicator_name"), row.get("market_name"))
    if not name:
        return None
    return {
        "name": name,
        "value": _first_text(
            row.get("value"),
            row.get("current"),
            row.get("close"),
            row.get("index_level"),
            row.get("level"),
        ),
        "change_pct": _first_text(
            row.get("change_pct"),
            row.get("change"),
            row.get("rate"),
            row.get("delta_pct"),
        ),
    }


def _collect_names(rows: list[dict[str, Any]], field_name: str) -> list[str]:
    collected: list[str] = []
    for row in rows:
        for item in _coerce_list(row.get(field_name)):
            if item and item not in collected:
                collected.append(item)
    return collected


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return []
        if text_value.startswith("[") and text_value.endswith("]"):
            try:
                parsed = json.loads(text_value)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        if "," in text_value:
            return [part.strip() for part in text_value.split(",") if part.strip()]
        return [text_value]
    return [str(value).strip()] if str(value).strip() else []


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text_value = str(value).strip()
        if text_value:
            return text_value
    return None


def _format_price(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{int(round(float(value))):,}원"
    except (TypeError, ValueError):
        return None


def _format_pct(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = float(value)
        return f"{numeric:+.2f}%"
    except (TypeError, ValueError):
        return None


def _format_number(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return None


def _format_index(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return None


def _format_korean_amount(value: Any) -> str | None:
    if value is None:
        return None
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        return None

    abs_numeric = abs(numeric)
    sign = "-" if numeric < 0 else ""

    if abs_numeric >= 1_0000_0000_0000:
        jo = abs_numeric // 1_0000_0000_0000
        uk = (abs_numeric % 1_0000_0000_0000) // 1_0000_0000
        if uk:
            return f"{sign}{jo}조 {uk:,}억 원"
        return f"{sign}{jo}조 원"

    if abs_numeric >= 1_0000_0000:
        uk = abs_numeric / 1_0000_0000
        return f"{sign}{uk:,.0f}억 원"

    return f"{sign}{abs_numeric:,}원"


def _format_yoy_pct(current: Any, previous: Any) -> str | None:
    try:
        current_value = float(current)
        previous_value = float(previous)
        if previous_value == 0:
            return None
        pct = ((current_value - previous_value) / abs(previous_value)) * 100
        return f"{pct:+.1f}%"
    except (TypeError, ValueError, ZeroDivisionError):
        return None
