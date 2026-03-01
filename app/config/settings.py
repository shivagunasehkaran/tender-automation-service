from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # OpenAI
    openai_api_key: str = ""

    # Models - cost-optimized per agent role
    classifier_model: str = "gpt-4o-mini"
    generator_model: str = "gpt-4o"
    reviewer_model: str = "gpt-4o-mini"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection_name: str = "historical_tenders"

    # Embedding (fastembed - local, zero API cost)
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Retrieval
    similarity_top_k: int = 3
    similarity_threshold: float = 0.7

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once, reused everywhere."""
    return Settings()
