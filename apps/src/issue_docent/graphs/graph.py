from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from apps.src.issue_docent.graphs.nodes import (
    make_article_brief_node,
    make_cluster_summary_node,
    make_issue_docent_node,
    make_quiz_node,
    prepare_cluster,
    validate_before_persist,
)
from apps.src.issue_docent.graphs.state import IssueDocentState
from apps.src.issue_docent.llm.client import IssueDocentLLMClient


def route_article_briefs(state: IssueDocentState) -> list[Send]:
    return [Send("article_brief", {"article": article}) for article in state["cluster"].articles]


def build_issue_docent_graph(llm_client: IssueDocentLLMClient | None = None):
    llm_client = llm_client or IssueDocentLLMClient()
    graph = StateGraph(IssueDocentState)
    graph.add_node("prepare_cluster", prepare_cluster)
    graph.add_node("article_brief", make_article_brief_node(llm_client))
    graph.add_node("cluster_summary", make_cluster_summary_node(llm_client))
    graph.add_node("issue_docent", make_issue_docent_node(llm_client))
    graph.add_node("quiz", make_quiz_node(llm_client))
    graph.add_node("validate_before_persist", validate_before_persist)

    graph.add_edge(START, "prepare_cluster")
    graph.add_conditional_edges("prepare_cluster", route_article_briefs, ["article_brief"])
    graph.add_edge("article_brief", "cluster_summary")
    graph.add_edge("cluster_summary", "issue_docent")
    graph.add_edge("issue_docent", "quiz")
    graph.add_edge("quiz", "validate_before_persist")
    graph.add_edge("validate_before_persist", END)
    return graph.compile()
