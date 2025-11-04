import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """Application settings resolved from environment variables."""

    parser_backend: str = field(default_factory=lambda: os.getenv("PDF_PARSER", "pymupdf"))
    embedding_backend: str = field(default_factory=lambda: os.getenv("EMBEDDING_BACKEND", "local"))
    sentence_transformer_model: str = field(
        default_factory=lambda: os.getenv(
            "SENTENCE_TRANSFORMER_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    )
    embedding_device: str = field(default_factory=lambda: os.getenv("EMBEDDING_DEVICE", "cpu"))
    embedding_dimension: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSION", "0") or "0")
    )
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "text-embedding-3-large"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/markdown.db"))
    vector_store_path: str = field(default_factory=lambda: os.getenv("VECTOR_STORE_PATH", "data/vector_store.db"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")))
    frontend_dist: Path = field(default_factory=lambda: Path(os.getenv("FRONTEND_DIST_PATH", "frontend/dist")))

    def ensure_directories(self) -> None:
        """Create expected data directories on disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        vector_dir = Path(self.vector_store_path).expanduser().resolve().parent
        vector_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite"):
            db_path = self.database_url.replace("sqlite:///", "")
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
