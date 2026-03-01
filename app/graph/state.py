"""
LangGraph state schema — single source of truth for all data flowing through the system.

Uses TypedDict for LangGraph compatibility. Each agent reads from and writes to
its designated fields only. Reducers are used for counters that may be
incremented by multiple nodes.
"""

from operator import add
from typing import Annotated, TypedDict


class QuestionResult(TypedDict):
    """
    Per-question data structure. Each question from the Excel gets one QuestionResult.
    Fields are populated by different agents as the pipeline processes the question.
    """

    question_number: int
    """From Excel parsing — 1-based index of the question."""

    original_question: str
    """Raw question text from Excel."""

    domain: str
    """Set by Classifier — e.g., 'Security', 'Infrastructure', 'AI/ML', 'General'."""

    keywords: list[str]
    """Set by Classifier — extracted key technical terms (3-5)."""

    historical_matches: list[dict]
    """Set by Retrieval — matched Q&A pairs with similarity scores."""

    has_historical_match: bool
    """Set by Retrieval — True if similarity score exceeds threshold."""

    generated_answer: str
    """Set by Generator — the final answer text."""

    confidence: float
    """Set by Reviewer — quality score from 0.0 to 1.0."""

    is_consistent: bool
    """Set by Reviewer — True if consistent with historical responses."""

    reviewer_flags: list[str]
    """Set by Reviewer — list of flag messages (contradictions, unsupported claims, etc.)."""

    status: str
    """Processing status: 'pending' | 'success' | 'failed'."""

    error: str | None
    """Error message if processing failed; None otherwise."""


class TenderState(TypedDict):
    """
    Main LangGraph state. Holds session-level data and the list of questions.
    Counters use operator.add reducer so nodes can increment without overwriting.
    """

    session_id: str
    """Unique ID for this processing session."""

    questions: list[QuestionResult]
    """All questions with their results. Updated in place as each question is processed."""

    current_question_index: int
    """Index of the question currently being processed (0-based)."""

    processed_count: Annotated[int, add]
    """Counter: number of questions successfully processed."""

    failed_count: Annotated[int, add]
    """Counter: number of questions that failed processing."""

    flagged_count: Annotated[int, add]
    """Counter: number of questions flagged for review."""

    overall_status: str
    """Session status: 'processing' | 'completed' | 'completed_with_flags' | 'failed'."""


def create_empty_question(number: int, text: str) -> QuestionResult:
    """
    Create a QuestionResult with default values for a new question.

    Args:
        number: 1-based question number from Excel.
        text: Raw question text.

    Returns:
        QuestionResult with all fields initialized to defaults.
    """
    return QuestionResult(
        question_number=number,
        original_question=text,
        domain="",
        keywords=[],
        historical_matches=[],
        has_historical_match=False,
        generated_answer="",
        confidence=0.0,
        is_consistent=True,
        reviewer_flags=[],
        status="pending",
        error=None,
    )


def create_initial_state(session_id: str, questions: list[tuple[int, str]]) -> TenderState:
    """
    Create a fresh TenderState from parsed questions.

    Args:
        session_id: Unique identifier for this processing session.
        questions: List of (question_number, question_text) tuples from Excel parsing.

    Returns:
        TenderState ready for the LangGraph workflow.
    """
    question_results = [
        create_empty_question(number, text) for number, text in questions
    ]
    return TenderState(
        session_id=session_id,
        questions=question_results,
        current_question_index=0,
        processed_count=0,
        failed_count=0,
        flagged_count=0,
        overall_status="processing",
    )
