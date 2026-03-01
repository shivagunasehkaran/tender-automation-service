"""
Quality Reviewer Agent — reviews generated answers for consistency and compliance.

LangGraph node: assigns confidence score, flags issues, updates status.
"""

import json
import logging

from langchain_openai import ChatOpenAI

from app.config.prompts import REVIEWER_SYSTEM_PROMPT, REVIEWER_USER_PROMPT
from app.config.settings import get_settings
from app.graph.state import TenderState

logger = logging.getLogger(__name__)


def _format_historical_matches(matches: list[dict]) -> str:
    """Format historical matches for review context."""
    if not matches:
        return "None"
    parts = []
    for i, m in enumerate(matches, 1):
        q = m.get("question", "")
        a = m.get("answer", "")
        parts.append(f"Match {i}:\nQ: {q}\nA: {a}")
    return "\n\n".join(parts)


def review_response(state: TenderState) -> dict:
    """
    Review generated answer for quality, consistency, and compliance.

    Reads: questions[current].generated_answer, original_question, domain, historical_matches
    Writes to: questions[current].confidence, is_consistent, reviewer_flags, status
    Returns: questions + processed_count, flagged_count (for reducer)
    On failure: confidence=0, is_consistent=False, status="failed".
    Skips review if generated_answer is empty (generator failed).
    """
    settings = get_settings()
    current_idx = state["current_question_index"]
    questions = [dict(q) for q in state["questions"]]
    current_q = questions[current_idx]

    generated_answer = current_q.get("generated_answer", "").strip()
    if not generated_answer:
        return {"questions": questions}

    try:
        llm = ChatOpenAI(
            model=settings.reviewer_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

        historical_matches_str = _format_historical_matches(
            current_q.get("historical_matches", [])
        )
        user_prompt = REVIEWER_USER_PROMPT.format(
            question=current_q.get("original_question", ""),
            domain=current_q.get("domain", ""),
            generated_answer=generated_answer,
            historical_matches=historical_matches_str,
        )

        messages = [
            ("system", REVIEWER_SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        parsed = json.loads(content)
        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        is_consistent = bool(parsed.get("is_consistent", True))
        flags = parsed.get("flags", [])
        if not isinstance(flags, list):
            flags = []
        flags = [str(f).strip() for f in flags if f]

        current_q["confidence"] = confidence
        current_q["is_consistent"] = is_consistent
        current_q["reviewer_flags"] = flags
        current_q["status"] = "success"
        questions[current_idx] = current_q

        result: dict = {"questions": questions}
        result["processed_count"] = 1
        if flags:
            result["flagged_count"] = 1
        return result

    except Exception as e:
        logger.error("Reviewer failed for question %s: %s", current_idx, e)
        current_q["confidence"] = 0.0
        current_q["is_consistent"] = False
        current_q["reviewer_flags"] = [str(e)]
        current_q["status"] = "failed"
        current_q["error"] = str(e)
        questions[current_idx] = current_q
        return {"questions": questions}
