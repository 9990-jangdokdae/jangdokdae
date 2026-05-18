from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from apps.src.models.analyzer_dto import AnalysisRequest, AnalysisResponse


# 읽는 순서:
# 1) run
# 2) _run_single_cluster
# 3) _build_graph
# 4) _select_representative -> _build_request -> _analyze_request
class ClusterWorkflowState(TypedDict, total=False):
    """그래프가 단계별로 채워 가는 상태 값들."""
    cluster: dict[str, Any]
    cluster_index: int
    representative_article: dict[str, Any]
    request: AnalysisRequest
    result: AnalysisResponse


class ClusterAnalysisWorkflow:
    """대표 기사 선택 -> request 생성 -> 분석 실행 순서를 고정한다."""

    def __init__(self, analyzer_service: Any) -> None:
        self._analyzer_service = analyzer_service
        self._graph = self._build_graph()

    def run(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[AnalysisResponse]:
        """배치 입력이면 클러스터를 하나씩 같은 절차로 분석한다."""
        clusters = self._coerce_clusters(payload)
        results: list[AnalysisResponse] = []
        total_clusters = len(clusters)

        for index, cluster in enumerate(clusters):
            result = self._run_single_cluster(cluster, index=index, total=total_clusters)
            results.append(result)

        return results

    def _run_single_cluster(self, cluster: dict[str, Any], *, index: int, total: int) -> AnalysisResponse:
        """클러스터 1개를 LangGraph state 흐름으로 실제 실행한다."""
        final_state = self._graph.invoke({"cluster": cluster, "cluster_index": index})
        return final_state["result"]

    def _coerce_clusters(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("clusters"), list):
            return payload["clusters"]
        return [payload]

    def _build_graph(self) -> Any:
        """분석 절차를 코드 레벨에서 고정한 최소 orchestration graph."""
        builder = StateGraph(ClusterWorkflowState)
        builder.add_node("select_representative", self._select_representative)
        builder.add_node("build_request", self._build_request)
        builder.add_node("analyze_request", self._analyze_request)
        builder.add_edge(START, "select_representative")
        builder.add_edge("select_representative", "build_request")
        builder.add_edge("build_request", "analyze_request")
        builder.add_edge("analyze_request", END)
        return builder.compile()

    def _select_representative(self, state: ClusterWorkflowState) -> dict[str, Any]:
        """1단계: 클러스터 전체에서 분석 기준이 될 대표 기사를 고른다."""
        representative = self._analyzer_service._select_representative_article(state["cluster"])
        return {"representative_article": representative}

    def _build_request(self, state: ClusterWorkflowState) -> dict[str, Any]:
        """2단계: 대표 기사 + 정형 문맥을 AnalysisRequest로 정리한다."""
        request = self._analyzer_service._cluster_to_request(
            state["cluster"],
            representative=state.get("representative_article"),
        )
        return {"request": request}

    def _analyze_request(self, state: ClusterWorkflowState) -> dict[str, Any]:
        """3단계: 정리된 request를 실제 analyzer에 넘긴다."""
        result = self._analyzer_service.analyze(state["request"])
        return {"result": result}
