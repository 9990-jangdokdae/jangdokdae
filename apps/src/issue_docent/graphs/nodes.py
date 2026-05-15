from apps.src.issue_docent.graphs.state import IssueDocentPersistPayload, IssueDocentState
from apps.src.issue_docent.llm.client import IssueDocentLLMClient
from apps.src.schemas.issue_docent_llm import QuizOutput
from apps.src.services.issue_docent.term_matcher import match_terms


def prepare_cluster(state: IssueDocentState) -> dict:
    cluster = state["cluster"]
    if not cluster.articles:
        raise ValueError(f"cluster {cluster.cluster_id} has no source articles")
    return {"article_briefs": []}


def make_article_brief_node(llm_client: IssueDocentLLMClient):
    async def article_brief_node(state: IssueDocentState) -> dict:
        brief = await llm_client.generate_article_brief(state["article"])
        return {"article_briefs": [brief]}

    return article_brief_node


def make_cluster_summary_node(llm_client: IssueDocentLLMClient):
    async def cluster_summary_node(state: IssueDocentState) -> dict:
        article_briefs = sorted(
            state["article_briefs"],
            key=lambda brief: brief.article_order,
        )
        cluster_summary = await llm_client.generate_cluster_summary(
            cluster=state["cluster"],
            article_briefs=article_briefs,
        )
        return {"cluster_summary": cluster_summary}

    return cluster_summary_node


def make_issue_docent_node(llm_client: IssueDocentLLMClient):
    async def issue_docent_node(state: IssueDocentState) -> dict:
        issue_docent = await llm_client.generate_issue_docent(state["cluster_summary"])
        return {"issue_docent": issue_docent}

    return issue_docent_node


def make_quiz_node(llm_client: IssueDocentLLMClient):
    async def quiz_node(state: IssueDocentState) -> dict:
        term_candidates = _build_quiz_term_candidates(state)
        quizzes = await llm_client.generate_quizzes(
            issue_docent=state["issue_docent"],
            term_candidates=term_candidates,
        )
        return {
            "quiz_term_candidates": term_candidates,
            "quizzes": quizzes,
        }

    return quiz_node


def validate_before_persist(state: IssueDocentState) -> dict:
    cluster_summary = state["cluster_summary"]
    issue_docent = state["issue_docent"]
    term_candidates = state.get("quiz_term_candidates", [])
    quizzes = QuizOutput.model_validate_with_term_candidates(
        state["quizzes"].model_dump(),
        has_term_candidates=bool(term_candidates),
    )
    payload = IssueDocentPersistPayload(
        cluster_id=state["cluster"].cluster_id,
        title=cluster_summary.title,
        teaser=cluster_summary.teaser,
        summary=cluster_summary.summary,
        explanation=[section.model_dump() for section in issue_docent.explanation],
        quizzes=_assign_quiz_ids(quizzes),
    )
    return {"persist_payload": payload}


def _build_quiz_term_candidates(state: IssueDocentState) -> list[dict]:
    stock_terms = state.get("stock_terms", [])
    if not stock_terms:
        return []

    candidates_by_id: dict[int, dict] = {}
    for section in state["issue_docent"].explanation:
        for paragraph in section.paragraphs:
            for match in match_terms(paragraph, stock_terms):
                candidates_by_id.setdefault(
                    match.term_id,
                    {
                        "term_id": match.term_id,
                        "term": match.term,
                        "category": match.category,
                        "definition": match.definition,
                    },
                )

    return list(candidates_by_id.values())


def _assign_quiz_ids(quizzes: QuizOutput) -> list[dict]:
    return [
        {
            **quiz.model_dump(),
            "quiz_id": f"quiz-{index}",
        }
        for index, quiz in enumerate(quizzes.quizzes, start=1)
    ]
