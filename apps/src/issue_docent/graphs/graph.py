from langgraph.graph import END, START, StateGraph

from apps.src.issue_docent.graphs.nodes import (
    make_article_briefs_node,
    make_content_plan_node,
    make_issue_docent_content_node,
    make_quiz_node,
    prepare_cluster,
    validate_before_persist,
)
from apps.src.issue_docent.graphs.state import IssueDocentState
from apps.src.issue_docent.llm.client import IssueDocentLLMClient


def build_issue_docent_graph(llm_client: IssueDocentLLMClient | None = None):
    llm_client = llm_client or IssueDocentLLMClient()
    graph = StateGraph(IssueDocentState)
    graph.add_node("prepare_cluster", prepare_cluster)
    graph.add_node("article_briefs", make_article_briefs_node(llm_client))
    graph.add_node("content_plan", make_content_plan_node(llm_client))
    graph.add_node("issue_docent_content", make_issue_docent_content_node(llm_client))
    graph.add_node("quiz", make_quiz_node(llm_client))
    graph.add_node("validate_before_persist", validate_before_persist)

    graph.add_edge(START, "prepare_cluster")
    graph.add_edge("prepare_cluster", "article_briefs")
    graph.add_edge("article_briefs", "content_plan")
    graph.add_edge("content_plan", "issue_docent_content")
    graph.add_edge("issue_docent_content", "quiz")
    graph.add_edge("quiz", "validate_before_persist")
    graph.add_edge("validate_before_persist", END)
    return graph.compile()
