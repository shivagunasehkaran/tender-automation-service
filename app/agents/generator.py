"""
Generator Agent — generates professional tender responses from question + history.

LangGraph node: uses gpt-4o for quality-critical answer generation.
"""

import logging

from langchain_openai import ChatOpenAI

from app.config.prompts import (
    GENERATOR_SYSTEM_PROMPT,
    GENERATOR_WITH_HISTORY_PROMPT,
    GENERATOR_WITHOUT_HISTORY_PROMPT,
)
from app.config.settings import get_settings
from app.graph.state import TenderState

logger = logging.getLogger(__name__)


def _format_historical_matches(matches: list[dict]) -> str:
    """Format historical matches as readable context for the prompt."""
    parts = []
    for i, m in enumerate(matches, 1):
        score = m.get("score", 0)
        q = m.get("question", "")
        a = m.get("answer", "")
        parts.append(
            f"Historical Response {i} (similarity: {score}):\n"
            f"Q: {q}\n"
            f"A: {a}"
        )
    return "\n\n".join(parts)


def generate_response(state: TenderState) -> dict:
    """
    Generate a professional tender response for the current question.

    Reads: questions[current].original_question, domain, historical_matches, has_historical_match
    Writes to: questions[current].generated_answer
    On failure: generated_answer="", status="failed", error set.
    """
    settings = get_settings()
    current_idx = state["current_question_index"]
    questions = [dict(q) for q in state["questions"]]
    current_q = questions[current_idx]

    try:
        llm = ChatOpenAI(
            model=settings.generator_model,
            api_key=settings.openai_api_key,
            temperature=0.3,
        )

        question = current_q.get("original_question", "")
        domain = current_q.get("domain", "")

        if current_q.get("has_historical_match") and current_q.get("historical_matches"):
            historical_matches_str = _format_historical_matches(current_q["historical_matches"])
            user_prompt = GENERATOR_WITH_HISTORY_PROMPT.format(
                question=question,
                domain=domain,
                historical_matches=historical_matches_str,
            )
        else:
            user_prompt = GENERATOR_WITHOUT_HISTORY_PROMPT.format(
                question=question,
                domain=domain,
            )

        messages = [
            ("system", GENERATOR_SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        generated_answer = (content or "").strip()

        current_q["generated_answer"] = generated_answer
        questions[current_idx] = current_q
        return {"questions": questions}

    except Exception as e:
        logger.error("Generator failed for question %s: %s", current_idx, e)
        current_q["generated_answer"] = ""
        current_q["status"] = "failed"
        current_q["error"] = str(e)
        questions[current_idx] = current_q
        return {"questions": questions}
