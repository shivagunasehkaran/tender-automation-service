#!/usr/bin/env python3
"""
Quick test for TLS 1.2 scenario.

Tests that different phrasings of the same question get consistent, adapted answers:
- "Do you support SSL and TLS?" 
- "Does the platform enforce TLS 1.2+?"

Requires: OPENAI_API_KEY, historical data loaded (run POST /api/v1/historical/load first)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph.state import create_initial_state
from app.graph.workflow import tender_graph


def run_tls_test(question: str) -> dict:
    """Run full pipeline for one TLS question."""
    state = create_initial_state("tls-test", [(1, question)])
    final = tender_graph.invoke(state)
    return final["questions"][0]


if __name__ == "__main__":
    questions = [
        "Do you support SSL and TLS?",
        "Does the platform enforce TLS 1.2 or higher for data in transit?",
    ]

    print("=" * 60)
    print("TLS 1.2 Scenario Test")
    print("=" * 60)

    for i, q in enumerate(questions, 1):
        print(f"\n--- Question {i}: {q} ---")
        result = run_tls_test(q)
        print(f"Domain: {result['domain']}")
        print(f"Historical match: {result['has_historical_match']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Answer:\n{result['generated_answer']}")
        print()
