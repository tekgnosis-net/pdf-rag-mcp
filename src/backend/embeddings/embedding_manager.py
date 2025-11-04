from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from ..config import Settings

LOGGER = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Container for an embedding vector and its origin metadata."""

    text: str
    vector: List[float]
    model: str
    provider: str


class EmbeddingManager:
    """Create embeddings using either local sentence transformers or OpenAI."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local_model = None
        self._openai_client = None

    def embed_documents(self, texts: Sequence[str]) -> List[EmbeddingResult]:
        if not texts:
            return []
        backend = self.settings.embedding_backend.lower()
        if backend == "local":
            return self._embed_local(texts)
        if backend == "openai":
            return self._embed_openai(texts)
        raise ValueError(f"Unsupported embedding backend: {backend}")

    def _embed_local(self, texts: Sequence[str]) -> List[EmbeddingResult]:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportError(
                "sentence-transformers is required for local embeddings."
            ) from exc

        if self._local_model is None:
            model_name = self.settings.sentence_transformer_model
            device = self._resolve_device()
            LOGGER.info("Loading sentence transformer model %s on %s", model_name, device)
            self._local_model = SentenceTransformer(model_name, device=device)

        assert self._local_model is not None
        embeddings = self._local_model.encode(list(texts), convert_to_numpy=True)
        results: List[EmbeddingResult] = []
        for text, vector in zip(texts, embeddings):
            results.append(
                EmbeddingResult(
                    text=text,
                    vector=vector.tolist(),
                    model=self.settings.sentence_transformer_model,
                    provider="sentence-transformers",
                )
            )
        return results

    def _embed_openai(self, texts: Sequence[str]) -> List[EmbeddingResult]:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportError("openai package is required for remote embeddings.") from exc

        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when using remote embeddings.")

        if self._openai_client is None:
            LOGGER.info("Configuring OpenAI embedding client against %s", self.settings.openai_base_url)
            self._openai_client = OpenAI(base_url=self.settings.openai_base_url, api_key=self.settings.openai_api_key)

        assert self._openai_client is not None
        model = self.settings.openai_model
        response = self._openai_client.embeddings.create(model=model, input=list(texts))
        data = response.data
        results: List[EmbeddingResult] = []
        for text, record in zip(texts, data):
            vector = list(record.embedding)
            results.append(EmbeddingResult(text=text, vector=vector, model=model, provider="openai"))
        return results

    def _resolve_device(self) -> str:
        device = self.settings.embedding_device.lower()
        if device == "cuda":
            return "cuda"
        return "cpu"

    @staticmethod
    def chunk_markdown(markdown: str, chunk_size: int = 700, overlap: int = 50) -> Iterable[str]:
        """Simple recursive chunker for markdown documents."""
        tokens = markdown.split()
        if not tokens:
            return []
        chunks: List[str] = []
        start = 0
        while start < len(tokens):
            end = min(len(tokens), start + chunk_size)
            chunk = " ".join(tokens[start:end])
            chunks.append(chunk)
            if end == len(tokens):
                break
            start = max(0, end - overlap)
        return chunks
