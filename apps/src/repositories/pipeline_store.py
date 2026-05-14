"""파이프라인 각 단계의 결과를 DB에 저장하는 Store."""

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.src.config.database import AsyncSessionLocal
from apps.src.models.article import Article
from apps.src.models.cluster import Cluster, ClusterArticle, EntityExtraction
from apps.src.models.company import CompanyMaster, DartDocument, DartFinancialStatement
from apps.src.services.embedder.news_embedder import NewsEmbedder
from apps.src.services.preprocessor.dart_preprocessor import pivot_financial_to_wide

logger = logging.getLogger(__name__)

# dart_document section 키 → 한국어 섹션명
_SECTION_NAMES: dict[str, str] = {
    "II_business":          "사업의 내용",
    "IV_director_analysis": "이사의 경영진단 및 분석의견",
    "V_audit_opinion":      "회계감사인의 감사의견",
}


class PipelineStore:
    """파이프라인 단계별 DB 저장 메서드 모음. 모든 메서드는 async."""

    def __init__(self, embedder: NewsEmbedder) -> None:
        self._embedder = embedder

    # ── articles ──────────────────────────────────────────────────────────────

    async def save_articles(self, articles: list[dict]) -> dict[str, int]:
        """전처리된 기사를 articles 테이블에 저장하고 article_id → PK 매핑을 반환."""
        if not articles:
            return {}

        rows = [
            {
                "article_id":     a["article_id"],
                "office_id":      a.get("office_id"),
                "title":          a["title"],
                "url":            a["url"],
                "press":          a.get("press"),
                "published_date": _parse_dt(a.get("published_date")),
                "content":        a["content"],
            }
            for a in articles
        ]

        stmt = (
            insert(Article.__table__)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["article_id"])
            .returning(Article.__table__.c.id, Article.__table__.c.article_id)
        )

        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(stmt)
                inserted = {row.article_id: row.id for row in result}

                # on_conflict_do_nothing은 충돌된 행을 RETURNING하지 않으므로
                # 이미 존재하는 기사 PK를 같은 트랜잭션에서 조회
                missing = [a["article_id"] for a in articles if a["article_id"] not in inserted]
                if missing:
                    existing = await session.execute(
                        select(Article.id, Article.article_id).where(
                            Article.article_id.in_(missing)
                        )
                    )
                    for row in existing:
                        inserted[row.article_id] = row.id

        logger.info("[store] articles saved=%d", len(inserted))
        return inserted

    # ── clusters ──────────────────────────────────────────────────────────────

    async def save_clusters(
        self,
        clusters: list[dict],
        run_date: date,
        article_id_map: dict[str, int],
    ) -> dict[int, int]:
        """클러스터와 cluster_articles 중간 테이블을 저장하고 cluster_seq → PK 매핑 반환."""
        if not clusters:
            return {}

        cluster_rows = [
            {
                "run_date":     run_date,
                "cluster_seq":  c["cluster_id"],
                "size":         c["size"],
                "is_singleton": c.get("is_singleton", False),
            }
            for c in clusters
        ]

        cluster_id_map: dict[int, int] = {}

        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 재실행 멱등성: 같은 (run_date, cluster_seq)가 있으면 건너뜀
                result = await session.execute(
                    insert(Cluster.__table__)
                    .values(cluster_rows)
                    .on_conflict_do_nothing(index_elements=["run_date", "cluster_seq"])
                    .returning(Cluster.__table__.c.id, Cluster.__table__.c.cluster_seq)
                )
                cluster_id_map = {row.cluster_seq: row.id for row in result}

                # 충돌로 건너뛴 기존 클러스터 PK 조회
                missing_seqs = [c["cluster_id"] for c in clusters if c["cluster_id"] not in cluster_id_map]
                if missing_seqs:
                    existing = await session.execute(
                        select(Cluster.id, Cluster.cluster_seq).where(
                            Cluster.run_date == run_date,
                            Cluster.cluster_seq.in_(missing_seqs),
                        )
                    )
                    for row in existing:
                        cluster_id_map[row.cluster_seq] = row.id

                # cluster_articles
                ca_rows = []
                for c in clusters:
                    cluster_pk = cluster_id_map.get(c["cluster_id"])
                    if cluster_pk is None:
                        continue
                    for article in c.get("articles", []):
                        article_pk = article_id_map.get(article["article_id"])
                        if article_pk is None:
                            continue
                        ca_rows.append({
                            "cluster_id":             cluster_pk,
                            "article_id":             article_pk,
                            "similarity_to_centroid": article.get("similarity_to_centroid"),
                        })

                if ca_rows:
                    await session.execute(
                        insert(ClusterArticle.__table__)
                        .values(ca_rows)
                        .on_conflict_do_nothing()
                    )

        logger.info("[store] clusters saved=%d", len(cluster_id_map))
        return cluster_id_map

    # ── entity_extraction ─────────────────────────────────────────────────────

    async def save_entity_extraction(
        self,
        clusters: list[dict],
        cluster_id_map: dict[int, int],
    ) -> None:
        """클러스터별 LLM 추출 결과(기업명·섹터·키워드)를 저장."""
        rows = []
        for c in clusters:
            extraction = c.get("extraction")
            if not extraction:
                continue
            cluster_pk = cluster_id_map.get(c["cluster_id"])
            if cluster_pk is None:
                continue
            rows.append({
                "cluster_id":    cluster_pk,
                "company_names": extraction.get("companies", []),
                "sectors":       extraction.get("sectors", []),
                "keywords":      extraction.get("keywords", []),
            })

        if not rows:
            return

        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    insert(EntityExtraction.__table__)
                    .values(rows)
                    .on_conflict_do_nothing(index_elements=["cluster_id"])
                )

        logger.info("[store] entity_extraction saved=%d", len(rows))

    # ── company_master + dart_financial_statements + dart_document ────────────

    async def save_company_data(self, clusters: list[dict]) -> None:
        """기업 마스터·재무제표·사업보고서 섹션을 저장."""
        seen: set[str] = set()

        async with AsyncSessionLocal() as session:
            async with session.begin():
                for cluster in clusters:
                    for company in cluster.get("company_data", []):
                        if not company.get("matched"):
                            continue

                        krx_code = company["krx_code"]
                        dart_code = company.get("dart_code")
                        dart_name = company.get("dart_name")
                        sector = company.get("sector")
                        market = company.get("market")

                        company_pk = await _upsert_company(
                            session, krx_code, dart_code, company["company_name"], dart_name, sector, market
                        )

                        if krx_code in seen:
                            continue
                        seen.add(krx_code)

                        fin_stmts = company.get("dart", {}).get("financial_statements", [])
                        if fin_stmts:
                            await _upsert_financial_statements(session, company_pk, fin_stmts)

                        biz_report = company.get("dart", {}).get("business_report")
                        if biz_report:
                            await _insert_dart_documents(session, company_pk, biz_report, self._embedder)

        logger.info("[store] company_data saved companies=%d", len(seen))


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

async def _upsert_company(
    session: Any,
    krx_code: str,
    dart_code: str | None,
    krx_name: str,
    dart_name: str | None = None,
    sector: str | None = None,
    market: str | None = None,
) -> int:
    result = await session.execute(
        select(CompanyMaster.id).where(CompanyMaster.krx_code == krx_code)
    )
    existing_id = result.scalar_one_or_none()
    if existing_id:
        return existing_id

    new_company = CompanyMaster(
        krx_code=krx_code,
        dart_code=dart_code,
        krx_name=krx_name,
        dart_name=dart_name,
        sector=sector,
        market=market,
        updated_at=datetime.now(),
    )
    session.add(new_company)
    await session.flush()  # FK 참조 전에 DB에 반영 → auto-increment id 할당
    return new_company.id


async def _upsert_financial_statements(
    session: Any, company_id: int, records: list[dict]
) -> None:
    """long-format 재무 레코드를 dart_preprocessor로 피벗 후 UPSERT."""
    wide_rows = pivot_financial_to_wide(records)
    if not wide_rows:
        return

    rows = [
        {
            "company_id": company_id,
            "updated_at": datetime.now(),
            **row,
        }
        for row in wide_rows
    ]

    await session.execute(
        insert(DartFinancialStatement.__table__)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["company_id", "fiscal_year", "fs_div", "reprt_code"],
            set_={
                col: insert(DartFinancialStatement.__table__).excluded[col]
                for col in ["revenue", "operating_income", "income_before_tax", "net_income",
                            "current_assets", "total_assets", "current_liabilities",
                            "total_liabilities", "capital_stock", "retained_earnings",
                            "total_equity", "updated_at"]
            },
        )
    )


async def _insert_dart_documents(
    session: Any, company_id: int, biz_report: dict, embedder: NewsEmbedder
) -> None:
    """사업보고서 섹션을 소제목 단위로 dart_document에 저장."""
    sections: dict = biz_report.get("sections", {})
    rcept_dt: str = biz_report.get("rcept_dt", "")
    fiscal_year = _parse_fiscal_year(rcept_dt)

    rows = []
    for key, section_name in _SECTION_NAMES.items():
        chunks: list[dict] = sections.get(key, [])
        if isinstance(chunks, str):
            # 이전 포맷 호환: 문자열이면 단일 청크로 래핑
            chunks = [{"subsection": "", "content": chunks}] if chunks else []
        for chunk in chunks:
            content = chunk.get("content", "")
            if not content.strip():
                continue
            subsection = chunk.get("subsection") or ""
            embedding = embedder.embed_text(content)
            rows.append({
                "company_id":    company_id,
                "document_type": "business_report",
                "fiscal_year":   fiscal_year,
                "period_type":   "annual",
                "section":       section_name,
                "subsection":    subsection,
                "content":       content,
                "embedding":     embedding,
                "source":        "DART",
                "source_url":    None,
                "created_at":    datetime.now(),
            })

    if rows:
        await session.execute(
            insert(DartDocument.__table__)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["company_id", "fiscal_year", "section", "subsection"])
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_fiscal_year(rcept_dt: str) -> int:
    """DART 접수일자(YYYY-MM-DD 또는 YYYYMMDD)에서 회계연도 추정."""
    try:
        year = int(rcept_dt[:4])
        # 사업보고서는 다음 해 3~4월에 제출 → 전년도가 회계연도
        return year - 1
    except (TypeError, ValueError, IndexError):
        return datetime.now().year - 1
