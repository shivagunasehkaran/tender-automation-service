"""
Tests for each agent — verifies structure and behavior with mock/sample state.

LLM-dependent agents (classifier, generator, reviewer) use mocked ChatOpenAI.
Retrieval agent has no LLM — tests run against real ChromaDB (may be empty).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.graph.state import create_initial_state
from app.agents.classifier import classify_question
from app.agents.retrieval import retrieve_historical
from app.agents.generator import generate_response
from app.agents.reviewer import review_response


# --- Classifier Agent ---

@patch("app.agents.classifier.ChatOpenAI")
def test_classifier_returns_domain_and_keywords(mock_chat):
    """Classifier sets domain and keywords on the current question."""
    mock_response = MagicMock()
    mock_response.content = '{"domain": "Security", "keywords": ["encryption", "TLS", "data protection"]}'
    mock_chat.return_value.invoke.return_value = mock_response

    state = create_initial_state("test", [(1, "How do you handle data encryption?")])
    out = classify_question(state)

    assert "questions" in out
    q = out["questions"][0]
    assert q["domain"] == "Security"
    assert isinstance(q["keywords"], list)
    assert len(q["keywords"]) > 0


@patch("app.agents.classifier.ChatOpenAI")
def test_classifier_on_failure_defaults_to_general(mock_chat):
    """Classifier defaults to General domain when LLM fails."""
    mock_chat.return_value.invoke.side_effect = Exception("API error")

    state = create_initial_state("test", [(1, "Some question?")])
    out = classify_question(state)

    q = out["questions"][0]
    assert q["domain"] == "General"
    assert q["keywords"] == []


# --- Retrieval Agent ---

def test_retrieval_returns_questions_with_matches_field():
    """Retrieval sets historical_matches and has_historical_match."""
    state = create_initial_state("test", [(1, "What is your security approach?")])
    state["questions"][0]["domain"] = "Security"

    out = retrieve_historical(state)

    assert "questions" in out
    q = out["questions"][0]
    assert "historical_matches" in q
    assert isinstance(q["historical_matches"], list)
    assert "has_historical_match" in q
    assert isinstance(q["has_historical_match"], bool)


def test_retrieval_on_failure_returns_empty_matches():
    """Retrieval returns empty matches on error (does not crash)."""
    state = create_initial_state("test", [(1, "Question?")])
    state["questions"][0]["domain"] = "Security"

    with patch("app.agents.retrieval.get_vector_store") as mock_vs:
        mock_vs.side_effect = Exception("ChromaDB error")
        out = retrieve_historical(state)

    q = out["questions"][0]
    assert q["historical_matches"] == []
    assert q["has_historical_match"] is False


# --- Generator Agent ---

@patch("app.agents.generator.ChatOpenAI")
def test_generator_sets_generated_answer(mock_chat):
    """Generator sets generated_answer on the current question."""
    mock_response = MagicMock()
    mock_response.content = "Our platform uses industry-standard encryption for all data."
    mock_chat.return_value.invoke.return_value = mock_response

    state = create_initial_state("test", [(1, "How do you encrypt data?")])
    state["questions"][0]["domain"] = "Security"
    state["questions"][0]["has_historical_match"] = False

    out = generate_response(state)

    assert "questions" in out
    q = out["questions"][0]
    assert "generated_answer" in q
    assert len(q["generated_answer"]) > 0


@patch("app.agents.generator.ChatOpenAI")
def test_generator_on_failure_marks_question_failed(mock_chat):
    """Generator sets status=failed when LLM fails."""
    mock_chat.return_value.invoke.side_effect = Exception("API error")

    state = create_initial_state("test", [(1, "Question?")])
    state["questions"][0]["domain"] = "Security"

    out = generate_response(state)

    q = out["questions"][0]
    assert q["generated_answer"] == ""
    assert q["status"] == "failed"
    assert q["error"] is not None


# --- Reviewer Agent ---

@patch("app.agents.reviewer.ChatOpenAI")
def test_reviewer_sets_confidence_and_status(mock_chat):
    """Reviewer sets confidence, is_consistent, reviewer_flags, status."""
    mock_response = MagicMock()
    mock_response.content = '{"confidence": 0.9, "is_consistent": true, "flags": []}'
    mock_chat.return_value.invoke.return_value = mock_response

    state = create_initial_state("test", [(1, "Security question?")])
    state["questions"][0]["domain"] = "Security"
    state["questions"][0]["generated_answer"] = "We use encryption."
    state["questions"][0]["historical_matches"] = []

    out = review_response(state)

    assert "questions" in out
    q = out["questions"][0]
    assert q["confidence"] == 0.9
    assert q["is_consistent"] is True
    assert q["status"] == "success"
    assert "reviewer_flags" in q


def test_reviewer_skips_when_generated_answer_empty():
    """Reviewer skips (returns unchanged) when generated_answer is empty."""
    state = create_initial_state("test", [(1, "Question?")])
    state["questions"][0]["generated_answer"] = ""
    state["questions"][0]["domain"] = "Security"

    out = review_response(state)

    assert "questions" in out
    q = out["questions"][0]
    assert q["confidence"] == 0.0
    assert q["status"] == "pending"


@patch("app.agents.reviewer.ChatOpenAI")
def test_reviewer_returns_processed_count_and_flagged_count(mock_chat):
    """Reviewer returns processed_count and flagged_count for reducer."""
    mock_response = MagicMock()
    mock_response.content = '{"confidence": 0.7, "is_consistent": false, "flags": ["Minor inconsistency"]}'
    mock_chat.return_value.invoke.return_value = mock_response

    state = create_initial_state("test", [(1, "Question?")])
    state["questions"][0]["generated_answer"] = "Some answer."
    state["questions"][0]["domain"] = "Security"

    out = review_response(state)

    assert "processed_count" in out
    assert out["processed_count"] == 1
    assert "flagged_count" in out
    assert out["flagged_count"] == 1
