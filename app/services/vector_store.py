"""
ChromaDB vector store service for historical tender response storage and retrieval.

Infrastructure service — agents call it but don't know its internals.
"""

import logging
import uuid
from typing import Any

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class FastEmbedEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Custom embedding function using fastembed for local, zero-API-cost embeddings.
    ChromaDB does not ship with a dense FastEmbed function, so we wrap it.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)

    def __call__(self, input: Documents) -> Embeddings:
        """Embed the input documents."""
        if not input:
            return []
        embeddings = list(self._model.embed(input))
        return [e.tolist() for e in embeddings]


class VectorStoreService:
    """Manages ChromaDB operations for historical tender response storage and retrieval."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._embedding_fn = FastEmbedEmbeddingFunction(model_name=settings.embedding_model)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "VectorStoreService initialized: collection=%s, persist_dir=%s",
            settings.chroma_collection_name,
            settings.chroma_persist_dir,
        )

    def add_historical_responses(self, responses: list[dict]) -> int:
        """
        Add historical tender Q&A pairs to the vector store.

        Each response dict should have:
        - question: str
        - answer: str
        - domain: str
        - tender_id: str (optional)
        - date: str (optional)

        Returns:
            Number of documents added.
        """
        if not responses:
            logger.warning("add_historical_responses called with empty list")
            return 0

        ids = [str(uuid.uuid4()) for _ in responses]
        documents = [r["question"] for r in responses]
        metadatas: list[dict[str, Any]] = []
        for r in responses:
            meta: dict[str, Any] = {
                "answer": r["answer"],
                "domain": r["domain"],
            }
            if "tender_id" in r and r["tender_id"]:
                meta["tender_id"] = str(r["tender_id"])
            if "date" in r and r["date"]:
                meta["date"] = str(r["date"])
            metadatas.append(meta)

        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Added %d historical responses to vector store", len(responses))
        return len(responses)

    def search_similar(
        self,
        query: str,
        domain: str | None = None,
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Search for similar historical questions, optionally filtered by domain.

        Args:
            query: The new tender question to match against.
            domain: If provided, filter results to this domain only.
            top_k: Number of results (defaults to settings.similarity_top_k).

        Returns:
            List of dicts with keys: question, answer, domain, score.
            Score is similarity (higher = more similar). Sorted by score descending.
        """
        k = top_k if top_k is not None else self._settings.similarity_top_k
        threshold = self._settings.similarity_threshold

        where_filter = {"domain": domain} if domain else None

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("ChromaDB query failed (possibly empty collection): %s", e)
            return []

        if not results or not results["ids"] or not results["ids"][0]:
            return []

        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        output: list[dict] = []
        for i, doc in enumerate(documents):
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = distances[i] if i < len(distances) else 1.0
            score = 1.0 - dist
            if score < threshold:
                continue
            output.append(
                {
                    "question": doc,
                    "answer": meta.get("answer", ""),
                    "domain": meta.get("domain", ""),
                    "score": round(score, 4),
                }
            )

        output.sort(key=lambda x: x["score"], reverse=True)
        return output

    def get_collection_stats(self) -> dict:
        """Return stats about the vector store: total docs, domains breakdown."""
        try:
            count = self._collection.count()
        except Exception:
            count = 0

        domains: dict[str, int] = {}
        if count > 0:
            try:
                all_data = self._collection.get(include=["metadatas"])
                metas = all_data.get("metadatas") or []
                for m in metas:
                    if m and "domain" in m:
                        d = m["domain"]
                        domains[d] = domains.get(d, 0) + 1
            except Exception as e:
                logger.warning("Could not compute domain stats: %s", e)

        return {"total_documents": count, "domains": domains}

    def reset_collection(self) -> None:
        """Delete and recreate the collection. Used for testing/reset."""
        self._client.delete_collection(name=self._settings.chroma_collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._settings.chroma_collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store collection reset")


_vector_store_instance: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    """Get the shared VectorStoreService instance (singleton)."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreService(get_settings())
    return _vector_store_instance
