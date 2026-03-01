"""
Classifier Agent — classifies tender questions into domain and extracts keywords.

LangGraph node: reads current question, writes domain and keywords.
"""

import json
import logging

from langchain_openai import ChatOpenAI

from app.config.prompts import CLASSIFIER_SYSTEM_PROMPT, CLASSIFIER_USER_PROMPT
from app.config.settings import get_settings
from app.graph.state import TenderState

logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = frozenset({
    "Security", "Infrastructure", "AI/ML", "Compliance", "Architecture", "Pricing", "General"
})


def classify_question(state: TenderState) -> dict:
    """
    Classify the current question into a domain and extract keywords.

    Writes to: questions[current].domain, questions[current].keywords
    On failure: defaults to "General" domain, empty keywords (recoverable).
    """
    settings = get_settings()
    current_idx = state["current_question_index"]
    questions = [dict(q) for q in state["questions"]]
    current_q = questions[current_idx]

    try:
        llm = ChatOpenAI(
            model=settings.classifier_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

        user_prompt = CLASSIFIER_USER_PROMPT.format(
            question=current_q["original_question"]
        )

        messages = [
            ("system", CLASSIFIER_SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(content)

        domain = str(parsed.get("domain", "General")).strip()
        if domain not in ALLOWED_DOMAINS:
            domain = "General"

        keywords = parsed.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        keywords = [str(k).strip() for k in keywords if k]

        current_q["domain"] = domain
        current_q["keywords"] = keywords
        questions[current_idx] = current_q
        return {"questions": questions}

    except Exception as e:
        logger.error("Classifier failed for question %s: %s", current_idx, e)
        current_q["domain"] = "General"
        current_q["keywords"] = []
        questions[current_idx] = current_q
        return {"questions": questions}
