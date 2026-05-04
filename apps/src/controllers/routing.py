from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from apps.src.models.DTO import AnalysisResponse
from apps.src.services.analyzer.analyzer_service import AnalyzerService


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/health")
def analysis_health() -> dict[str, str]:
    return {"status": "ok", "service": "analyzer"}


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_article(request: dict[str, Any]) -> AnalysisResponse:
    service = AnalyzerService()
    return service.analyze_payload(request)


@router.post("/analyze-batch", response_model=list[AnalysisResponse])
def analyze_articles(request: dict[str, Any] | list[dict[str, Any]]) -> list[AnalysisResponse]:
    service = AnalyzerService()
    return service.analyze_many(request)
