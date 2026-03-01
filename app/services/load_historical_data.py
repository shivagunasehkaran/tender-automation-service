"""
Load historical tender responses from data/historical/ into ChromaDB.

Expected JSON format per file:
  {"domain": "Security", "responses": [{"question": "...", "answer": "..."}]}
Or flat: [{"question": "...", "answer": "...", "domain": "..."}]
"""

import json
import logging
from pathlib import Path

from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

HISTORICAL_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "historical"


def load_historical_data() -> int:
    """
    Load all JSON files from data/historical/ into the vector store.

    Returns:
        Total number of documents added.
    """
    vector_store = get_vector_store()
    vector_store.reset_collection()

    all_responses: list[dict] = []
    if not HISTORICAL_DATA_DIR.exists():
        logger.warning("Historical data dir does not exist: %s", HISTORICAL_DATA_DIR)
        return 0

    for path in HISTORICAL_DATA_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    if "question" in item and "answer" in item:
                        item.setdefault("domain", _domain_from_filename(path.stem))
                        all_responses.append(item)
            elif isinstance(data, dict):
                domain = data.get("domain", _domain_from_filename(path.stem))
                for r in data.get("responses", data.get("items", [])):
                    if "question" in r and "answer" in r:
                        all_responses.append({
                            "question": r["question"],
                            "answer": r["answer"],
                            "domain": r.get("domain", domain),
                            "tender_id": r.get("tender_id"),
                            "date": r.get("date"),
                        })
        except Exception as e:
            logger.error("Failed to load %s: %s", path, e)

    if not all_responses:
        logger.info("No historical responses to load")
        return 0

    n = vector_store.add_historical_responses(all_responses)
    logger.info("Loaded %d historical responses", n)
    return n


def _domain_from_filename(stem: str) -> str:
    """Infer domain from filename, e.g. security_responses -> Security."""
    parts = stem.replace("_", " ").replace("-", " ").split()
    if not parts:
        return "General"
    return parts[0].title()
