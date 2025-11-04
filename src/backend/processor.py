from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import Settings
from .embeddings import EmbeddingManager
from .logging_config import configure_logging
from .parsers import BasePDFParser, DoclingParser, PyMuPDFParser
from .storage import MarkdownRecord, MarkdownRepository, VectorStore

LOGGER = logging.getLogger(__name__)


class PDFProcessor:
    """Coordinates parsing, embedding generation, and persistence."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        configure_logging(self.settings)
        self.settings.ensure_directories()

        self.parser = self._create_parser(self.settings.parser_backend)
        self.markdown_repository = MarkdownRepository(self.settings.database_url)
        self.embedding_manager = EmbeddingManager(self.settings)
        embedding_dim = self.settings.embedding_dimension or None
        self.vector_store = VectorStore(self.settings.vector_store_path, embedding_dim)

    def _create_parser(self, backend: str) -> BasePDFParser:
        backend = backend.lower()
        if backend == "pymupdf":
            LOGGER.info("Using PyMuPDF parser backend")
            return PyMuPDFParser()
        if backend == "docling":
            LOGGER.info("Using Docling parser backend")
            return DoclingParser()
        raise ValueError(f"Unsupported parser backend: {backend}")

    def process_pdf(self, pdf_path: Path, title: Optional[str] = None) -> MarkdownRecord:
        path = Path(pdf_path).expanduser().resolve()
        if title is None:
            title = path.stem

        LOGGER.info("Processing PDF %s with title %s", path, title)
        markdown = self.parser.parse_to_markdown(path)
        record = self.markdown_repository.save(title=title, source_path=path, markdown=markdown)

        chunks = list(EmbeddingManager.chunk_markdown(markdown))
        LOGGER.debug("Generated %d chunks for embeddings", len(chunks))
        embeddings = self.embedding_manager.embed_documents(chunks)
        self.vector_store.add_embeddings(record.id, embeddings)
        LOGGER.info("Persisted markdown and embeddings for %s", title)
        return record

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, object]]:
        LOGGER.info("Searching vector store for query: %s", query)
        embedding_results = self.embedding_manager.embed_documents([query])
        if not embedding_results:
            return []
        query_embedding = embedding_results[0]
        matches = self.vector_store.similarity_search(query_embedding.vector, top_k=top_k)
        results: List[Dict[str, object]] = []
        for match in matches:
            document = self.markdown_repository.get_by_id(match.document_id)
            results.append(
                {
                    "document_id": match.document_id,
                    "title": document.title if document else "Unknown",
                    "chunk_index": match.chunk_index,
                    "similarity": match.similarity,
                    "text": match.text,
                    "provider": match.provider,
                    "model": match.model,
                }
            )
        return results

    def fetch_markdown_by_id(self, document_id: int) -> Optional[str]:
        record = self.markdown_repository.get_by_id(document_id)
        return record.markdown if record else None

    def fetch_markdown_by_title(self, title: str) -> Optional[str]:
        record = self.markdown_repository.get_by_title(title)
        return record.markdown if record else None
