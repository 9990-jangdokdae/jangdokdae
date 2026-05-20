from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.repositories.issue_docent import IssueDocentRepository
from apps.src.schemas.issue_docent import (
    IssueDocentDetailResponse,
    IssueDocentListResponse,
    IssueDocentSearchSuggestionsResponse,
)
from apps.src.services.issue_docent.issue_docent_service import IssueDocentReadService

router = APIRouter(prefix="/api/v1/contents/issue-docent", tags=["issue-docent"])


async def get_issue_docent_service(
    session: AsyncSession = Depends(get_db),
) -> IssueDocentReadService:
    return IssueDocentReadService(IssueDocentRepository(session))


ISSUE_DOCENT_SERVICE_DEPENDENCY = Depends(get_issue_docent_service)


@router.get("", response_model=IssueDocentListResponse)
async def list_issue_docents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=50),
    service: IssueDocentReadService = ISSUE_DOCENT_SERVICE_DEPENDENCY,
) -> IssueDocentListResponse:
    search_query = q.strip() if q else None
    return await service.list_issue_docents(
        limit=limit,
        offset=offset,
        search_query=search_query or None,
    )


@router.get("/search-suggestions", response_model=IssueDocentSearchSuggestionsResponse)
async def search_suggestions(
    q: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=8, ge=1, le=12),
    service: IssueDocentReadService = ISSUE_DOCENT_SERVICE_DEPENDENCY,
) -> IssueDocentSearchSuggestionsResponse:
    search_query = q.strip()
    if not search_query:
        raise HTTPException(status_code=422, detail="Search query is required")
    return await service.search_suggestions(search_query=search_query, limit=limit)


@router.get("/{issue_docent_id}", response_model=IssueDocentDetailResponse)
async def get_issue_docent(
    issue_docent_id: int,
    service: IssueDocentReadService = ISSUE_DOCENT_SERVICE_DEPENDENCY,
) -> IssueDocentDetailResponse:
    response = await service.get_issue_docent(issue_docent_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Issue Docent content not found")
    return response
