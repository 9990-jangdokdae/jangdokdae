from apps.src.repositories.issue_docent import IssueDocentRepository
from apps.src.schemas.issue_docent import (
    IssueDocentDetailResponse,
    IssueDocentListItem,
    IssueDocentListResponse,
    IssueDocentQuiz,
    MatchedTerm,
    SourceArticle,
    SummaryContent,
    SummaryParagraph,
)
from apps.src.services.issue_docent.sector_companies import build_sector_companies
from apps.src.services.issue_docent.term_matcher import StockTermForMatch, match_terms

_STOCK_TERMS_CACHE: list[StockTermForMatch] | None = None


def clear_stock_terms_cache() -> None:
    global _STOCK_TERMS_CACHE
    _STOCK_TERMS_CACHE = None


class IssueDocentReadService:
    def __init__(self, repository: IssueDocentRepository) -> None:
        self.repository = repository

    async def list_issue_docents(self, *, limit: int, offset: int) -> IssueDocentListResponse:
        records, total = await self.repository.list_issue_docents(limit=limit, offset=offset)
        candidates = await self.repository.get_company_master_candidates(
            _unique_company_names(records)
        )
        return IssueDocentListResponse(
            items=[
                IssueDocentListItem(
                    id=record.id,
                    cluster_id=record.cluster_id,
                    title=record.title,
                    teaser=record.teaser,
                    sector_companies=build_sector_companies(
                        record.extracted_company_names,
                        candidates,
                    ),
                    article_count=record.article_count,
                    created_at=record.created_at,
                )
                for record in records
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_issue_docent(self, issue_docent_id: int) -> IssueDocentDetailResponse | None:
        record = await self.repository.get_issue_docent(issue_docent_id)
        if record is None:
            return None

        terms = await self._get_stock_terms()
        articles = await self.repository.get_source_articles(record.cluster_id)
        candidates = await self.repository.get_company_master_candidates(
            record.extracted_company_names
        )
        return IssueDocentDetailResponse(
            id=record.id,
            cluster_id=record.cluster_id,
            title=record.title,
            teaser=record.teaser,
            sector_companies=build_sector_companies(
                record.extracted_company_names,
                candidates,
            ),
            article_count=record.article_count,
            summary=_enrich_summary(record.summary, terms),
            articles=[
                SourceArticle.model_validate(article, from_attributes=True)
                for article in articles
            ],
            quizzes=[IssueDocentQuiz.model_validate(quiz) for quiz in record.quizzes],
            created_at=record.created_at,
        )

    async def _get_stock_terms(self) -> list[StockTermForMatch]:
        global _STOCK_TERMS_CACHE
        if _STOCK_TERMS_CACHE is None:
            _STOCK_TERMS_CACHE = await self.repository.get_stock_terms()
        return _STOCK_TERMS_CACHE


def _enrich_summary(
    summary: str,
    terms: list[StockTermForMatch],
) -> SummaryContent:
    return SummaryContent(
        paragraphs=[
            SummaryParagraph(
                text=paragraph,
                matched_terms=_matched_terms_for_paragraph(paragraph, terms),
            )
            for paragraph in _split_summary_paragraphs(summary)
        ]
    )


def _split_summary_paragraphs(summary: str) -> list[str]:
    return [paragraph.strip() for paragraph in summary.split("\n\n") if paragraph.strip()]


def _matched_terms_for_paragraph(
    paragraph: str,
    terms: list[StockTermForMatch],
) -> list[MatchedTerm]:
    return [
        MatchedTerm(
            term_id=match.term_id,
            term=match.term,
            category=match.category,
            definition=match.definition,
            start=match.start,
            end=match.end,
        )
        for match in match_terms(paragraph, terms)
    ]


def _unique_company_names(records: list) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for record in records:
        for name in record.extracted_company_names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
    return ordered
