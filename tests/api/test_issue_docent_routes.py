from datetime import datetime

from fastapi.testclient import TestClient

from apps.src.api.issue_docent import get_issue_docent_service
from apps.main import create_app
from apps.src.schemas.issue_docent import (
    ExplanationParagraph,
    ExplanationSection,
    IssueDocentDetailResponse,
    IssueDocentListItem,
    IssueDocentListResponse,
    IssueDocentQuiz,
    MatchedTerm,
    SectorCompanies,
    SectorCompany,
    SourceArticle,
)


class FakeIssueDocentService:
    async def list_issue_docents(self, *, limit: int, offset: int) -> IssueDocentListResponse:
        return IssueDocentListResponse(
            items=[
                IssueDocentListItem(
                    id=1,
                    cluster_id=10,
                    title="삼성전자 반도체 투자 확대",
                    teaser="삼성전자가 반도체 투자 계획을 밝혔다. 관련 수치가 기사에 명시됐다.",
                    sector_companies=[
                        SectorCompanies(
                            sector="전기·전자",
                            companies=[
                                SectorCompany(
                                    company_id=1,
                                    name="삼성전자",
                                    market="KOSPI",
                                )
                            ],
                        )
                    ],
                    article_count=2,
                    created_at=datetime(2026, 5, 14, 9, 0, 0),
                )
            ],
            total=1,
            limit=limit,
            offset=offset,
        )

    async def get_issue_docent(self, issue_docent_id: int) -> IssueDocentDetailResponse | None:
        if issue_docent_id != 1:
            return None
        return IssueDocentDetailResponse(
            id=1,
            cluster_id=10,
            title="삼성전자 반도체 투자 확대",
            teaser="삼성전자가 반도체 투자 계획을 밝혔다. 관련 수치가 기사에 명시됐다.",
            sector_companies=[
                SectorCompanies(
                    sector="전기·전자",
                    companies=[
                        SectorCompany(
                            company_id=1,
                            name="삼성전자",
                            market="KOSPI",
                        )
                    ],
                )
            ],
            article_count=2,
            explanation=[
                ExplanationSection(
                    section_type="what_happened",
                    title="무슨 일이 있었나",
                    paragraphs=[
                        ExplanationParagraph(
                            text="영업이익 수치가 기사에 포함됐다.",
                            matched_terms=[
                                MatchedTerm(
                                    term_id=1,
                                    term="영업이익",
                                    category="재무제표",
                                    definition="",
                                    start=0,
                                    end=4,
                                )
                            ],
                        )
                    ],
                )
            ],
            articles=[
                SourceArticle(
                    article_id="001",
                    title="원문 기사 제목",
                    press="테스트신문",
                    published_date=datetime(2026, 5, 14, 8, 0, 0),
                    url="https://example.com/news/1",
                )
            ],
            quizzes=[
                IssueDocentQuiz(
                    quiz_id="quiz-1",
                    kind="issue",
                    question="첫 번째 질문",
                    options=["A", "B", "C", "D"],
                    answer_index=0,
                    explanation="해설",
                ),
                IssueDocentQuiz(
                    quiz_id="quiz-2",
                    kind="issue",
                    question="두 번째 질문",
                    options=["A", "B", "C", "D"],
                    answer_index=1,
                    explanation="해설",
                ),
            ],
            created_at=datetime(2026, 5, 14, 9, 0, 0),
        )


def make_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_issue_docent_service] = lambda: FakeIssueDocentService()
    return TestClient(app)


def test_list_issue_docents_excludes_explanation_and_summary():
    response = make_client().get("/api/v1/contents/issue-docent")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert "explanation" not in body["items"][0]
    assert "summary" not in body["items"][0]
    assert "quizzes" not in body["items"][0]


def test_list_issue_docents_uses_sector_companies_only():
    response = make_client().get("/api/v1/contents/issue-docent")

    body = response.json()
    item = body["items"][0]
    assert item["sector_companies"][0]["sector"] == "전기·전자"
    assert item["sector_companies"][0]["companies"][0]["name"] == "삼성전자"
    assert "company_names" not in item
    assert "sectors" not in item


def test_get_issue_docent_includes_articles_and_matched_terms():
    response = make_client().get("/api/v1/contents/issue-docent/1")

    assert response.status_code == 200
    body = response.json()
    assert body["articles"][0]["url"] == "https://example.com/news/1"
    assert body["explanation"][0]["paragraphs"][0]["matched_terms"][0]["term"] == "영업이익"
    assert body["quizzes"][0]["quiz_id"] == "quiz-1"
    assert len(body["quizzes"]) == 2


def test_get_issue_docent_uses_sector_companies_only():
    response = make_client().get("/api/v1/contents/issue-docent/1")

    body = response.json()
    assert body["sector_companies"][0]["companies"][0]["market"] == "KOSPI"
    assert "company_names" not in body
    assert "sectors" not in body


def test_get_issue_docent_returns_404():
    response = make_client().get("/api/v1/contents/issue-docent/999")

    assert response.status_code == 404
