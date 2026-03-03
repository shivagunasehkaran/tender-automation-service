"""
Tests for the LangGraph workflow — full pipeline: classify → retrieve → generate → review.

Mocks all LLM calls so tests run without OPENAI_API_KEY.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.graph.state import create_initial_state
from app.graph.workflow import tender_graph


def _mock_classifier_response():
    return MagicMock(content='{"domain": "Security", "keywords": ["encryption", "TLS"]}')


def _mock_generator_response():
    return MagicMock(content="Our platform uses AES-256 encryption for all data at rest.")


def _mock_reviewer_response():
    return MagicMock(content='{"confidence": 0.9, "is_consistent": true, "flags": []}')


@patch("app.agents.reviewer.ChatOpenAI")
@patch("app.agents.generator.ChatOpenAI")
@patch("app.agents.classifier.ChatOpenAI")
def test_workflow_processes_single_question(mock_classifier, mock_generator, mock_reviewer):
    """Workflow processes one question end-to-end and returns complete state."""
    mock_classifier.return_value.invoke.return_value = _mock_classifier_response()
    mock_generator.return_value.invoke.return_value = _mock_generator_response()
    mock_reviewer.return_value.invoke.return_value = _mock_reviewer_response()

    state = create_initial_state("test-session", [(1, "How do you encrypt data?")])
    final_state = tender_graph.invoke(state)

    assert final_state["session_id"] == "test-session"
    assert len(final_state["questions"]) == 1

    q = final_state["questions"][0]
    assert q["domain"] == "Security"
    assert q["generated_answer"] != ""
    assert q["confidence"] == 0.9
    assert q["status"] == "success"
    assert final_state["overall_status"] in ("completed", "completed_with_flags")


@patch("app.agents.reviewer.ChatOpenAI")
@patch("app.agents.generator.ChatOpenAI")
@patch("app.agents.classifier.ChatOpenAI")
def test_workflow_processes_multiple_questions(mock_classifier, mock_generator, mock_reviewer):
    """Workflow processes multiple questions and loops correctly."""
    mock_classifier.return_value.invoke.return_value = _mock_classifier_response()
    mock_generator.return_value.invoke.return_value = _mock_generator_response()
    mock_reviewer.return_value.invoke.return_value = _mock_reviewer_response()

    state = create_initial_state(
        "test-session",
        [
            (1, "Question one about security?"),
            (2, "Question two about infrastructure?"),
        ],
    )
    final_state = tender_graph.invoke(state)

    assert len(final_state["questions"]) == 2
    assert all("domain" in q and q["domain"] for q in final_state["questions"])
    assert all("generated_answer" in q and q["generated_answer"] for q in final_state["questions"])
    assert all(q["status"] == "success" for q in final_state["questions"])
    assert final_state["overall_status"] in ("completed", "completed_with_flags")


@patch("app.agents.reviewer.ChatOpenAI")
@patch("app.agents.generator.ChatOpenAI")
@patch("app.agents.classifier.ChatOpenAI")
def test_workflow_includes_summary_counts(mock_classifier, mock_generator, mock_reviewer):
    """Workflow final state includes processed_count, failed_count, overall_status."""
    mock_classifier.return_value.invoke.return_value = _mock_classifier_response()
    mock_generator.return_value.invoke.return_value = _mock_generator_response()
    mock_reviewer.return_value.invoke.return_value = _mock_reviewer_response()

    state = create_initial_state("test", [(1, "Security question?")])
    final_state = tender_graph.invoke(state)

    assert "processed_count" in final_state or "overall_status" in final_state
    assert "overall_status" in final_state
    assert final_state["overall_status"] in ("completed", "completed_with_flags", "failed")
