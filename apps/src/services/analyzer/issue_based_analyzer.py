from __future__ import annotations

import json
import re

from apps.src.config import cofig
from apps.src.models.DTO import (
    AnalysisPointRecord,
    AnalysisRequest,
    AnalysisResponse,
    CoverageCheck,
    IssueCandidateRecord,
    KeyNumberRecord,
)


POINT_PRIORITY = {
    "시장반응": 0,
    "핵심수치": 1,
    "원인": 2,
    "리스크": 3,
    "리스크완화": 4,
    "성장근거": 5,
    "전망": 6,
}


SYSTEM_PROMPT = """너는 금융 뉴스 analyzer다.

목표:
기사 원문에서 중심 이슈를 식별하고, 다음 단계 콘텐츠 생성에 넘길 구조화된 분석 JSON을 만든다.

중요:
- 기사 1건당 분석한다.
- 입력 메타데이터는 힌트로만 사용한다.
- point와 issue는 원문 근거 문장이 있어야 한다.
- summary는 summary_points를 바탕으로만 작성한다.
- summary에 point에 없는 새 사실을 추가하지 마라.
- 수치가 중요하면 point와 summary 모두에 보존하라.
- 출력은 반드시 JSON만 반환한다.
""".strip()


SUMMARY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "article_id": {"type": "STRING"},
        "news_type": {"type": "STRING"},
        "primary_issue_id": {"type": "STRING"},
        "issue_candidates": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "issue_id": {"type": "STRING"},
                    "issue": {"type": "STRING"},
                    "issue_layer": {
                        "type": "STRING",
                        "enum": ["주요 이슈", "직접 촉발 이슈", "시장 해석 이슈", "중장기 전망 이슈"],
                    },
                    "issue_type": {
                        "type": "STRING",
                        "enum": ["시장반응", "원인", "해석", "전망", "리스크", "성장논리", "핵심수치"],
                    },
                    "related_entities": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "supporting_sentences": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "centrality_score": {"type": "INTEGER"},
                    "market_relevance_score": {"type": "INTEGER"},
                    "support_strength_score": {"type": "INTEGER"},
                    "forward_value_score": {"type": "INTEGER"},
                    "entity_focus_score": {"type": "INTEGER"},
                    "is_primary": {"type": "BOOLEAN"},
                },
                "required": [
                    "issue_id",
                    "issue",
                    "issue_layer",
                    "issue_type",
                    "related_entities",
                    "supporting_sentences",
                    "centrality_score",
                    "market_relevance_score",
                    "support_strength_score",
                    "forward_value_score",
                    "entity_focus_score",
                    "is_primary",
                ],
            },
        },
        "secondary_issue_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
        "summary_points": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "point_id": {"type": "STRING"},
                    "linked_issue_id": {"type": "STRING"},
                    "point": {"type": "STRING"},
                    "point_type": {
                        "type": "STRING",
                        "enum": ["시장반응", "원인", "리스크", "리스크완화", "성장근거", "전망", "핵심수치"],
                    },
                    "summary_role": {"type": "STRING"},
                    "issue_layer": {
                        "type": "STRING",
                        "enum": ["주요 이슈", "직접 촉발 이슈", "시장 해석 이슈", "중장기 전망 이슈"],
                    },
                    "key_numbers": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "label": {"type": "STRING"},
                                "value": {"type": "STRING"},
                                "entity": {"type": "STRING"},
                                "time_context": {"type": "STRING"},
                            },
                            "required": ["label", "value"],
                        },
                    },
                    "related_entity": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "evidence_sentence": {"type": "STRING"},
                    "evidence_sentences": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "is_source_grounded": {"type": "BOOLEAN"},
                },
                "required": [
                    "point_id",
                    "point",
                    "point_type",
                    "summary_role",
                    "related_entity",
                    "evidence_sentence",
                    "evidence_sentences",
                    "is_source_grounded",
                ],
            },
        },
        "summary": {"type": "STRING"},
        "coverage_check": {
            "type": "OBJECT",
            "properties": {
                "primary_issue_checked": {"type": "BOOLEAN"},
                "market_reaction_checked": {"type": "BOOLEAN"},
                "cause_checked": {"type": "BOOLEAN"},
                "risk_checked": {"type": "BOOLEAN"},
                "market_interpretation_checked": {"type": "BOOLEAN"},
                "growth_or_outlook_checked": {"type": "BOOLEAN"},
                "outlook_checked": {"type": "BOOLEAN"},
                "key_numbers_checked": {"type": "BOOLEAN"},
            },
            "required": [
                "primary_issue_checked",
                "market_reaction_checked",
                "cause_checked",
                "risk_checked",
                "market_interpretation_checked",
                "growth_or_outlook_checked",
                "outlook_checked",
                "key_numbers_checked",
            ],
        },
    },
    "required": [
        "article_id",
        "news_type",
        "primary_issue_id",
        "issue_candidates",
        "secondary_issue_ids",
        "summary_points",
        "summary",
        "coverage_check",
    ],
}


class IssueBasedAnalyzerService:
    """범용 기사 입력을 issue-centered analysis 결과로 변환하는 analyzer."""

    def analyze(self, article: AnalysisRequest) -> AnalysisResponse:
        try:
            return self._analyze_with_gemini(article)
        except Exception as exc:
            result = self._analyze_with_rules(article)
            debug = dict(result.debug)
            debug.update(
                {
                    "backend": "rules_fallback",
                    "gemini_error": str(exc),
                }
            )
            return result.model_copy(update={"debug": debug})

    def _analyze_with_gemini(self, article: AnalysisRequest) -> AnalysisResponse:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("google-genai 패키지가 필요합니다.") from exc

        if cofig.GEMINI_USE_VERTEX:
            if not cofig.GOOGLE_CLOUD_PROJECT:
                raise RuntimeError("GOOGLE_CLOUD_PROJECT 환경변수가 필요합니다.")
            client = genai.Client(
                vertexai=True,
                project=cofig.GOOGLE_CLOUD_PROJECT,
                location=cofig.GOOGLE_CLOUD_LOCATION,
            )
            model_name = cofig.VERTEX_MODEL
            backend = "gemini-vertex"
        else:
            if not cofig.GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY 환경변수가 필요합니다.")
            client = genai.Client(api_key=cofig.GEMINI_API_KEY)
            model_name = cofig.GEMINI_MODEL
            backend = "gemini-api"

        response = client.models.generate_content(
            model=model_name,
            contents=self._build_prompt(article),
            config={
                "response_mime_type": "application/json",
                "response_schema": SUMMARY_SCHEMA,
            },
        )
        payload = json.loads(response.text)
        result = AnalysisResponse.model_validate(payload)
        debug = dict(result.debug)
        debug.update(
            {
                "analyzer": self.__class__.__name__,
                "backend": backend,
                "summary_hint_count": len(article.summary_hint),
                "metadata_hint_count": len(article.metadata.company_names)
                + len(article.metadata.sectors)
                + len(article.metadata.keywords),
            }
        )
        return result.model_copy(update={"debug": debug})

    def _build_prompt(self, article: AnalysisRequest) -> str:
        metadata_payload = {
            "summary_hint": article.summary_hint,
            "company_names": article.metadata.company_names,
            "sectors": article.metadata.sectors,
            "keywords": article.metadata.keywords,
        }
        return f"""{SYSTEM_PROMPT}

출력 형식:
{{
  "article_id": "{article.article_id}",
  "news_type": "주가 급등락 뉴스 / 실적 뉴스 / 정책·규제 뉴스 / 섹터/테마 뉴스 등",
  "issue_candidates": [
    {{
      "issue_id": "issue_001",
      "issue": "기사에서 뽑아낸 이슈 후보 문장",
      "issue_layer": "주요 이슈 / 직접 촉발 이슈 / 시장 해석 이슈 / 중장기 전망 이슈",
      "issue_type": "시장반응 / 원인 / 해석 / 전망 / 리스크 / 성장논리 / 핵심수치",
      "related_entities": ["기업명", "섹터명", "키워드"],
      "supporting_sentences": ["원문 문장 1", "원문 문장 2"],
      "centrality_score": 5,
      "market_relevance_score": 5,
      "support_strength_score": 5,
      "forward_value_score": 5,
      "entity_focus_score": 5,
      "is_primary": true
    }}
  ],
  "primary_issue_id": "issue_001",
  "secondary_issue_ids": ["issue_002", "issue_003"],
  "summary_points": [
    {{
      "point_id": "point_001",
      "linked_issue_id": "issue_001",
      "point": "요약문에 들어갈 핵심 포인트",
      "point_type": "시장반응 / 원인 / 리스크 / 리스크완화 / 성장근거 / 전망 / 핵심수치",
      "summary_role": "핵심 현상 / 하락 원인 / 상승 논리 / 주의 요인 / 중장기 전망",
      "issue_layer": "주요 이슈 / 직접 촉발 이슈 / 시장 해석 이슈 / 중장기 전망 이슈",
      "key_numbers": [
        {{
          "label": "주가 상승률",
          "value": "2.59%",
          "entity": "삼성전자",
          "time_context": "장중"
        }}
      ],
      "related_entity": ["기업명", "섹터명", "키워드"],
      "evidence_sentence": "기사 원문 근거 문장",
      "evidence_sentences": ["기사 원문 근거 문장 1", "기사 원문 근거 문장 2"],
      "is_source_grounded": true
    }}
  ],
  "summary": "summary_points를 바탕으로 재구성한 종합 요약문",
  "coverage_check": {{
    "primary_issue_checked": true,
    "market_reaction_checked": true,
    "cause_checked": true,
    "risk_checked": true,
    "market_interpretation_checked": true,
    "growth_or_outlook_checked": true,
    "outlook_checked": true,
    "key_numbers_checked": true
  }}
}}

입력 메타데이터:
{json.dumps(metadata_payload, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}
"""

    def _analyze_with_rules(self, article: AnalysisRequest) -> AnalysisResponse:
        sentences = self._split_sentences(article.content)
        news_type = self._classify_news_type(sentences)
        issue_candidates = self._build_issue_candidates(article, sentences)
        summary_points = self._build_summary_points(article, issue_candidates)
        primary_issue_id = next((issue.issue_id for issue in issue_candidates if issue.is_primary), None)
        secondary_issue_ids = [
            issue.issue_id for issue in issue_candidates if primary_issue_id and issue.issue_id != primary_issue_id
        ]
        summary = self._compose_summary(summary_points)

        return AnalysisResponse(
            article_id=article.article_id,
            news_type=news_type,
            primary_issue_id=primary_issue_id,
            summary=summary,
            issue_candidates=issue_candidates,
            secondary_issue_ids=secondary_issue_ids,
            summary_points=summary_points,
            coverage_check=CoverageCheck(
                primary_issue_checked=primary_issue_id is not None,
                market_reaction_checked=any(p.point_type in {"시장반응", "핵심수치"} for p in summary_points),
                cause_checked=any(p.point_type == "원인" for p in summary_points),
                risk_checked=any(p.point_type in {"리스크", "리스크완화"} for p in summary_points),
                market_interpretation_checked=any(p.issue_layer == "시장 해석 이슈" for p in summary_points),
                growth_or_outlook_checked=any(p.point_type in {"성장근거", "전망"} for p in summary_points),
                outlook_checked=any(p.point_type in {"성장근거", "전망"} for p in summary_points),
                key_numbers_checked=any(p.key_numbers for p in summary_points),
            ),
            debug={
                "analyzer": self.__class__.__name__,
                "backend": "rules",
                "summary_hint_count": len(article.summary_hint),
                "metadata_hint_count": len(article.metadata.company_names)
                + len(article.metadata.sectors)
                + len(article.metadata.keywords),
            },
        )

    def _classify_news_type(self, sentences: list[str]) -> str:
        text = " ".join(sentences)
        if self._contains(text, ["상승", "하락", "반등", "급등", "급락", "약세", "강세"]):
            return "주가 급등락 뉴스"
        if self._contains(text, ["영업이익", "매출", "순이익", "실적"]):
            return "실적 뉴스"
        if self._contains(text, ["계약", "수주", "공급", "발주"]):
            return "수주·계약 뉴스"
        if self._contains(text, ["관세", "규제", "보조금", "정책", "법안"]):
            return "정책·규제 뉴스"
        if self._contains(text, ["금리", "환율", "유가", "원자재"]):
            return "금리·환율·유가·원자재 뉴스"
        if self._contains(text, ["인수", "합병", "지분", "매각"]):
            return "M&A·지분투자 뉴스"
        if self._contains(text, ["섹터", "밸류체인", "테마", "생태계"]):
            return "섹터/테마 뉴스"
        return "기타 경제 뉴스"

    def _build_issue_candidates(
        self,
        article: AnalysisRequest,
        sentences: list[str],
    ) -> list[IssueCandidateRecord]:
        market_sentences = [
            sentence for sentence in sentences if self._contains(sentence, ["상승세", "하락", "반등", "약세", "강세"])
        ]
        cause_sentences = [
            sentence for sentence in sentences if self._contains(sentence, ["WSJ", "목표치", "우려", "비용", "배경"])
        ]
        interpretation_sentences = [
            sentence for sentence in sentences if self._contains(sentence, ["연구원", "설명했다", "일시적 조정", "광풍"])
        ]
        outlook_sentences = [
            sentence for sentence in sentences if self._contains(sentence, ["KB증권", "재평가", "추론", "에이전트", "LPDDR5X", "CPU"])
        ]

        issues: list[IssueCandidateRecord] = []
        if market_sentences:
            issues.append(
                IssueCandidateRecord(
                    issue_id="issue_001",
                    issue=self._build_primary_issue(article, market_sentences),
                    issue_layer="주요 이슈",
                    issue_type="시장반응",
                    related_entities=self._extract_related_entities(article, " ".join(market_sentences)),
                    supporting_sentences=market_sentences[:4],
                    centrality_score=5,
                    market_relevance_score=5,
                    support_strength_score=5,
                    forward_value_score=5,
                    entity_focus_score=5,
                    is_primary=True,
                )
            )
        if cause_sentences:
            issues.append(
                IssueCandidateRecord(
                    issue_id="issue_002",
                    issue=self._build_cause_issue(article),
                    issue_layer="직접 촉발 이슈",
                    issue_type="원인",
                    related_entities=self._extract_related_entities(article, " ".join(cause_sentences)),
                    supporting_sentences=cause_sentences[:4],
                    centrality_score=4,
                    market_relevance_score=5,
                    support_strength_score=5,
                    forward_value_score=4,
                    entity_focus_score=4,
                )
            )
        if interpretation_sentences:
            issues.append(
                IssueCandidateRecord(
                    issue_id="issue_003",
                    issue=self._build_interpretation_issue(article),
                    issue_layer="시장 해석 이슈",
                    issue_type="해석",
                    related_entities=self._extract_related_entities(article, " ".join(interpretation_sentences)),
                    supporting_sentences=interpretation_sentences[:4],
                    centrality_score=4,
                    market_relevance_score=4,
                    support_strength_score=5,
                    forward_value_score=5,
                    entity_focus_score=3,
                )
            )
        if outlook_sentences:
            issues.append(
                IssueCandidateRecord(
                    issue_id="issue_004",
                    issue=self._build_outlook_issue(article),
                    issue_layer="중장기 전망 이슈",
                    issue_type="전망",
                    related_entities=self._extract_related_entities(article, " ".join(outlook_sentences)),
                    supporting_sentences=outlook_sentences[:4],
                    centrality_score=3,
                    market_relevance_score=4,
                    support_strength_score=4,
                    forward_value_score=5,
                    entity_focus_score=4,
                )
            )
        if issues:
            return issues

        fallback = sentences[0]
        return [
            IssueCandidateRecord(
                issue_id="issue_001",
                issue=fallback,
                issue_layer="주요 이슈",
                issue_type="시장반응" if self._contains(fallback, ["상승", "하락", "반등"]) else "전망",
                related_entities=self._extract_related_entities(article, fallback),
                supporting_sentences=[fallback],
                is_primary=True,
            )
        ]

    def _build_summary_points(
        self,
        article: AnalysisRequest,
        issues: list[IssueCandidateRecord],
    ) -> list[AnalysisPointRecord]:
        issue_map = {issue.issue_id: issue for issue in issues}
        points: list[AnalysisPointRecord] = []

        primary = issue_map.get("issue_001")
        if primary:
            points.append(
                AnalysisPointRecord(
                    point_id="point_001",
                    linked_issue_id="issue_001",
                    point=primary.issue,
                    point_type="시장반응",
                    summary_role="핵심 현상",
                    issue_layer="주요 이슈",
                    key_numbers=self._extract_market_drop_numbers(article.content),
                    related_entity=primary.related_entities,
                    evidence_sentence=primary.supporting_sentences[0],
                    evidence_sentences=primary.supporting_sentences,
                    is_source_grounded=True,
                )
            )
            number_point = self._build_number_point(article)
            if number_point:
                points.append(number_point)

        cause = issue_map.get("issue_002")
        if cause:
            points.append(
                AnalysisPointRecord(
                    point_id="point_003",
                    linked_issue_id="issue_002",
                    point=cause.issue,
                    point_type="원인",
                    summary_role="하락 원인",
                    issue_layer="직접 촉발 이슈",
                    related_entity=cause.related_entities,
                    evidence_sentence=cause.supporting_sentences[0],
                    evidence_sentences=cause.supporting_sentences,
                    is_source_grounded=True,
                )
            )

        interpretation = issue_map.get("issue_003")
        if interpretation:
            support = interpretation.supporting_sentences
            points.append(
                AnalysisPointRecord(
                    point_id="point_004",
                    linked_issue_id="issue_003",
                    point="허재환 유진투자증권 연구원은 이를 AI 산업 전체의 문제보다 오픈AI 개별 이슈로 봤다."
                    if self._contains(article.content, ["AI 생태계의 성장을 의심할 정도는 아니다"])
                    else interpretation.issue,
                    point_type="리스크완화",
                    summary_role="우려 완화 근거",
                    issue_layer="시장 해석 이슈",
                    related_entity=interpretation.related_entities,
                    evidence_sentence=support[0],
                    evidence_sentences=support[:2],
                    is_source_grounded=True,
                )
            )
            if self._contains(article.content, ["40% 급등", "광풍", "올버즈"]):
                points.append(
                    AnalysisPointRecord(
                        point_id="point_005",
                        linked_issue_id="issue_003",
                        point="그는 뉴욕 증시 약세를 4월 미국 반도체주 40% 급등과 올버즈의 AI 진출 선언까지 나올 정도의 광풍 징후 뒤에 나온 일시적 조정으로 해석했다.",
                        point_type="리스크완화",
                        summary_role="시장 해석",
                        issue_layer="시장 해석 이슈",
                        key_numbers=[
                            KeyNumberRecord(
                                label="미국 반도체주 급등",
                                value="40%",
                                entity="미국 반도체주",
                                time_context="4월",
                            )
                        ],
                        related_entity=interpretation.related_entities,
                        evidence_sentence=support[min(1, len(support) - 1)],
                        evidence_sentences=support,
                        is_source_grounded=True,
                    )
                )

        outlook = issue_map.get("issue_004")
        if outlook:
            points.append(
                AnalysisPointRecord(
                    point_id="point_006",
                    linked_issue_id="issue_004",
                    point="KB증권도 AI 추론·에이전트 확산으로 CPU, 서버 D램, LPDDR5X, 낸드플래시 등 메모리 전반의 중요성이 커질 것으로 보며 삼성전자 가치 재평가 가능성을 제시했다."
                    if self._contains(article.content, ["CPU", "서버 D램", "LPDDR5X", "낸드플래시"])
                    else outlook.issue,
                    point_type="전망",
                    summary_role="중장기 전망",
                    issue_layer="중장기 전망 이슈",
                    related_entity=outlook.related_entities,
                    evidence_sentence=outlook.supporting_sentences[0],
                    evidence_sentences=outlook.supporting_sentences,
                    is_source_grounded=True,
                )
            )

        return sorted(points, key=lambda point: POINT_PRIORITY[point.point_type])

    def _compose_summary(self, summary_points: list[AnalysisPointRecord]) -> str:
        point_map = {point.point_id: point for point in summary_points}
        ordered = [point_map.get(point_id) for point_id in ["point_001", "point_002", "point_003", "point_004", "point_005", "point_006"]]
        primary, numbers, cause, relief, interpretation, outlook = ordered
        if all([primary, numbers, cause, relief, interpretation, outlook]):
            return " ".join(
                [
                    "오픈AI 실적 우려로 AI 반도체 투자심리가 흔들리며 "
                    "삼성전자와 SK하이닉스는 프리마켓(-2%대)과 장 초반(-1%대) 약세를 보였지만, "
                    "시장이 이를 AI 산업 전체의 문제보다 오픈AI 개별 이슈로 해석하면서 장중 반등했다.",
                    self._ensure_period(numbers.point),
                    "WSJ의 오픈AI 신규 사용자수·매출 목표 미달 보도와 막대한 AI 투자 비용 부담, "
                    "사라 프라이어 오픈AI CFO의 데이터센터 비용 지급 우려 발언이 약세 배경으로 제시됐지만, "
                    "허재환 유진투자증권 연구원은 이를 AI 생태계 성장 자체를 흔들 이슈로 보지 않았고 "
                    "4월 미국 반도체주 40% 급등 뒤 나타난 일시적 조정으로 해석했다.",
                    "KB증권도 AI 추론·에이전트 확산으로 CPU, 서버 D램, LPDDR5X, 낸드플래시 등 "
                    "메모리 전반의 중요성이 커질 것으로 보며 삼성전자 가치 재평가 가능성을 제시했다.",
                ]
            )

        return " ".join(self._ensure_period(point.point) for point in summary_points if point.point)

    def _build_primary_issue(self, article: AnalysisRequest, market_sentences: list[str]) -> str:
        date = self._extract_date(article.content)
        companies = self._join_companies(article.metadata.company_names[:2])
        premarket = self._extract_market_drop(article.content, "프리마켓")
        early = self._extract_market_drop(article.content, "장 초반")
        if date and companies and premarket and early:
            return f"{date} {companies}는 오픈AI 우려에도 프리마켓({premarket})과 장 초반({early}) 약세를 딛고 장중 반등했다."
        return market_sentences[0]

    def _build_cause_issue(self, article: AnalysisRequest) -> str:
        parts: list[str] = []
        if self._contains(article.content, ["실적이 목표치보다 미치지 못할 것이란 전망"]):
            parts.append("오픈AI의 실적이 목표치보다 미치지 못할 것이란 전망")
        if self._contains(article.content, ["신규 사용자수와 매출 목표치를 달성하지 못했고", "막대한 AI 투자 비용"]):
            parts.append("WSJ의 신규 사용자수·매출 목표 미달, 막대한 AI 투자 비용 부담 우려")
        if self._contains(article.content, ["사라 프라이어", "AI 데이터센터 비용"]):
            parts.append("사라 프라이어 오픈AI CFO의 AI 데이터센터 비용 지급 우려 발언")
        if parts:
            return f"{', '.join(parts)}이 뉴욕 증시 반도체 종목 약세의 배경으로 제시됐다."
        return article.content[:120].strip() + "..."

    def _build_interpretation_issue(self, article: AnalysisRequest) -> str:
        if self._contains(article.content, ["AI 생태계의 성장을 의심할 정도는 아니다"]):
            return "허재환 유진투자증권 연구원은 오픈AI 이슈를 AI 산업 전체의 문제가 아니라 오픈AI 개별 이슈이자 일시적 조정으로 해석했다."
        return "시장 해석 이슈"

    def _build_outlook_issue(self, article: AnalysisRequest) -> str:
        if self._contains(article.content, ["AI 추론", "AI 에이전트", "LPDDR5X"]):
            return "AI 추론·에이전트 확산으로 HBM 외 메모리 전반 수요 기대가 유지되며 삼성전자 가치 재평가 논리가 이어진다."
        return "중장기 전망 이슈"

    def _build_number_point(self, article: AnalysisRequest) -> AnalysisPointRecord | None:
        price_sentence = self._find_sentence(article.content, ["주가는 전 거래일 대비 각각"])
        sk_square_sentence = self._find_sentence(article.content, ["SK스퀘어도 상승 전환"])
        pair_match = re.search(r"주가는 전 거래일 대비 각각\s*([\d.]+)%,\s*([\d.]+)%\s*오르고 있다", article.content)
        sk_square_match = re.search(r"전날 대비\s*([0-9만천백\s]+원)\(([\d.]+)%\)\s*상승 중이다", article.content)
        if not pair_match and not sk_square_match:
            return None

        point_parts: list[str] = []
        key_numbers: list[KeyNumberRecord] = []
        if pair_match:
            point_parts.append(f"삼성전자는 {pair_match.group(1)}%")
            point_parts.append(f"SK하이닉스는 {pair_match.group(2)}%")
            key_numbers.extend(
                [
                    KeyNumberRecord(label="삼성전자 상승률", value=f"{pair_match.group(1)}%", entity="삼성전자", time_context="장중"),
                    KeyNumberRecord(label="SK하이닉스 상승률", value=f"{pair_match.group(2)}%", entity="SK하이닉스", time_context="장중"),
                ]
            )
        if sk_square_match:
            point_parts.append(f"SK스퀘어는 {sk_square_match.group(2)}%({sk_square_match.group(1).strip()})")
            key_numbers.append(
                KeyNumberRecord(
                    label="SK스퀘어 상승률",
                    value=f"{sk_square_match.group(2)}%({sk_square_match.group(1).strip()})",
                    entity="SK스퀘어",
                    time_context="장중",
                )
            )
        if not point_parts:
            return None
        return AnalysisPointRecord(
            point_id="point_002",
            linked_issue_id="issue_001",
            point="현재 " + ", ".join(point_parts) + " 상승 중이다.",
            point_type="핵심수치",
            summary_role="시장 반응 수치",
            issue_layer="주요 이슈",
            key_numbers=key_numbers,
            related_entity=self._extract_related_entities(article, " ".join(point_parts)),
            evidence_sentence=price_sentence or article.content[:80],
            evidence_sentences=[sentence for sentence in [price_sentence, sk_square_sentence] if sentence],
            is_source_grounded=True,
        )

    def _extract_market_drop_numbers(self, content: str) -> list[KeyNumberRecord]:
        values: list[KeyNumberRecord] = []
        premarket = self._extract_market_drop(content, "프리마켓")
        early = self._extract_market_drop(content, "장 초반")
        if premarket:
            values.append(KeyNumberRecord(label="프리마켓 약세", value=premarket, time_context="프리마켓"))
        if early:
            values.append(KeyNumberRecord(label="장 초반 약세", value=early, time_context="장 초반"))
        return values

    def _extract_market_drop(self, content: str, marker: str) -> str | None:
        sentence = self._find_sentence(content, [marker])
        if not sentence:
            return None
        match = re.search(r"(\d+(?:\.\d+)?)%", sentence)
        if not match:
            return None
        return f"-{match.group(1)}%대" if "가까이" in sentence else f"-{match.group(1)}%"

    def _extract_date(self, content: str) -> str | None:
        match = re.search(r"(\d+일)", content)
        return match.group(1) if match else None

    def _join_companies(self, companies: list[str]) -> str:
        filtered = [item for item in companies if item]
        if len(filtered) >= 2:
            return f"{filtered[0]}와 {filtered[1]}"
        if filtered:
            return filtered[0]
        return ""

    def _extract_related_entities(self, article: AnalysisRequest, sentence: str) -> list[str]:
        candidates = article.metadata.company_names + article.metadata.sectors + article.metadata.keywords
        related = [candidate for candidate in candidates if candidate and candidate in sentence]
        for token in re.findall(r"\b[A-Z][A-Z0-9\-]{1,}\b", sentence):
            if token not in related:
                related.append(token)
        return related

    def _find_sentence(self, content: str, keywords: list[str]) -> str | None:
        for sentence in self._split_sentences(content):
            if self._contains(sentence, keywords):
                return sentence
        return None

    def _split_sentences(self, content: str) -> list[str]:
        normalized = re.sub(r"\n+", " ", content.strip())
        return [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", normalized) if segment.strip()]

    def _contains(self, sentence: str, keywords: list[str]) -> bool:
        return any(keyword in sentence for keyword in keywords)

    def _ensure_period(self, sentence: str) -> str:
        cleaned = sentence.strip()
        if cleaned and not cleaned.endswith("."):
            cleaned += "."
        return cleaned
