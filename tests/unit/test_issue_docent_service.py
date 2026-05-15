from datetime import datetime

import pytest

from apps.src.repositories.issue_docent import (
    IssueDocentDetailRecord,
    IssueDocentListRecord,
    SourceArticleRecord,
)
from apps.src.services.issue_docent.issue_docent_service import (
    IssueDocentReadService,
    clear_stock_terms_cache,
)
from apps.src.services.issue_docent.sector_companies import CompanyMasterCandidate


class FakeIssueDocentRepository:
    def __init__(self) -> None:
        self.requested_company_names: list[list[str]] = []

    async def list_issue_docents(self, *, limit: int, offset: int):
        return (
            [
                IssueDocentListRecord(
                    id=1,
                    cluster_id=10,
                    title="삼성전자 투자 확대",
                    teaser="삼성전자 관련 이슈",
                    extracted_company_names=["삼성전자", "미등록회사"],
                    article_count=2,
                    created_at=datetime(2026, 5, 14, 9, 0, 0),
                )
            ],
            1,
        )

    async def get_issue_docent(self, issue_docent_id: int):
        if issue_docent_id != 1:
            return None
        return IssueDocentDetailRecord(
            id=1,
            cluster_id=10,
            title="삼성전자 투자 확대",
            teaser="삼성전자 관련 이슈",
            extracted_company_names=["삼성전자"],
            article_count=2,
            created_at=datetime(2026, 5, 14, 9, 0, 0),
            explanation=[],
            quizzes=[],
        )

    async def get_company_master_candidates(self, company_names: list[str]):
        self.requested_company_names.append(company_names)
        return [
            CompanyMasterCandidate(
                id=1,
                krx_name="삼성전자",
                dart_name="삼성전자",
                sector="전기·전자",
                market="KOSPI",
            )
        ]

    async def get_source_articles(self, cluster_id: int):
        return [
            SourceArticleRecord(
                article_id="001",
                title="원문 기사 제목",
                press="테스트신문",
                published_date=datetime(2026, 5, 14, 8, 0, 0),
                url="https://example.com/news/1",
            )
        ]

    async def get_stock_terms(self):
        return []


@pytest.fixture(autouse=True)
def reset_stock_terms_cache():
    clear_stock_terms_cache()
    yield
    clear_stock_terms_cache()


@pytest.mark.asyncio
async def test_list_issue_docents_builds_sector_companies_once_per_request():
    repository = FakeIssueDocentRepository()
    service = IssueDocentReadService(repository)

    response = await service.list_issue_docents(limit=20, offset=0)

    assert repository.requested_company_names == [["삼성전자", "미등록회사"]]
    assert response.items[0].sector_companies[0].sector == "전기·전자"
    assert response.items[0].sector_companies[1].sector is None


@pytest.mark.asyncio
async def test_get_issue_docent_builds_sector_companies_for_detail():
    repository = FakeIssueDocentRepository()
    service = IssueDocentReadService(repository)

    response = await service.get_issue_docent(1)

    assert response is not None
    assert response.sector_companies[0].companies[0].company_id == 1
