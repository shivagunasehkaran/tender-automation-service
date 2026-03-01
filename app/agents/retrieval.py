"""
Retrieval Agent — searches ChromaDB for similar historical Q&A pairs.

LangGraph node: no LLM — pure vector search with domain-scoped filtering.
"""

import logging

from app.graph.state import TenderState
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def retrieve_historical(state: TenderState) -> dict:
    """
    Search historical responses for similar questions in the same domain.

    Reads: questions[current].domain, questions[current].original_question
    Writes to: questions[current].historical_matches, questions[current].has_historical_match
    On failure: empty matches, has_historical_match=False.
    """
    current_idx = state["current_question_index"]
    questions = [dict(q) for q in state["questions"]]
    current_q = questions[current_idx]

    try:
        vector_store = get_vector_store()
        domain = current_q.get("domain") or ""
        query = current_q.get("original_question") or ""

        matches = vector_store.search_similar(
            query=query,
            domain=domain if domain else None,
        )

        current_q["historical_matches"] = matches
        current_q["has_historical_match"] = len(matches) > 0
        questions[current_idx] = current_q
        return {"questions": questions}

    except Exception as e:
        logger.error("Retrieval failed for question %s: %s", current_idx, e)
        current_q["historical_matches"] = []
        current_q["has_historical_match"] = False
        questions[current_idx] = current_q
        return {"questions": questions}
