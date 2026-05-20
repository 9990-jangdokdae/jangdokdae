from __future__ import annotations

import json
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from apps.src.config import getenv
from apps.src.models.analyzer_dto import (
    AnalysisSection,
    AnalysisSectionsResponse,
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummary,
    KeyMetric,
    LLMAnalysisResponse,
    RelatedCompanyCard,
    RelatedMarketCard,
    SidebarInsightsResponse,
    SidebarMetricsResponse,
    SidebarContext,
)


SYSTEM_PROMPT = """너는 금융 뉴스 analyzer다.

목표:
대표 기사 본문과 앞단에서 전달된 cluster payload 문맥을 함께 읽고,
핵심 이슈와 요약 포인트를 구조화한 분석 결과 JSON을 만든다.

중요:
- representative 기사 1건을 중심으로 분석한다.
- 입력 메타데이터와 기업/섹터/시장 데이터는 힌트이자 비교 기준으로만 사용한다.
- 핵심 이슈와 요약 포인트는 반드시 기사 원문 근거가 있어야 한다.
- summary는 짧은 제목이 아니라, 이 뉴스를 이해하는 데 필요한 사실/원인/시장 반응/해석/시사점을 담은 설명형 문단으로 작성한다.
- summary_points와 evidence_sentences는 기사 원문에 있는 내용만 반영한다.
- summary와 analysis_sections의 모든 문장은 반드시 자연스러운 서술형 존댓말(~습니다/~입니다)로 작성한다.
- 반말, 메모체, 단정적인 명령문을 쓰지 않는다.
- analysis_sections는 프론트 상세 페이지의 분석 블록이다. 기본은 3개로 작성하고, 정말 필요한 경우에만 4개까지 허용한다. 번호를 붙이지 않는다.
- analysis_sections의 기본 역할은 아래 3단계 흐름을 따른다.
  1) 지금 무슨 변화가 있었는지
  2) 왜 중요한지 / 시장이 무엇을 보는지
  3) 지금 무엇을 더 확인해야 하는지
- section title은 위 역할 설명을 그대로 옮긴 메타 문구가 아니라, 기사 주제에 맞는 자연스러운 소제목으로 작성한다.
- "지금 무슨 변화가 있었는지", "왜 중요한지 / 시장이 무엇을 보는지", "지금 무엇을 더 확인해야 하는지"를 title로 그대로 쓰지 않는다.
- analysis_sections의 각 section은 서로 역할이 달라야 하며, 같은 사실이나 같은 해석을 의미 없이 반복하지 않는다.
- 중요한 사실이 여러 section에 필요하면 같은 말을 반복하지 말고, 각 section 역할에 맞게 의미를 달리해서 녹인다.
- 직접적인 투자판단(매수/매도 권유, 목표가 제시)은 하지 않는다.
- 기업/섹터/시장 데이터는 새 사실을 만들지 말고 기사 해석 보조용으로만 사용한다.
- 기사 주제에 맞지 않는 섹터나 테마를 억지로 중심 주제로 끌어오지 않는다.
- ETF 기사라면 ETF 시장, 자금 유입, 점유율 변화, 상품 경쟁력을 중심으로 해석한다.
- 출력은 반드시 JSON만 반환한다.
""".strip()


SIDEBAR_SYSTEM_PROMPT = """너는 금융 뉴스 analyzer의 우측 사이드바만 작성하는 보조 모델이다.

목표:
대표 기사 본문과 메인 분석 결과를 함께 읽고,
우측 사이드바에 들어갈 한마디 요약과 핵심 수치 카드를 JSON으로 만든다.

중요:
- sidebar_markets는 1개 또는 2개로 작성한다.
- sidebar_markets의 summary는 단순 요약이 아니라, 겉으로 보이는 현상보다 무엇을 먼저 봐야 하는지까지 담은 짧고 단단한 한 줄 문장으로 쓴다.
- sidebar_markets는 기사 핵심 이슈 기준으로 잡고, 키워드만 보고 섹터 이름을 기계적으로 고르지 않는다.
- sidebar_metrics는 2개 또는 3개로 작성한다.
- sidebar_metrics는 기사마다 성격이 달라질 수 있다. 비교형 카드만 고집하지 말고, 비교형·현황형·체크포인트형이 기사 주제에 맞게 섞일 수 있다.
- 저장된 기업 재무/과거 실적/시장 데이터가 있으면 그 값을 우선 사용하고, 기사 본문 숫자는 보조 근거로만 사용한다.
- sidebar_metrics의 emphasis는 숫자를 어떻게 읽어야 하는지 보여주는 한 줄이어야 한다. 전년 대비, 직전 분기 대비, 조회 시점 등락률, 지금 봐야 할 체크포인트처럼 기준이 바로 읽혀야 한다.
- sidebar_metrics는 첫 번째 숫자를 기계적으로 뽑지 말고, 기사 핵심 이슈를 설명하는 데 정말 중요한 숫자만 고른다.
- sidebar_metrics는 서로 다른 의미의 카드로 구성한다. 같은 수치를 이름만 바꿔 반복하지 않는다.
- 단위가 불분명하거나 근거가 약한 숫자는 카드로 만들지 않는다.
- 빈 배열을 반환하지 않는다.
- 출력은 반드시 JSON만 반환한다.
""".strip()


SIDEBAR_METRICS_SYSTEM_PROMPT = """너는 금융 뉴스 analyzer의 우측 사이드바 수치 카드만 작성하는 보조 모델이다.

목표:
대표 기사 본문과 메인 분석 결과를 읽고,
기사 주제를 설명하는 데 꼭 필요한 수치 카드만 JSON으로 만든다.

중요:
- sidebar_metrics는 2개 또는 3개를 작성한다.
- 기사마다 카드 성격은 달라질 수 있다. 비교형, 현황형, 체크포인트형 중 지금 기사에 맞는 조합을 고른다.
- 저장된 기업 재무/과거 실적/시장 데이터가 있으면 그 값을 우선 사용하고, 기사 본문 숫자는 보조 근거로만 사용한다.
- label/value/emphasis가 기사 핵심 이슈와 정확히 맞아야 한다.
- emphasis는 숫자의 의미를 읽게 하는 한 줄이어야 한다. 예를 들어 전년 대비, 직전 분기 대비, 조회 시점 등락률, 확인이 필요한 포인트처럼 기준이 분명해야 한다.
- 첫 번째 숫자를 기계적으로 뽑지 말고, 기사 핵심을 설명하는 숫자를 선택한다.
- 같은 의미의 숫자를 중복해서 쓰지 않는다.
- 아래에 제공되는 "수치 후보 문장"은 보조 근거로만 사용한다.
- 단위가 불분명하거나 근거가 약한 숫자는 카드로 만들지 않는다.
- 빈 배열을 반환하지 않는다.
- 출력은 반드시 JSON만 반환한다.
""".strip()


ANALYSIS_SECTIONS_REPAIR_PROMPT = """너는 금융 뉴스 analyzer의 본문 분석 섹션만 다시 작성하는 보조 모델이다.

목표:
대표 기사 본문과 이미 생성된 요약을 바탕으로,
프론트 상세에 들어갈 analysis_sections만 다시 JSON으로 만든다.

중요:
- analysis_sections는 반드시 3개를 작성한다.
- 모든 문장은 자연스러운 서술형 존댓말(~습니다/~입니다)로 작성한다.
- 각 섹션은 아래 3단계 역할을 정확히 따른다.
  1) 지금 무슨 변화가 있었는지
  2) 왜 중요한지 / 시장이 무엇을 보는지
  3) 지금 무엇을 더 확인해야 하는지
- section title은 위 역할 설명을 그대로 옮긴 메타 문구가 아니라, 기사 주제에 맞는 자연스러운 소제목으로 작성한다.
- "지금 무슨 변화가 있었는지", "왜 중요한지 / 시장이 무엇을 보는지", "지금 무엇을 더 확인해야 하는지"를 title로 그대로 쓰지 않는다.
- 기사 주제에 맞지 않는 섹터나 테마를 억지로 끌어오지 않는다.
- 같은 사실을 반복하지 않는다.
- 출력은 반드시 JSON만 반환한다.
""".strip()


class IssueBasedAnalyzerService:
    """대표 기사 기반 LLM 분석과 sidebar 정형화를 함께 맡는 본체."""

    def analyze(self, article: AnalysisRequest) -> AnalysisResponse:
        """LLM 1차 결과를 만들고, 프론트가 바로 쓰는 최종 응답으로 다시 묶는다."""
        result = self._analyze_with_langchain(article)
        sidebar_result = self._analyze_sidebar_with_langchain(article, result)
        return self._finalize_response(article, result, sidebar_result)

    def _analyze_with_langchain(self, article: AnalysisRequest) -> LLMAnalysisResponse:
        """LangChain structured output으로 Gemini 1차 결과를 받는다."""
        llm = self._build_langchain_model()
        structured_llm = llm.with_structured_output(LLMAnalysisResponse)
        result = structured_llm.invoke(self._build_prompt(article))
        if not isinstance(result, LLMAnalysisResponse):
            result = LLMAnalysisResponse.model_validate(result)
        if len(result.analysis_sections) < 3:
            repaired_sections = self._repair_analysis_sections(article, result)
            result = result.model_copy(update={"analysis_sections": repaired_sections.analysis_sections})
        return result

    def _repair_analysis_sections(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> AnalysisSectionsResponse:
        llm = self._build_langchain_model()
        structured_llm = llm.with_structured_output(AnalysisSectionsResponse)
        prompt = self._build_analysis_sections_repair_prompt(article, analysis_result)
        result = structured_llm.invoke(prompt)
        if not isinstance(result, AnalysisSectionsResponse):
            result = AnalysisSectionsResponse.model_validate(result)
        if len(result.analysis_sections) >= 3:
            return result

        raw_response = llm.invoke(prompt)
        raw_content = getattr(raw_response, "content", raw_response)
        if isinstance(raw_content, list):
            raw_content = "\n".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        parsed = self._parse_json_block(str(raw_content))
        return AnalysisSectionsResponse.model_validate(parsed)

    def _analyze_sidebar_with_langchain(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> SidebarInsightsResponse:
        """메인 분석 결과를 바탕으로 사이드바 전용 한마디와 수치 카드를 다시 만든다."""
        llm = self._build_langchain_model()
        structured_llm = llm.with_structured_output(SidebarInsightsResponse)
        result = structured_llm.invoke(self._build_sidebar_prompt(article, analysis_result))
        if not isinstance(result, SidebarInsightsResponse):
            result = SidebarInsightsResponse.model_validate(result)
        if len(result.sidebar_markets) >= 1 and len(result.sidebar_metrics) >= 2:
            return result

        repaired = structured_llm.invoke(
            self._build_sidebar_repair_prompt(article, analysis_result, result)
        )
        if not isinstance(repaired, SidebarInsightsResponse):
            repaired = SidebarInsightsResponse.model_validate(repaired)

        if len(repaired.sidebar_metrics) < 2:
            metrics_only = self._analyze_sidebar_metrics_with_langchain(article, analysis_result)
            repaired = repaired.model_copy(
                update={"sidebar_metrics": metrics_only.sidebar_metrics}
            )
        return repaired

    def _analyze_sidebar_metrics_with_langchain(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> SidebarMetricsResponse:
        raw_result = self._analyze_sidebar_metrics_with_raw_json(article, analysis_result)
        if len(raw_result.sidebar_metrics) >= 2:
            return raw_result

        llm = self._build_langchain_model()
        structured_llm = llm.with_structured_output(SidebarMetricsResponse)
        result = structured_llm.invoke(self._build_sidebar_metrics_prompt(article, analysis_result))
        if not isinstance(result, SidebarMetricsResponse):
            result = SidebarMetricsResponse.model_validate(result)
        if len(result.sidebar_metrics) >= len(raw_result.sidebar_metrics):
            return result
        if len(raw_result.sidebar_metrics) >= len(result.sidebar_metrics):
            return raw_result
        return result

    def _analyze_sidebar_metrics_with_raw_json(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> SidebarMetricsResponse:
        llm = self._build_langchain_model()
        raw_response = llm.invoke(self._build_sidebar_metrics_prompt(article, analysis_result))
        raw_content = getattr(raw_response, "content", raw_response)
        if isinstance(raw_content, list):
            raw_content = "\n".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in raw_content
            )
        parsed = self._parse_json_block(str(raw_content))
        return SidebarMetricsResponse.model_validate(parsed)

    def _build_langchain_model(self) -> object:
        """Vertex AI 환경에서 analyzer LLM을 만든다."""
        if not getenv.GOOGLE_CLOUD_PROJECT:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT 환경변수가 필요합니다.")

        return ChatGoogleGenerativeAI(
            model=getenv.VERTEX_MODEL,
            vertexai=True,
            project=getenv.GOOGLE_CLOUD_PROJECT,
            location=getenv.GOOGLE_CLOUD_LOCATION,
            temperature=0,
        )

    def _build_prompt(self, article: AnalysisRequest) -> str:
        """대표 기사 본문은 중심, context는 보조라는 원칙으로 최종 프롬프트를 만든다."""
        metadata_payload = {
            "cluster_id": article.cluster_id,
            "cluster_size": article.cluster_size,
            "summary_hint": article.summary_hint,
            "company_names": article.metadata.company_names,
            "sectors": article.metadata.sectors,
            "keywords": article.metadata.keywords,
            "source_titles": article.source_titles,
            "market_context": article.context.model_dump(),
        }
        example_output = {
            "article_id": article.article_id,
            "summary": "이 뉴스를 이해하는 데 필요한 핵심 사실, 원인, 시장 반응, 해석, 시사점을 담은 설명형 문단",
            "selected_issue_candidates": [
                "핵심 이슈 후보 1",
                "핵심 이슈 후보 2",
            ],
            "issue_selection_reason": "왜 이 이슈를 핵심으로 봤는지",
            "summary_points": [
                "핵심 요약 포인트 1",
                "핵심 요약 포인트 2",
            ],
            "evidence_sentences": [
                "핵심 포인트를 뒷받침하는 기사 원문 문장 1",
                "핵심 포인트를 뒷받침하는 기사 원문 문장 2",
            ],
            "analysis_sections": [
                {
                    "title": "ETF 시장 점유율 경쟁이 다시 뜨거워진 이유",
                    "summary": "2~4문장 이내의 짧은 분석 문단입니다.",
                },
                {
                    "title": "히트 상품이 실제 점유율 확대로 이어지는지",
                    "summary": "2~4문장 이내의 짧은 분석 문단입니다.",
                },
                {
                    "title": "지속 여부를 가를 다음 체크포인트",
                    "summary": "중복 없이 다른 역할을 하는 분석 문단입니다.",
                },
            ],
            "risk_factors": [
                "기사에서 읽을 수 있는 위험 요인",
            ],
            "opportunity_factors": [
                "기사에서 읽을 수 있는 기회 요인",
            ],
        }
        return f"""{SYSTEM_PROMPT}

출력 형식:
{json.dumps(example_output, ensure_ascii=False, indent=2)}

입력 메타데이터와 cluster payload 문맥:
{json.dumps(metadata_payload, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}
"""

    def _build_sidebar_prompt(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> str:
        analysis_payload = {
            "summary": analysis_result.summary,
            "summary_points": analysis_result.summary_points,
            "analysis_sections": [section.model_dump() for section in analysis_result.analysis_sections],
            "selected_issue_candidates": analysis_result.selected_issue_candidates,
        }
        example_output = {
            "sidebar_markets": [
                {
                    "name": "ETF 시장",
                    "summary": "단순 인기보다 자금 유입이 실제 점유율 확대로 이어지는지 보는 편이 더 중요합니다.",
                }
            ],
            "sidebar_metrics": [
                {
                    "label": "시장 점유율 변화",
                    "value": "7.03% → 7.11%",
                    "emphasis": "+0.08%p 변화",
                },
                {
                    "label": "연초 이후 순자산 증가율",
                    "value": "58.81%",
                    "emphasis": "기사 기준",
                },
                {
                    "label": "ETF 순자산 총액",
                    "value": "33조3149억원",
                    "emphasis": "기사 기준",
                },
            ],
        }

        return f"""{SIDEBAR_SYSTEM_PROMPT}

출력 형식:
{json.dumps(example_output, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}

메인 분석 결과:
{json.dumps(analysis_payload, ensure_ascii=False, indent=2)}
"""

    def _build_analysis_sections_repair_prompt(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> str:
        payload = {
            "summary": analysis_result.summary,
            "summary_points": analysis_result.summary_points,
            "selected_issue_candidates": analysis_result.selected_issue_candidates,
            "issue_selection_reason": analysis_result.issue_selection_reason,
        }
        example_output = {
            "analysis_sections": [
                {
                    "title": "ETF 시장 점유율 경쟁이 다시 뜨거워진 이유",
                    "summary": "기사에서 실제로 어떤 변화가 나타났는지 2~4문장으로 설명합니다.",
                },
                {
                    "title": "히트 상품이 실제 점유율 확대로 이어지는지",
                    "summary": "이 변화가 왜 중요한지, 시장이 무엇을 중심으로 해석하는지 2~4문장으로 설명합니다.",
                },
                {
                    "title": "지속 여부를 가를 다음 체크포인트",
                    "summary": "지금 추가로 확인해야 할 변수나 체크포인트를 2~4문장으로 설명합니다.",
                },
            ]
        }

        return f"""{ANALYSIS_SECTIONS_REPAIR_PROMPT}

출력 형식:
{json.dumps(example_output, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}

이미 생성된 요약 정보:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""

    def _build_sidebar_repair_prompt(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
        previous_result: SidebarInsightsResponse,
    ) -> str:
        analysis_payload = {
            "summary": analysis_result.summary,
            "summary_points": analysis_result.summary_points,
            "analysis_sections": [section.model_dump() for section in analysis_result.analysis_sections],
            "selected_issue_candidates": analysis_result.selected_issue_candidates,
        }
        previous_payload = previous_result.model_dump()
        numeric_candidates = self._collect_numeric_fact_candidates(article, analysis_result)

        return f"""{SIDEBAR_SYSTEM_PROMPT}

추가 지시:
- 이전 응답에서 sidebar가 불완전했다.
- 이번에는 sidebar_markets를 최소 1개, sidebar_metrics를 반드시 2개 또는 3개 작성한다.
- sidebar_metrics는 기사에 실제 나온 숫자만 사용한다.
- ETF 기사라면 점유율 변화, 순자산 증가율, ETF 순자산 총액처럼 기사 핵심을 설명하는 숫자를 우선한다.

이전 응답:
{json.dumps(previous_payload, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}

메인 분석 결과:
{json.dumps(analysis_payload, ensure_ascii=False, indent=2)}

수치 후보 문장:
{json.dumps(numeric_candidates, ensure_ascii=False, indent=2)}
"""

    def _build_sidebar_metrics_prompt(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> str:
        analysis_payload = {
            "summary": analysis_result.summary,
            "summary_points": analysis_result.summary_points,
            "analysis_sections": [section.model_dump() for section in analysis_result.analysis_sections],
            "evidence_sentences": analysis_result.evidence_sentences,
        }
        numeric_candidates = self._collect_numeric_fact_candidates(article, analysis_result)
        example_output = {
            "sidebar_metrics": [
                {
                    "label": "시장 점유율 변화",
                    "value": "7.03% → 7.11%",
                    "emphasis": "+0.08%p 변화",
                },
                {
                    "label": "연초 이후 순자산 증가율",
                    "value": "58.81%",
                    "emphasis": "기사 기준",
                },
                {
                    "label": "ETF 순자산 총액",
                    "value": "33조3149억원",
                    "emphasis": "기사 기준",
                },
            ]
        }

        return f"""{SIDEBAR_METRICS_SYSTEM_PROMPT}

이번 응답에서는 기사 본문 전체보다 아래 "수치 후보 문장"을 우선적으로 사용한다.
반드시 그 후보 안에 실제로 나온 숫자 중에서 2개 또는 3개를 골라 작성한다.

출력 형식:
{json.dumps(example_output, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}

메인 분석 결과:
{json.dumps(analysis_payload, ensure_ascii=False, indent=2)}

수치 후보 문장:
{json.dumps(numeric_candidates, ensure_ascii=False, indent=2)}
"""

    def _parse_json_block(self, raw_text: str) -> dict:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("LLM JSON 응답을 찾지 못했습니다.")

        return json.loads(cleaned[start : end + 1])

    def _collect_numeric_fact_candidates(
        self,
        article: AnalysisRequest,
        analysis_result: LLMAnalysisResponse,
    ) -> list[str]:
        candidates: list[str] = []
        seen: set[str] = set()

        for text in [*analysis_result.evidence_sentences, *analysis_result.summary_points]:
            normalized = str(text or "").strip()
            if not normalized or normalized in seen or not re.search(r"\d", normalized):
                continue
            seen.add(normalized)
            candidates.append(normalized)

        for sentence in re.split(r"(?<=[.!?。])\s+|\n+", article.content):
            normalized = str(sentence or "").strip()
            if not normalized or normalized in seen or not re.search(r"\d", normalized):
                continue
            if len(normalized) < 12:
                continue
            seen.add(normalized)
            candidates.append(normalized)
            if len(candidates) >= 8:
                break

        return candidates[:8]

    def _finalize_response(
        self,
        article: AnalysisRequest,
        result: LLMAnalysisResponse,
        sidebar_result: SidebarInsightsResponse,
    ) -> AnalysisResponse:
        """LLM 1차 결과와 정형 sidebar를 묶어 최종 AnalysisResponse를 만든다."""
        analysis_summary = self._build_analysis_summary(article, result)
        sidebar_context = self._build_sidebar_context(article, sidebar_result)
        return AnalysisResponse(
            cluster_id=article.cluster_id,
            analysis_summary=analysis_summary,
            market_context=article.context,
            sidebar_context=sidebar_context,
        )

    def build_sidebar_context(self, article: AnalysisRequest) -> SidebarContext:
        """메인 분석과 별개로 sidebar만 다시 조회할 때 쓰는 진입점이다."""
        return self._build_sidebar_context(article)

    def _build_analysis_summary(self, article: AnalysisRequest, result: LLMAnalysisResponse) -> AnalysisSummary:
        """중복을 정리하고 프론트 메인 분석 블록 모양으로 다시 묶는다."""
        return AnalysisSummary(
            summary=result.summary,
            selected_issue_candidates=self._dedupe_strings(result.selected_issue_candidates),
            issue_selection_reason=result.issue_selection_reason,
            summary_points=self._dedupe_strings(result.summary_points),
            evidence_sentences=self._dedupe_strings(result.evidence_sentences),
            analysis_sections=self._normalize_analysis_sections(result),
            risk_factors=self._dedupe_strings(result.risk_factors),
            opportunity_factors=self._dedupe_strings(result.opportunity_factors),
        )

    def _normalize_analysis_sections(
        self,
        result: LLMAnalysisResponse,
    ) -> list[AnalysisSection]:
        """section 수와 중복을 정리해 프론트가 바로 쓸 수 있게 맞춘다."""
        sections: list[AnalysisSection] = []
        seen_titles: set[str] = set()
        seen_summaries: set[str] = set()

        for section in result.analysis_sections:
            title = str(section.title).strip()
            summary = str(section.summary).strip()
            if not title or not summary:
                continue
            if title in seen_titles or summary in seen_summaries:
                continue
            seen_titles.add(title)
            seen_summaries.add(summary)
            sections.append(AnalysisSection(title=title, summary=summary))

        return sections[:4]

    def _build_sidebar_context(
        self,
        article: AnalysisRequest,
        sidebar_result: SidebarInsightsResponse | None = None,
    ) -> SidebarContext:
        """회사/시장/핵심 숫자를 우측 sidebar 카드 구조로 조립한다."""
        related_companies = [
            RelatedCompanyCard(
                name=company.name,
                ticker=company.ticker,
                sector=company.sector,
                current_price=company.metrics.get("current_price") or company.metrics.get("price") or company.metrics.get("close_price"),
                price_change_pct=company.metrics.get("price_change_pct"),
            )
            for company in article.context.companies
            if company.name
            and (
                company.ticker
                or company.sector
                or company.metrics.get("current_price")
                or company.metrics.get("price")
                or company.metrics.get("close_price")
                or company.metrics.get("price_change_pct")
            )
        ]
        related_markets = [
            RelatedMarketCard(
                name=indicator.name,
                value=indicator.value,
                change_pct=indicator.change,
                summary=None,
            )
            for indicator in article.context.market_indicators
        ]
        related_markets = self._merge_sidebar_market_insights(
            related_markets,
            self._normalize_sidebar_markets(article, sidebar_result),
        )
        return SidebarContext(
            related_companies=related_companies,
            related_markets=related_markets,
            key_metrics=self._build_sidebar_key_metrics(article, sidebar_result),
        )

    def _normalize_sidebar_markets(
        self,
        article: AnalysisRequest,
        result: SidebarInsightsResponse | None,
    ) -> list[RelatedMarketCard]:
        if result is None:
            return []

        fallback_name = self._guess_primary_market_name(article)
        normalized: list[RelatedMarketCard] = []
        seen_names: set[str] = set()

        for market in result.sidebar_markets:
            name = str(market.name or "").strip() or fallback_name
            summary = str(market.summary or "").strip()
            if not name or not summary or name in seen_names:
                continue
            seen_names.add(name)
            normalized.append(
                RelatedMarketCard(
                    name=name,
                    summary=summary,
                )
            )

        return normalized[:2]

    def _merge_sidebar_market_insights(
        self,
        base_markets: list[RelatedMarketCard],
        llm_markets: list[RelatedMarketCard],
    ) -> list[RelatedMarketCard]:
        merged_by_name: dict[str, RelatedMarketCard] = {}
        ordered_names: list[str] = []

        for market in [*base_markets, *llm_markets]:
            if not market.name:
                continue
            existing = merged_by_name.get(market.name)
            if existing is None:
                merged_by_name[market.name] = market
                ordered_names.append(market.name)
                continue
            merged_by_name[market.name] = existing.model_copy(
                update={
                    "value": existing.value or market.value,
                    "change_pct": existing.change_pct or market.change_pct,
                    "summary": existing.summary or market.summary,
                }
            )

        return [merged_by_name[name] for name in ordered_names]

    def _guess_primary_market_name(self, article: AnalysisRequest) -> str | None:
        joined_text = " ".join(
            [
                article.title or "",
                article.content,
                *article.metadata.sectors,
                *article.metadata.keywords,
            ]
        )

        if "ETF" in joined_text.upper():
            return "ETF 시장"
        if "반도체" in joined_text:
            return "반도체"
        if "코스피" in joined_text:
            return "KOSPI"
        if "코스닥" in joined_text:
            return "KOSDAQ"
        if article.metadata.sectors:
            return article.metadata.sectors[0]
        if article.context.sectors:
            return article.context.sectors[0].name
        return None

    def _build_sidebar_key_metrics(
        self,
        article: AnalysisRequest,
        result: SidebarInsightsResponse | None = None,
    ) -> list[KeyMetric]:
        """수치 카드는 기사 유형에 맞는 의미형 카드로 만들고, 저장된 근거 데이터를 우선 사용한다."""
        issue_type = self._classify_issue_type(article)
        context_metrics = self._build_context_key_metrics(article, issue_type)
        story_anchor_metrics = self._extract_story_anchor_metrics(article)
        llm_metrics = self._normalize_sidebar_metrics(result)
        fallback_metrics = self._build_article_fallback_key_metrics(article, issue_type)
        if len(story_anchor_metrics) >= 2:
            return self._merge_key_metrics(story_anchor_metrics, context_metrics, fallback_metrics, llm_metrics)[:3]
        if issue_type in {"launch", "supply", "general"}:
            return self._merge_key_metrics(fallback_metrics, context_metrics, llm_metrics)[:3]
        return self._merge_key_metrics(context_metrics, fallback_metrics, llm_metrics)[:3]

    def _build_context_key_metrics(
        self,
        article: AnalysisRequest,
        issue_type: str,
    ) -> list[KeyMetric]:
        has_context_overlap = self._has_context_company_overlap(article)
        launch_structure_metrics = self._build_launch_structure_metrics(article)
        comparison_metrics = self._build_financial_comparison_metrics(article) if has_context_overlap else []
        company_status_metrics = self._build_company_status_metrics(article) if has_context_overlap else []
        market_status_metrics = self._build_market_status_metrics(article)

        group_map = {
            "launch_structure": launch_structure_metrics,
            "comparison": comparison_metrics,
            "company_status": company_status_metrics,
            "market_status": market_status_metrics,
        }
        group_order = {
            "launch": ["launch_structure", "comparison", "company_status", "market_status"],
            "earnings": ["comparison", "company_status", "market_status"],
            "market": ["market_status", "company_status", "comparison"],
            "policy": ["market_status", "comparison", "company_status"],
            "supply": ["company_status", "comparison", "market_status"],
            "general": ["comparison", "company_status", "market_status"],
        }

        ordered: list[KeyMetric] = []
        for group_name in group_order.get(issue_type, group_order["general"]):
            ordered.extend(group_map[group_name])

        return self._dedupe_key_metrics(ordered)

    def _build_launch_structure_metrics(self, article: AnalysisRequest) -> list[KeyMetric]:
        """출시/상장/상품 구조 기사에서는 기사 구조 자체를 설명하는 숫자를 우선 카드화한다."""
        metrics: list[KeyMetric] = []
        seen_labels: set[str] = set()
        sentences = self._split_sentences(article.content)

        for sentence in sentences:
            if "출시" in sentence or "상장" in sentence or "첫선" in sentence:
                date_match = re.search(r"(\d+월\s*\d+일|\d+일)", sentence)
                if date_match and "출시 예정일" not in seen_labels:
                    seen_labels.add("출시 예정일")
                    emphasis = "단일종목 ETF 출시 일정"
                    if "첫선" in sentence:
                        emphasis = "국내 첫 단일종목 ETF 출시"
                    metrics.append(
                        KeyMetric(
                            label="출시 예정일",
                            value=date_match.group(1).replace(" ", ""),
                            emphasis=emphasis,
                        )
                    )

            if any(token in sentence for token in ["추종", "레버리지", "인버스"]):
                if re.search(r"2배\s*또는\s*-2배", sentence) and "레버리지 배율" not in seen_labels:
                    seen_labels.add("레버리지 배율")
                    metrics.append(
                        KeyMetric(
                            label="레버리지 배율",
                            value="±2배",
                            emphasis="기초자산 일간 수익률 추종 구조",
                        )
                    )
                else:
                    leverage_match = re.search(r"([+-]?\d+(?:\.\d+)?)배", sentence)
                    if leverage_match and "레버리지 배율" not in seen_labels:
                        seen_labels.add("레버리지 배율")
                        metrics.append(
                            KeyMetric(
                                label="레버리지 배율",
                                value=f"{leverage_match.group(1)}배",
                                emphasis="기초자산 일간 수익률 추종 구조",
                            )
                        )
                    inverse_match = re.search(r"-\s*(\d+(?:\.\d+)?)배", sentence)
                    if inverse_match and "인버스 배율" not in seen_labels:
                        seen_labels.add("인버스 배율")
                        metrics.append(
                            KeyMetric(
                                label="인버스 배율",
                                value=f"-{inverse_match.group(1)}배",
                                emphasis="하락 방향 추종 구조",
                            )
                        )

            manager_match = re.search(r"(\d+)개\s*운용사", sentence)
            if manager_match and "참여 운용사 수" not in seen_labels:
                seen_labels.add("참여 운용사 수")
                emphasis = "동시 출시 예정"
                if "레버리지" in sentence:
                    emphasis = "대다수 레버리지 상품"
                metrics.append(
                    KeyMetric(
                        label="참여 운용사 수",
                        value=f"{manager_match.group(1)}개사",
                        emphasis=emphasis,
                    )
                )

        return metrics[:3]

    def _build_financial_comparison_metrics(self, article: AnalysisRequest) -> list[KeyMetric]:
        anchor = self._select_financial_anchor_company(article)
        if anchor is None:
            return []

        specs = [
            ("operating_income", "영업이익", "operating_income_yoy_pct"),
            ("revenue", "매출", "revenue_yoy_pct"),
            ("net_income", "순이익", "net_income_yoy_pct"),
        ]
        built: list[KeyMetric] = []
        financial_year = anchor.metrics.get("financial_year")

        for metric_key, label, yoy_key in specs:
            value = anchor.metrics.get(metric_key)
            if not value:
                continue

            basis_parts: list[str] = []
            if financial_year:
                basis_parts.append(f"{financial_year}년 기준")

            yoy_pct = anchor.metrics.get(yoy_key)
            if yoy_pct:
                basis_parts.append(f"전년 대비 {yoy_pct}")

            built.append(
                KeyMetric(
                    label=f"{anchor.name} {label}",
                    value=value,
                    emphasis=" · ".join(basis_parts) or None,
                )
            )

        return built

    def _build_company_status_metrics(self, article: AnalysisRequest) -> list[KeyMetric]:
        metrics: list[KeyMetric] = []

        for company in article.context.companies:
            current_price = (
                company.metrics.get("current_price")
                or company.metrics.get("price")
                or company.metrics.get("close_price")
            )
            change_pct = company.metrics.get("price_change_pct")
            if not current_price and not change_pct:
                continue

            value = current_price or change_pct or ""
            emphasis = None
            if current_price and change_pct:
                emphasis = f"조회 시점 등락률 {change_pct}"
            elif change_pct:
                emphasis = "조회 시점 주가 반응"
            elif current_price:
                emphasis = "조회 시점 반영"

            metrics.append(
                KeyMetric(
                    label=f"{company.name} 주가",
                    value=value,
                    emphasis=emphasis,
                )
            )

        return metrics[:2]

    def _build_market_status_metrics(self, article: AnalysisRequest) -> list[KeyMetric]:
        metrics: list[KeyMetric] = []

        for indicator in article.context.market_indicators:
            if not indicator.name:
                continue

            value = indicator.value or indicator.change or ""
            if not value:
                continue

            emphasis = None
            if indicator.value and indicator.change:
                emphasis = f"조회 시점 등락률 {indicator.change}"
            elif indicator.change:
                emphasis = "조회 시점 시장 흐름"
            elif indicator.value:
                emphasis = "조회 시점 반영"

            label = (
                f"{indicator.name} 지수"
                if indicator.name.upper() in {"KOSPI", "KOSDAQ", "NASDAQ"}
                else indicator.name
            )
            metrics.append(
                KeyMetric(
                    label=label,
                    value=value,
                    emphasis=emphasis,
                )
            )

        return metrics[:1]

    def _build_article_fallback_key_metrics(
        self,
        article: AnalysisRequest,
        issue_type: str,
    ) -> list[KeyMetric]:
        primary_market = self._select_primary_market(article)
        return self._extract_article_key_metrics(article, issue_type, primary_market)

    def _merge_key_metrics(self, *metric_groups: list[KeyMetric]) -> list[KeyMetric]:
        merged: list[KeyMetric] = []
        seen: set[tuple[str, str]] = set()
        seen_labels: set[str] = set()

        for group in metric_groups:
            for metric in group:
                label = str(metric.label).strip()
                value = str(metric.value).strip()
                if not label or not value:
                    continue
                key = (label, value)
                if key in seen or label in seen_labels:
                    continue
                seen.add(key)
                seen_labels.add(label)
                merged.append(metric)

        return merged

    def _dedupe_key_metrics(self, metrics: list[KeyMetric]) -> list[KeyMetric]:
        return self._merge_key_metrics(metrics)

    def _normalize_sidebar_metrics(
        self,
        result: SidebarInsightsResponse | None,
    ) -> list[KeyMetric]:
        if result is None:
            return []

        normalized: list[KeyMetric] = []
        seen: set[tuple[str, str]] = set()

        for metric in result.sidebar_metrics:
            label = str(metric.label or "").strip()
            value = str(metric.value or "").strip()
            emphasis = str(metric.emphasis or "").strip() or None
            if not label or not value:
                continue
            key = (label, value)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                KeyMetric(
                    label=label,
                    value=value,
                    emphasis=emphasis,
                )
            )

        return normalized[:3]

    def _classify_issue_type(self, article: AnalysisRequest) -> str:
        article_text = " ".join([article.title or "", article.content])
        haystack = " ".join(
            [
                article_text,
                *article.metadata.keywords,
                *article.metadata.sectors,
            ]
        )
        has_company = bool(article.context.companies or article.metadata.company_names)
        market_tokens = [
            "코스피",
            "코스닥",
            "지수",
            "급락",
            "급등",
            "외국인",
            "순매도",
            "변동성",
            "환율",
            "대차",
            "수급",
        ]
        earnings_tokens = [
            "실적",
            "매출",
            "영업이익",
            "순이익",
            "컨센서스",
            "가이던스",
            "어닝",
        ]
        launch_tokens = [
            "출시",
            "상장",
            "첫선",
            "레버리지",
            "인버스",
            "추종",
            "etf",
            "운용사",
            "리밸런싱",
        ]
        supply_tokens = [
            "지분",
            "주요주주",
            "공급",
            "수주",
            "공정",
            "증설",
            "capex",
            "설비투자",
            "계약",
            "채택",
        ]
        policy_tokens = [
            "정책",
            "규제",
            "정부",
            "금리",
            "관세",
            "지원",
            "법안",
            "재정",
            "환율",
        ]

        lowered = haystack.lower()

        if not has_company and article.context.market_indicators:
            return "market"
        if "etf" in article_text.lower() and any(token in article_text.lower() for token in launch_tokens):
            return "launch"
        if any(token in lowered for token in supply_tokens):
            return "supply"
        corporate_tokens = [
            "매각",
            "인수",
            "m&a",
            "최대주주",
            "몸값",
            "재시동",
        ]
        if has_company and any(token in lowered for token in corporate_tokens):
            return "general"
        if has_company and any(token in haystack for token in earnings_tokens):
            return "earnings"
        if any(token in haystack for token in policy_tokens):
            return "policy"
        if any(token in haystack for token in market_tokens):
            return "market"
        return "general"

    def _extract_article_key_metrics(
        self,
        article: AnalysisRequest,
        issue_type: str,
        primary_market: RelatedMarketCard | None,
    ) -> list[KeyMetric]:
        candidates_by_group: dict[str, list[KeyMetric]] = {
            "story_anchor": self._extract_story_anchor_metrics(article),
            "range_pct": [],
            "single_pct": [],
            "count_change": [],
            "financial_amount": [],
            "flow_amount": [],
            "price_reaction": [],
            "market_value": [],
        }

        sentences = self._split_sentences(article.content)
        companies = article.context.companies

        for sentence in sentences:
            for metric in self._extract_percent_range_metrics(sentence):
                candidates_by_group["range_pct"].append(metric)
            for metric in self._extract_single_percent_metrics(sentence):
                candidates_by_group["single_pct"].append(metric)
            for metric in self._extract_count_change_metrics(sentence):
                candidates_by_group["count_change"].append(metric)
            for metric in self._extract_financial_amount_metrics(sentence, article):
                candidates_by_group["financial_amount"].append(metric)
            for metric in self._extract_flow_amount_metrics(sentence):
                candidates_by_group["flow_amount"].append(metric)
            for metric in self._extract_company_reaction_metrics(sentence, companies, primary_market):
                candidates_by_group["price_reaction"].append(metric)
            for metric in self._extract_market_sentence_metrics(sentence, primary_market):
                candidates_by_group["market_value"].append(metric)

        group_order = {
            "launch": ["story_anchor", "count_change", "range_pct", "single_pct", "financial_amount", "price_reaction", "market_value", "flow_amount"],
            "market": ["story_anchor", "flow_amount", "price_reaction", "market_value", "range_pct", "single_pct", "count_change", "financial_amount"],
            "earnings": ["story_anchor", "financial_amount", "price_reaction", "range_pct", "single_pct", "count_change", "market_value", "flow_amount"],
            "supply": ["story_anchor", "range_pct", "count_change", "single_pct", "financial_amount", "price_reaction", "market_value", "flow_amount"],
            "policy": ["story_anchor", "flow_amount", "market_value", "price_reaction", "range_pct", "single_pct", "financial_amount", "count_change"],
            "general": ["story_anchor", "range_pct", "single_pct", "count_change", "financial_amount", "price_reaction", "market_value", "flow_amount"],
        }

        ordered: list[KeyMetric] = []
        for group in group_order.get(issue_type, group_order["general"]):
            ordered.extend(candidates_by_group[group])

        deduped: list[KeyMetric] = []
        seen: set[tuple[str, str]] = set()
        seen_labels: set[str] = set()
        for metric in ordered:
            key = (metric.label.strip(), metric.value.strip())
            label_key = metric.label.strip()
            if key in seen or label_key in seen_labels:
                continue
            seen.add(key)
            seen_labels.add(label_key)
            deduped.append(metric)

        return deduped[:3]

    def _extract_story_anchor_metrics(self, article: AnalysisRequest) -> list[KeyMetric]:
        """대표 기사 자체에서 가장 먼저 읽히는 핵심 숫자를 우선 카드화한다."""
        text = " ".join([article.title or "", article.content])
        metrics: list[KeyMetric] = []

        high_match = re.search(
            r"((?:\d+\s*조\s*)?(?:\d+\s*억\s*)?(?:\d+\s*만\s*)?\d[\d,]*)원까지\s*상승하며[^.\n]{0,12}(?:신고가|역사적 신고가)",
            text,
        )
        rise_match = re.search(
            r"전\s*거래일\s*(?:대비|보다)\s*((?:[+-]?(?:\d+\s*조\s*)?(?:\d+\s*억\s*)?(?:\d+\s*만\s*)?\d[\d,]*)원)?\s*\(?([+-]?\d+(?:\.\d+)?)%\)?\s*(상승|하락)",
            text,
        )
        if high_match:
            emphasis = "역사적 신고가 경신"
            if rise_match:
                pct = rise_match.group(2)
                direction = rise_match.group(3)
                pct_text = f"+{pct}%" if direction == "상승" and not pct.startswith(("+", "-")) else f"-{pct}%" if direction == "하락" and not pct.startswith(("+", "-")) else f"{pct}%"
                emphasis = f"전 거래일 대비 {pct_text}"
            metrics.append(
                KeyMetric(
                    label="장중 신고가",
                    value=f"{high_match.group(1)}원",
                    emphasis=emphasis,
                )
            )

        target_avg_match = re.search(r"목표주가\s*평균치(?:는)?\s*(\d[\d,]*)원", text)
        target_high_match = re.search(r"최고치(?:는)?\s*(\d[\d,]*)원", text)
        if target_avg_match:
            emphasis = None
            if target_high_match:
                emphasis = f"최고치 {target_high_match.group(1)}원"
            metrics.append(
                KeyMetric(
                    label="목표주가 평균",
                    value=f"{target_avg_match.group(1)}원",
                    emphasis=emphasis,
                )
            )

        profit_projection_match = re.search(
            r"영업이익\s*추정치(?:를)?\s*각각\s*(\d조\s*\d+,?\d*억원|\d조원|\d+,?\d*억원),\s*(\d조\s*\d+,?\d*억원|\d조원|\d+,?\d*억원)",
            text,
        )
        if profit_projection_match:
            metrics.append(
                KeyMetric(
                    label="올해 영업이익 추정",
                    value=profit_projection_match.group(1).replace(" ", ""),
                    emphasis=f"내년 추정치 {profit_projection_match.group(2).replace(' ', '')}",
                )
            )

        new_clients_match = re.search(r"신규\s*(\d+)개사", text)
        if new_clients_match:
            metrics.append(
                KeyMetric(
                    label="기판 고객사 확대",
                    value=f"신규 {new_clients_match.group(1)}개사",
                    emphasis="북미 클라우드·GPU 고객 기반 확대",
                )
            )

        robot_match = re.search(r"미국\s*(\d+)대\s*휴머노이드", text)
        if robot_match:
            metrics.append(
                KeyMetric(
                    label="비전 센싱 고객 확대",
                    value=f"미국 {robot_match.group(1)}대 업체",
                    emphasis="휴머노이드 모듈 매출 기여 확인 필요",
                )
            )

        return metrics

    def _select_primary_market(self, article: AnalysisRequest) -> RelatedMarketCard | None:
        if not article.context.market_indicators:
            return None

        for indicator in article.context.market_indicators:
            if indicator.name.upper() == "KOSPI":
                return RelatedMarketCard(
                    name=indicator.name,
                    value=indicator.value,
                    change_pct=indicator.change,
                    summary=None,
                )

        indicator = article.context.market_indicators[0]
        return RelatedMarketCard(
            name=indicator.name,
            value=indicator.value,
            change_pct=indicator.change,
            summary=None,
        )

    def _select_financial_anchor_company(self, article: AnalysisRequest):
        preferred_company_names = self._extract_article_company_names(article)
        if preferred_company_names:
            for preferred_name in preferred_company_names:
                for company in article.context.companies:
                    if (
                        company.name == preferred_name
                        and any(company.metrics.get(key) for key in ("revenue", "operating_income", "net_income"))
                    ):
                        return company

        for company in article.context.companies:
            if any(company.metrics.get(key) for key in ("revenue", "operating_income", "net_income")):
                return company
        return None

    def _has_context_company_overlap(self, article: AnalysisRequest) -> bool:
        article_names = self._extract_article_company_names(article)
        if not article_names:
            return False
        context_names = {str(company.name).strip() for company in article.context.companies if str(company.name).strip()}
        return any(name in context_names for name in article_names)

    def _extract_article_company_names(self, article: AnalysisRequest) -> list[str]:
        text = " ".join([article.title or "", article.content])
        ordered_names: list[str] = []

        for name in article.metadata.company_names:
            normalized = str(name).strip()
            if normalized and normalized in text and normalized not in ordered_names:
                ordered_names.append(normalized)

        for company in article.context.companies:
            normalized = str(company.name).strip()
            if normalized and normalized in text and normalized not in ordered_names:
                ordered_names.append(normalized)

        return ordered_names

    def _build_market_value_metric(self, market: RelatedMarketCard | None) -> KeyMetric | None:
        if not market or not market.name:
            return None

        if market.value and market.change_pct:
            return KeyMetric(
                label=f"{market.name} 지수",
                value=market.value,
                emphasis=f"일간 등락률 {market.change_pct}",
            )
        if market.change_pct:
            return KeyMetric(
                label=f"{market.name} 등락률",
                value=market.change_pct,
                emphasis=None,
            )
        if market.value:
            return KeyMetric(
                label=f"{market.name} 지수",
                value=market.value,
                emphasis=None,
            )
        return None

    def _split_sentences(self, content: str) -> list[str]:
        collapsed = re.sub(r"\s+", " ", content or "").strip()
        if not collapsed:
            return []
        parts = re.split(r"(?<=[.!?다])\s+", collapsed)
        return [part.strip() for part in parts if part.strip()]

    def _extract_percent_range_metrics(self, sentence: str) -> list[KeyMetric]:
        metrics: list[KeyMetric] = []
        for match in re.finditer(r"(\d+(?:\.\d+)?)%\s*(?:에서|→|->|~)\s*(\d+(?:\.\d+)?)%", sentence):
            start = float(match.group(1))
            end = float(match.group(2))
            label = "지분 확대 속도" if any(token in sentence for token in ["지분", "주주"]) else "비율 변화"
            value = f"{match.group(1)}% → {match.group(2)}%"
            emphasis = f"{end - start:+.2f}%p 변화"
            metrics.append(KeyMetric(label=label, value=value, emphasis=emphasis))
        return metrics

    def _extract_count_change_metrics(self, sentence: str) -> list[KeyMetric]:
        metrics: list[KeyMetric] = []
        for match in re.finditer(r"(\d[\d,]*)\s*개\s*(?:에서|→|->|~)\s*(\d[\d,]*)\s*개", sentence):
            start = int(match.group(1).replace(",", ""))
            end = int(match.group(2).replace(",", ""))
            if any(token in sentence for token in ["공정", "적용"]):
                label = "적용 공정 수"
            elif any(token in sentence for token in ["공급", "채택"]):
                label = "공급 범위 변화"
            else:
                label = "수량 변화"
            value = f"{match.group(1)}개 → {match.group(2)}개"
            if start > 0:
                emphasis = f"약 {end / start:.1f}배 확대" if end >= start else f"약 {start / max(end, 1):.1f}배 축소"
            else:
                emphasis = f"{end - start:+,}개 변화"
            metrics.append(KeyMetric(label=label, value=value, emphasis=emphasis))
        return metrics

    def _extract_single_percent_metrics(self, sentence: str) -> list[KeyMetric]:
        metrics: list[KeyMetric] = []
        if re.search(r"\d+(?:\.\d+)?%\s*(?:에서|→|->|~)\s*\d+(?:\.\d+)?%", sentence):
            return metrics
        pct_match = re.search(r"(\d+(?:\.\d+)?)%", sentence)
        if not pct_match:
            return metrics

        pct_value = f"{pct_match.group(1)}%"
        lowered = sentence.lower()

        if "지분" in sentence or "주주" in sentence:
            label = "보유 지분"
            metrics.append(
                KeyMetric(
                    label=label,
                    value=pct_value,
                    emphasis=None,
                )
            )
            return metrics

        if "roe" in lowered:
            metrics.append(KeyMetric(label="ROE", value=pct_value, emphasis=None))

        return metrics

    def _extract_financial_amount_metrics(self, sentence: str, article: AnalysisRequest) -> list[KeyMetric]:
        metric_specs = [
            ("매출", "매출", "revenue"),
            ("영업이익", "영업이익", "operating_income"),
            ("순이익", "순이익", "net_income"),
            ("영업손실", "영업손실", "operating_income"),
            ("거래대금", "거래대금", None),
            ("거래량", "거래량", None),
            ("판매량", "판매량", None),
            ("목표주가", "목표주가", None),
            ("몸값", "예상 몸값", None),
            ("CSM", "CSM", None),
        ]
        metrics: list[KeyMetric] = []

        for token, label, financial_key in metric_specs:
            if token not in sentence:
                continue
            amount_text = self._extract_amount_near_token(sentence, token)
            if not amount_text:
                continue

            display_label = self._build_amount_label(label, sentence)
            emphasis = self._extract_growth_hint(sentence)

            if not emphasis and financial_key:
                anchor = self._select_financial_anchor_company(article)
                if anchor:
                    emphasis = self._build_financial_comparison_emphasis(
                        article_text_value=amount_text,
                        sentence=sentence,
                        financial_key=financial_key,
                        metrics=anchor.metrics,
                    )

            metrics.append(KeyMetric(label=display_label, value=amount_text, emphasis=emphasis))

        return metrics

    def _extract_flow_amount_metrics(self, sentence: str) -> list[KeyMetric]:
        metrics: list[KeyMetric] = []
        for actor in ("외국인", "기관", "개인"):
            for flow in ("순매수", "순매도"):
                token = f"{actor} {flow}"
                if token not in sentence:
                    continue
                amount_text = self._extract_amount_near_token(sentence, flow)
                if not amount_text:
                    continue
                metrics.append(KeyMetric(label=token, value=amount_text, emphasis=self._extract_growth_hint(sentence)))
        return metrics

    def _extract_company_reaction_metrics(
        self,
        sentence: str,
        companies: list,
        primary_market: RelatedMarketCard | None,
    ) -> list[KeyMetric]:
        if not any(token in sentence for token in ["상승", "하락", "올랐", "내렸", "반등", "강세", "약세", "급등", "급락"]):
            return []

        companies_in_sentence = [
            company.name
            for company in companies
            if company.name
            and company.name in sentence
            and (company.ticker or company.metrics.get("current_price") or company.metrics.get("price_change_pct"))
        ]
        if not companies_in_sentence:
            return []

        pct_matches = [match.group(0) for match in re.finditer(r"\d+(?:\.\d+)?%", sentence)]
        if not pct_matches:
            return []

        metrics: list[KeyMetric] = []
        for company_name, pct_text in zip(companies_in_sentence, pct_matches):
            normalized_pct = self._normalize_article_pct(pct_text, sentence)
            emphasis = self._build_article_price_emphasis(normalized_pct, primary_market)
            metrics.append(
                KeyMetric(
                    label=f"{company_name} 주가 반응",
                    value=normalized_pct,
                    emphasis=emphasis,
                )
            )
        return metrics

    def _extract_market_sentence_metrics(
        self,
        sentence: str,
        primary_market: RelatedMarketCard | None,
    ) -> list[KeyMetric]:
        if not primary_market:
            return []
        if primary_market.name not in sentence and "지수" not in sentence and "코스피" not in sentence and "코스닥" not in sentence:
            return []
        return [self._build_market_value_metric(primary_market)] if self._build_market_value_metric(primary_market) else []

    def _extract_amount_near_token(self, sentence: str, token: str) -> str | None:
        value_pattern = r"[+-]?[0-9천백십만억조.,]+(?:조\s*[0-9천백십만억조.,]+억\s*원|조\s*원|억원|억\s*원|원|만\s*장|장)(?:\s*(?:∼|~|\-|→|->)\s*[0-9천백십만억조.,]+(?:조\s*[0-9천백십만억조.,]+억\s*원|조\s*원|억원|억\s*원|원|만\s*장|장))?"
        patterns = [
            rf"{re.escape(token)}[은는이가\s:]*({value_pattern})",
            rf"({value_pattern})[^\n]{{0,6}}{re.escape(token)}",
        ]
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip()
        return None

    def _build_amount_label(self, label: str, sentence: str) -> str:
        quarter_match = re.search(r"(\d)분기", sentence)
        prefix = ""
        suffix = ""

        if label == "판매량":
            subject = self._extract_subject_for_metric(sentence)
            if subject:
                label = f"{subject} 판매량"

        if quarter_match and "판매량" not in label:
            prefix = f"{quarter_match.group(1)}분기 "
        elif "연간" in sentence or "올해" in sentence:
            prefix = "연간 "

        if any(token in sentence for token in ["예상", "전망", "예측", "가이던스"]):
            suffix = " 전망"
        if "누적" in sentence:
            prefix = f"{prefix}누적 "

        return f"{prefix}{label}{suffix}".strip()

    def _extract_growth_hint(self, sentence: str) -> str | None:
        patterns = [
            r"(전년\s*동기\s*대비\s*[+-]?\d+(?:\.\d+)?%)",
            r"(전년\s*대비\s*[+-]?\d+(?:\.\d+)?%)",
            r"(직전\s*분기\s*대비\s*[+-]?\d+(?:\.\d+)?%)",
            r"(전분기\s*대비\s*[+-]?\d+(?:\.\d+)?%)",
        ]
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match:
                return match.group(1).replace("  ", " ")
        return None

    def _build_financial_comparison_emphasis(
        self,
        article_text_value: str,
        sentence: str,
        financial_key: str,
        metrics: dict[str, str],
    ) -> str | None:
        financial_year = metrics.get("financial_year")
        anchor_value = metrics.get(financial_key)
        if not financial_year or not anchor_value:
            return None

        if any(sep in article_text_value for sep in ("∼", "~", "-")):
            return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value} 기준 가이던스"

        article_amount = self._parse_korean_amount(article_text_value)
        anchor_amount = self._parse_korean_amount(anchor_value)
        if article_amount is None or anchor_amount in (None, 0):
            return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value} 기준"

        if anchor_amount < 0 < article_amount:
            return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value} 적자 구간에서 흑자 전환 기대"
        if article_amount < 0 < anchor_amount:
            return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value} 흑자 구간 대비 적자 전환 우려"
        if anchor_amount < 0 and article_amount < 0:
            if abs(article_amount) < abs(anchor_amount):
                return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value} 대비 적자폭 축소"
            if abs(article_amount) > abs(anchor_amount):
                return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value} 대비 적자폭 확대"
            return f"{financial_year}년 연간 {self._financial_label(financial_key)} {anchor_value}와 유사한 적자 수준"

        if "분기" in sentence:
            share = (article_amount / anchor_amount) * 100
            return f"{financial_year}년 연간 {self._financial_label(financial_key)}의 {share:.1f}% 수준"

        diff_pct = ((article_amount - anchor_amount) / abs(anchor_amount)) * 100
        direction = "상회" if diff_pct > 0 else "하회" if diff_pct < 0 else "동일"
        if abs(diff_pct) < 0.1:
            return f"{financial_year}년 연간 {self._financial_label(financial_key)}와 유사"
        return f"{financial_year}년 연간 {self._financial_label(financial_key)} 대비 {diff_pct:+.1f}% {direction}"

    def _normalize_article_pct(self, pct_text: str, sentence: str) -> str:
        pct_text = pct_text.strip()
        if pct_text.startswith(("+", "-")):
            return pct_text
        if any(token in sentence for token in ["상승", "올랐", "반등", "강세", "급등"]):
            return f"+{pct_text}"
        if any(token in sentence for token in ["하락", "내렸", "약세", "급락"]):
            return f"-{pct_text}"
        return pct_text

    def _build_article_price_emphasis(
        self,
        article_change_pct: str,
        market: RelatedMarketCard | None,
    ) -> str | None:
        if not market or not market.change_pct:
            return "기사 기준 주가 반응"
        article_change = self._parse_pct(article_change_pct)
        market_change = self._parse_pct(market.change_pct)
        if article_change is None or market_change is None:
            return f"{market.name}({market.change_pct}) 비교 기준"
        diff = article_change - market_change
        direction = "강세" if diff > 0 else "약세" if diff < 0 else "동일"
        if direction == "동일":
            return f"{market.name}({market.change_pct})와 유사한 흐름"
        return f"{market.name}({market.change_pct}) 대비 {self._format_diff_pct(diff)} {direction}"

    def _parse_korean_amount(self, value: str | None) -> int | None:
        if not value:
            return None
        text = str(value).replace(" ", "").replace(",", "")
        sign = -1 if text.startswith("-") else 1
        text = text.lstrip("+-")

        total = 0
        jo_match = re.search(r"(\d+(?:\.\d+)?)조", text)
        uk_match = re.search(r"(\d+(?:\.\d+)?)억", text)
        won_match = re.search(r"(\d+(?:\.\d+)?)원", text)
        man_jang_match = re.search(r"(\d+(?:\.\d+)?)만장", text)
        jang_match = re.search(r"(\d+(?:\.\d+)?)장", text)

        if jo_match or uk_match:
            if jo_match:
                total += int(float(jo_match.group(1)) * 1000000000000)
            if uk_match:
                total += int(float(uk_match.group(1)) * 100000000)
            return sign * total
        if man_jang_match:
            return sign * int(float(man_jang_match.group(1)) * 10000)
        if jang_match:
            return sign * int(float(jang_match.group(1)))
        if won_match:
            return sign * int(float(won_match.group(1)))
        return None

    def _extract_subject_for_metric(self, sentence: str) -> str | None:
        quoted = re.search(r"'([^']+)'[^.\n]{0,12}판매량", sentence)
        if quoted:
            return quoted.group(1).strip()
        plain = re.search(r"([A-Za-z0-9가-힣]+)[^.\n]{0,8}판매량", sentence)
        if plain:
            subject = plain.group(1).strip()
            if subject not in {"판매량", "누적", "초기", "기록"}:
                return subject
        return None

    def _extract_share_subject(self, sentence: str) -> str | None:
        patterns = [
            r"([A-Za-z0-9가-힣]+)[^.\n]{0,8}지분",
            r"([A-Za-z0-9가-힣]+)[^.\n]{0,8}주주",
        ]
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match:
                subject = match.group(1).strip()
                subject = re.sub(r"(이|가|은|는|을|를)$", "", subject)
                if subject not in {"지분", "주주", "보유", "확대"}:
                    return subject
        return None

    def _financial_label(self, financial_key: str) -> str:
        return {
            "revenue": "매출",
            "operating_income": "영업이익",
            "net_income": "순이익",
        }.get(financial_key, financial_key)

    def _extract_key_numbers(self, article: AnalysisRequest) -> list[str]:
        numbers: list[str] = []
        for company in article.context.companies:
            company_metric_text = self._format_company_key_metric(company.name, company.metrics)
            if company_metric_text:
                numbers.append(company_metric_text)
        for indicator in article.context.market_indicators:
            market_text = self._format_market_indicator(indicator.name, indicator.value, indicator.change)
            if market_text:
                numbers.append(market_text)
        return self._dedupe_strings(numbers)

    def _extract_market_status(self, article: AnalysisRequest) -> list[str]:
        statuses: list[str] = []
        for indicator in article.context.market_indicators:
            market_text = self._format_market_indicator(indicator.name, indicator.value, indicator.change)
            if market_text:
                statuses.append(market_text)
        return self._dedupe_strings(statuses)

    def _format_metrics(self, metrics: dict[str, str]) -> str | None:
        if not metrics:
            return None
        parts = [f"{key}={value}" for key, value in metrics.items() if str(value).strip()]
        return ", ".join(parts) if parts else None

    def _format_market_indicator(self, name: str, value: str | None, change: str | None) -> str | None:
        parts = [name]
        if value:
            parts.append(str(value))
        if change:
            parts.append(str(change))
        joined = " / ".join(part for part in parts if part)
        return joined or None

    def _format_company_key_metric(self, name: str, metrics: dict[str, str]) -> str | None:
        if not metrics:
            return None

        current_price = (
            metrics.get("current_price")
            or metrics.get("price")
            or metrics.get("close_price")
        )
        change_rate = metrics.get("price_change_pct")
        change_value = metrics.get("price_change")

        parts = [name]
        if current_price:
            parts.append(str(current_price))
        if change_rate:
            parts.append(str(change_rate))
        elif change_value:
            parts.append(str(change_value))

        if len(parts) > 1:
            return " / ".join(parts)

        fallback = self._format_metrics(metrics)
        if fallback:
            return f"{name}: {fallback}"
        return None

    def _parse_pct(self, value: str | None) -> float | None:
        if not value:
            return None

        cleaned = str(value).strip().replace("%", "").replace(",", "")
        match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if not match:
            return None

        try:
            return float(match.group(0))
        except ValueError:
            return None

    def _format_diff_pct(self, diff: float) -> str:
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff:.2f}%p"

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = str(value).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(key)
        return deduped
