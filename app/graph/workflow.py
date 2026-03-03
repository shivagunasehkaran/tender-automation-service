"""
LangGraph workflow — orchestrates the 4 agents with conditional branching and question loop.

Parsing happens before the graph (in API). The graph receives pre-populated state.
"""

import logging

from langgraph.graph import END, StateGraph

from app.agents.classifier import classify_question
from app.agents.generator import generate_with_history, generate_without_history
from app.agents.retrieval import retrieve_historical
from app.agents.reviewer import review_response
from app.graph.state import TenderState

logger = logging.getLogger(__name__)


def increment_question_index(state: TenderState) -> dict:
    """Move to the next question in the list."""
    return {"current_question_index": state["current_question_index"] + 1}


def generate_summary(state: TenderState) -> dict:
    """Generate final processing summary from all question results."""
    questions = state["questions"]
    successful = sum(1 for q in questions if q["status"] == "success")
    failed = sum(1 for q in questions if q["status"] == "failed")
    flagged = sum(1 for q in questions if q.get("reviewer_flags"))

    overall_status = "completed"
    if failed > 0 or flagged > 0:
        overall_status = "completed_with_flags"
    if failed == len(questions):
        overall_status = "failed"

    return {
        "failed_count": failed,
        "overall_status": overall_status,
    }


def route_by_history(state: TenderState) -> str:
    """
    Conditional edge: branch based on historical match.
    Returns 'with_history' or 'without_history'.
    """
    current_idx = state["current_question_index"]
    current_q = state["questions"][current_idx]
    if current_q.get("has_historical_match") and current_q.get("historical_matches"):
        return "with_history"
    return "without_history"


def should_continue(state: TenderState) -> str:
    """
    Conditional edge: decide whether to process next question or finish.
    Returns the name of the next node.
    """
    next_idx = state["current_question_index"] + 1
    if next_idx < len(state["questions"]):
        return "increment"
    return "summarize"


def build_workflow() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(TenderState)

    workflow.add_node("classify", classify_question)
    workflow.add_node("retrieve", retrieve_historical)
    workflow.add_node("generate_with_history", generate_with_history)
    workflow.add_node("generate_without_history", generate_without_history)
    workflow.add_node("review", review_response)
    workflow.add_node("increment", increment_question_index)
    workflow.add_node("summarize", generate_summary)

    workflow.set_entry_point("classify")

    workflow.add_edge("classify", "retrieve")
    workflow.add_conditional_edges(
        "retrieve",
        route_by_history,
        {
            "with_history": "generate_with_history",
            "without_history": "generate_without_history",
        },
    )
    workflow.add_edge("generate_with_history", "review")
    workflow.add_edge("generate_without_history", "review")

    workflow.add_conditional_edges(
        "review",
        should_continue,
        {
            "increment": "increment",
            "summarize": "summarize",
        },
    )

    workflow.add_edge("increment", "classify")
    workflow.add_edge("summarize", END)

    return workflow.compile()


tender_graph = build_workflow()
