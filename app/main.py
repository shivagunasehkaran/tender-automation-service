"""
FastAPI application — tender automation service API layer.
"""

import logging
import uuid
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.config.settings import get_settings
from app.graph.state import create_initial_state
from app.graph.workflow import tender_graph
from app.models.schemas import (
    HealthResponse,
    HistoricalStats,
    ProcessingSummary,
    QuestionResponse,
    TenderProcessResponse,
)
from app.services.excel_handler import generate_output_excel, parse_tender_excel
from app.services.load_historical_data import load_historical_data
from app.services.vector_store import get_vector_store

logging.basicConfig(
    level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app):
    """Startup: optionally load historical data. Shutdown: cleanup."""
    yield


app = FastAPI(
    title="Tender Automation Service",
    description="Multi-agent tender response automation using LangGraph",
    version=VERSION,
    lifespan=lifespan,
)


def convert_state_to_response(state: dict) -> TenderProcessResponse:
    """Convert LangGraph final state to API response model."""
    results = []
    for q in state["questions"]:
        results.append(
            QuestionResponse(
                question_number=q["question_number"],
                original_question=q["original_question"],
                generated_answer=q.get("generated_answer", ""),
                domain=q.get("domain", "Unknown"),
                confidence=q.get("confidence", 0.0),
                historical_match=q.get("has_historical_match", False),
                reviewer_flags=q.get("reviewer_flags", []),
                status=q.get("status", "failed"),
                error=q.get("error"),
            )
        )

    summary = ProcessingSummary(
        total_questions=len(results),
        successful=state.get("processed_count", 0),
        failed=state.get("failed_count", 0),
        flagged_inconsistencies=state.get("flagged_count", 0),
        overall_status=state.get("overall_status", "unknown"),
    )

    return TenderProcessResponse(
        session_id=state["session_id"],
        results=results,
        summary=summary,
    )


@app.post("/api/v1/tender/process", response_model=TenderProcessResponse)
async def process_tender(
    file: UploadFile = File(...),
    format: str = Query("json", enum=["json", "excel"]),
):
    """
    Process a tender questionnaire Excel file and generate responses.

    - Upload an Excel file with tender questions
    - System classifies, retrieves history, generates, and reviews each answer
    - Returns structured results with confidence scores and flags
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "File must be an Excel file (.xlsx or .xls)")

    try:
        content = await file.read()
        questions = parse_tender_excel(content)

        if not questions:
            raise HTTPException(400, "No questions found in the uploaded file")

        session_id = str(uuid.uuid4())
        initial_state = create_initial_state(
            session_id,
            [(q["question_number"], q["original_question"]) for q in questions],
        )

        logger.info("Processing tender %s with %d questions", session_id, len(questions))
        final_state = tender_graph.invoke(initial_state)

        response = convert_state_to_response(final_state)

        if format == "excel":
            excel_results = [
                {
                    "question_number": r.question_number,
                    "original_question": r.original_question,
                    "domain": r.domain,
                    "generated_answer": r.generated_answer,
                    "confidence": r.confidence,
                    "has_historical_match": r.historical_match,
                    "status": r.status,
                }
                for r in response.results
            ]
            summary_dict = {
                "total_questions": response.summary.total_questions,
                "successful": response.summary.successful,
                "failed": response.summary.failed,
                "flagged": response.summary.flagged_inconsistencies,
                "overall_status": response.summary.overall_status,
            }
            excel_bytes = generate_output_excel(excel_results, summary_dict)
            return StreamingResponse(
                BytesIO(excel_bytes),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=tender_response_{session_id}.xlsx"
                },
            )

        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("Failed to process tender: %s", e)
        raise HTTPException(500, f"Processing failed: {str(e)}") from e


@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    """Return service health, version, and vector store readiness."""
    try:
        vs = get_vector_store()
        vs.get_collection_stats()
        vector_store_ready = True
    except Exception:
        vector_store_ready = False

    return HealthResponse(
        status="ok",
        version=VERSION,
        vector_store_ready=vector_store_ready,
    )


@app.get("/api/v1/historical/stats", response_model=HistoricalStats)
async def historical_stats():
    """Return stats about historical data (total docs, per-domain count)."""
    try:
        vs = get_vector_store()
        stats = vs.get_collection_stats()
        return HistoricalStats(
            total_documents=stats.get("total_documents", 0),
            domains=stats.get("domains", {}),
        )
    except Exception as e:
        logger.exception("Failed to get historical stats: %s", e)
        raise HTTPException(500, f"Failed to get stats: {str(e)}") from e


@app.post("/api/v1/historical/load")
async def load_historical():
    """Trigger loading/reloading of historical data from data/historical/."""
    try:
        n = load_historical_data()
        return {"loaded": n, "message": f"Loaded {n} historical responses"}
    except Exception as e:
        logger.exception("Failed to load historical data: %s", e)
        raise HTTPException(500, f"Failed to load: {str(e)}") from e
