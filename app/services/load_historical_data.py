"""
Load historical tender responses from data/historical/ into ChromaDB.

Expected JSON format per file:
  [{"question": "...", "answer": "...", "domain": "..."}]
Or: {"domain": "X", "responses": [{"question": "...", "answer": "..."}]}

Usage:
    python -m app.services.load_historical_data
"""

import json
import logging
from pathlib import Path

from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)

HISTORICAL_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "historical"


def _domain_from_filename(stem: str) -> str:
    """Infer domain from filename, e.g. security_responses -> Security."""
    parts = stem.replace("_", " ").replace("-", " ").split()
    if not parts:
        return "General"
    return parts[0].title()


def load_all_historical_data(data_dir: str | Path | None = None) -> dict:
    """
    Load all JSON files from the historical data directory into ChromaDB.

    Returns:
        Dict with loading stats: files_processed, total_documents, domains.
    """
    data_path = Path(data_dir) if data_dir else HISTORICAL_DATA_DIR
    stats: dict = {"files_processed": 0, "total_documents": 0, "domains": {}}

    if not data_path.exists():
        logger.warning("Historical data dir does not exist: %s", data_path)
        return stats

    vector_store = get_vector_store()
    vector_store.reset_collection()

    all_responses: list[dict] = []

    for json_file in sorted(data_path.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            file_count = 0

            if isinstance(data, list):
                for item in data:
                    if "question" in item and "answer" in item:
                        item.setdefault("domain", _domain_from_filename(json_file.stem))
                        all_responses.append(item)
                        file_count += 1
            elif isinstance(data, dict):
                domain = data.get("domain", _domain_from_filename(json_file.stem))
                for r in data.get("responses", data.get("items", [])):
                    if "question" in r and "answer" in r:
                        all_responses.append({
                            "question": r["question"],
                            "answer": r["answer"],
                            "domain": r.get("domain", domain),
                            "tender_id": r.get("tender_id"),
                            "date": r.get("date"),
                        })
                        file_count += 1

            if file_count > 0:
                stats["files_processed"] += 1
                logger.info("Loaded %s: %d documents", json_file.name, file_count)

        except Exception as e:
            logger.error("Failed to load %s: %s", json_file, e)

    if all_responses:
        n = vector_store.add_historical_responses(all_responses)
        stats["total_documents"] = n
        for r in all_responses:
            d = r.get("domain", "Unknown")
            stats["domains"][d] = stats["domains"].get(d, 0) + 1
        logger.info("Total: %d documents loaded into ChromaDB", n)
    else:
        logger.info("No historical responses to load")

    return stats


def load_historical_data() -> int:
    """
    Load historical data (for API endpoint). Returns total documents added.
    """
    stats = load_all_historical_data()
    return stats["total_documents"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    stats = load_all_historical_data()
    print(f"Loaded historical data: {stats}")
