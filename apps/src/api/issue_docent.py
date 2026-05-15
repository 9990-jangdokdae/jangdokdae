from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.src.config.database import get_db
from apps.src.repositories.issue_docent import IssueDocentRepository
from apps.src.schemas.issue_docent import IssueDocentDetailResponse, IssueDocentListResponse
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
    service: IssueDocentReadService = ISSUE_DOCENT_SERVICE_DEPENDENCY,
) -> IssueDocentListResponse:
    return await service.list_issue_docents(limit=limit, offset=offset)


@router.get("/{issue_docent_id}", response_model=IssueDocentDetailResponse)
async def get_issue_docent(
    issue_docent_id: int,
    service: IssueDocentReadService = ISSUE_DOCENT_SERVICE_DEPENDENCY,
) -> IssueDocentDetailResponse:
    response = await service.get_issue_docent(issue_docent_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Issue Docent content not found")
    return response
