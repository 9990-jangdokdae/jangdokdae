from __future__ import annotations

import json
import re

from langchain_google_genai import ChatGoogleGenerativeAI

from apps.src.config import cofig
from apps.src.models.analyzer_dto import (
    AnalysisSection,
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSummary,
    KeyMetric,
    LLMAnalysisResponse,
    RelatedCompanyCard,
    RelatedMarketCard,
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
- analysis_sections는 프론트 상세 페이지의 분석 블록이다. 3개 또는 4개로 작성하고, 번호를 붙이지 않는다.
- analysis_sections의 각 section은 서로 역할이 달라야 하며, 같은 사실이나 같은 해석을 의미 없이 반복하지 않는다.
- 중요한 사실이 여러 section에 필요하면 같은 말을 반복하지 말고, 각 section 역할에 맞게 의미를 달리해서 녹인다.
- 직접적인 투자판단(매수/매도 권유, 목표가 제시)은 하지 않는다.
- 기업/섹터/시장 데이터는 새 사실을 만들지 말고 기사 해석 보조용으로만 사용한다.
- 출력은 반드시 JSON만 반환한다.
""".strip()


class IssueBasedAnalyzerService:
    """대표 기사 기반 LLM 분석과 sidebar 정형화를 함께 맡는 본체."""

    def analyze(self, article: AnalysisRequest) -> AnalysisResponse:
        """LLM 1차 결과를 만들고, 프론트가 바로 쓰는 최종 응답으로 다시 묶는다."""
        result = self._analyze_with_langchain(article)
        return self._finalize_response(article, result)

    def _analyze_with_langchain(self, article: AnalysisRequest) -> LLMAnalysisResponse:
        """LangChain structured output으로 Gemini 1차 결과를 받는다."""
        llm = self._build_langchain_model()
        structured_llm = llm.with_structured_output(LLMAnalysisResponse)
        result = structured_llm.invoke(self._build_prompt(article))
        if not isinstance(result, LLMAnalysisResponse):
            result = LLMAnalysisResponse.model_validate(result)
        return result

    def _build_langchain_model(self) -> object:
        """standalone이 아니라 서버 실행 환경의 Gemini 설정을 그대로 사용한다."""
        if not cofig.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY 환경변수가 필요합니다.")

        return ChatGoogleGenerativeAI(
            model=cofig.GEMINI_MODEL,
            google_api_key=cofig.GEMINI_API_KEY,
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
        return f"""{SYSTEM_PROMPT}

출력 형식:
{{
  "article_id": "{article.article_id}",
  "summary": "이 뉴스를 이해하는 데 필요한 핵심 사실, 원인, 시장 반응, 해석, 시사점을 담은 설명형 문단",
  "selected_issue_candidates": [
    "핵심 이슈 후보 1",
    "핵심 이슈 후보 2"
  ],
  "issue_selection_reason": "왜 이 이슈를 핵심으로 봤는지",
  "summary_points": [
    "핵심 요약 포인트 1",
    "핵심 요약 포인트 2"
  ],
  "evidence_sentences": [
    "핵심 포인트를 뒷받침하는 기사 원문 문장 1",
    "핵심 포인트를 뒷받침하는 기사 원문 문장 2"
  ],
  "analysis_sections": [
    {
      "title": "기사 유형에 맞는 분석 제목 1",
      "summary": "2~4문장 이내의 짧은 분석 문단"
    },
    {
      "title": "기사 유형에 맞는 분석 제목 2",
      "summary": "2~4문장 이내의 짧은 분석 문단"
    },
    {
      "title": "주의할 점 또는 체크포인트",
      "summary": "중복 없이 다른 역할을 하는 분석 문단"
    }
  ],
  "risk_factors": [
    "기사에서 읽을 수 있는 위험 요인"
  ],
  "opportunity_factors": [
    "기사에서 읽을 수 있는 기회 요인"
  ]
}}

입력 메타데이터와 cluster payload 문맥:
{json.dumps(metadata_payload, ensure_ascii=False, indent=2)}

기사 제목:
{article.title or ""}

기사 본문:
{article.content}
"""

    def _finalize_response(self, article: AnalysisRequest, result: LLMAnalysisResponse) -> AnalysisResponse:
        """LLM 1차 결과와 정형 sidebar를 묶어 최종 AnalysisResponse를 만든다."""
        analysis_summary = self._build_analysis_summary(article, result)
        sidebar_context = self._build_sidebar_context(article)
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
            )
            for indicator in article.context.market_indicators
        ]
        return SidebarContext(
            related_companies=related_companies,
            related_markets=related_markets,
            key_metrics=self._build_sidebar_key_metrics(article),
        )

    def _build_sidebar_key_metrics(self, article: AnalysisRequest) -> list[KeyMetric]:
        """기사 본문 숫자를 우선으로 고르고, 필요할 때만 비교 문구를 붙인다."""
        primary_market = self._select_primary_market(article)
        issue_type = self._classify_issue_type(article)
        metrics = self._extract_article_key_metrics(
            article,
            issue_type=issue_type,
            primary_market=primary_market,
        )

        deduped: list[KeyMetric] = []
        seen: set[tuple[str, str]] = set()
        for metric in metrics:
            key = (metric.label.strip(), metric.value.strip())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(metric)

        return deduped[:3]

    def _classify_issue_type(self, article: AnalysisRequest) -> str:
        haystack = " ".join(
            [
                article.title or "",
                article.content,
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
            "market": ["flow_amount", "price_reaction", "market_value", "range_pct", "single_pct", "count_change", "financial_amount"],
            "earnings": ["financial_amount", "price_reaction", "range_pct", "single_pct", "count_change", "market_value", "flow_amount"],
            "supply": ["range_pct", "count_change", "single_pct", "financial_amount", "price_reaction", "market_value", "flow_amount"],
            "policy": ["flow_amount", "market_value", "price_reaction", "range_pct", "single_pct", "financial_amount", "count_change"],
            "general": ["range_pct", "single_pct", "count_change", "financial_amount", "price_reaction", "market_value", "flow_amount"],
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

    def _select_primary_market(self, article: AnalysisRequest) -> RelatedMarketCard | None:
        if not article.context.market_indicators:
            return None

        for indicator in article.context.market_indicators:
            if indicator.name.upper() == "KOSPI":
                return RelatedMarketCard(
                    name=indicator.name,
                    value=indicator.value,
                    change_pct=indicator.change,
                )

        indicator = article.context.market_indicators[0]
        return RelatedMarketCard(
            name=indicator.name,
            value=indicator.value,
            change_pct=indicator.change,
        )

    def _select_financial_anchor_company(self, article: AnalysisRequest):
        for company in article.context.companies:
            if any(company.metrics.get(key) for key in ("revenue", "operating_income", "net_income")):
                return company
        return None

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
