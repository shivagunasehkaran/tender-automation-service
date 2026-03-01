"""
Pydantic models for API request/response.
"""

from pydantic import BaseModel


class QuestionResponse(BaseModel):
    """Single question result in the API response."""

    question_number: int
    original_question: str
    generated_answer: str
    domain: str
    confidence: float
    historical_match: bool
    reviewer_flags: list[str]
    status: str  # "success" | "failed"
    error: str | None = None


class ProcessingSummary(BaseModel):
    """Overall processing summary."""

    total_questions: int
    successful: int
    failed: int
    flagged_inconsistencies: int
    overall_status: str  # "completed" | "completed_with_flags" | "failed"


class TenderProcessResponse(BaseModel):
    """Full response for tender processing endpoint."""

    session_id: str
    results: list[QuestionResponse]
    summary: ProcessingSummary


class HistoricalStats(BaseModel):
    """Stats about the historical data store."""

    total_documents: int
    domains: dict[str, int]  # domain -> count


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    vector_store_ready: bool
