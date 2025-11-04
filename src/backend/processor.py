from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional
import threading
import time
from dataclasses import dataclass

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
        # start directory watcher (daemon) if enabled
        if self.settings.watch_enabled:
            watcher = DirectoryWatcher(self, self.markdown_repository, self.settings)
            watcher.start()

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


@dataclass
class DirectoryWatcher:
    """Simple polling directory watcher that attempts to process unprocessed PDFs.

    - Watches `settings.watch_dir` for new/changed PDFs.
    - Skips files already in the MarkdownRepository (by source_path).
    - Tracks failures in `failed_files` table and blacklists after configured attempts.
    """

    processor: PDFProcessor
    markdown_repo: MarkdownRepository
    settings: Settings
    _thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="pdf-watcher")
        self._thread.start()
        LOGGER.info("Started DirectoryWatcher on %s", self.settings.watch_dir)

    def _run(self) -> None:
        poll = max(1, int(self.settings.watch_poll_interval))
        while True:
            try:
                self._scan_once()
            except Exception:  # pragma: no cover - defensive loop
                LOGGER.exception("DirectoryWatcher encountered an error")
            time.sleep(poll)

    def _scan_once(self) -> None:
        watch_dir = Path(self.settings.watch_dir)
        if not watch_dir.exists():
            return
        for path in watch_dir.iterdir():
            if not path.is_file():
                continue
            if not path.name.lower().endswith(".pdf"):
                continue
            # skip if we already have a record for this source path
            try:
                existing = self.markdown_repo.get_by_source_path(str(path))
            except Exception:  # pragma: no cover - defensive db issue
                LOGGER.exception("Failed to query repository for %s", path)
                existing = None
            if existing:
                continue
            # skip if blacklisted
            try:
                if self.markdown_repo.is_blacklisted(str(path)):
                    LOGGER.debug("Skipping blacklisted file %s", path)
                    continue
            except Exception:
                LOGGER.exception("Failed to check blacklist for %s", path)

            # Attempt processing
            LOGGER.info("Watcher: attempting to process %s", path)
            try:
                record = self.processor.process_pdf(path, title=path.stem)
                # success: clear any failure state
                try:
                    self.markdown_repo.clear_failures(str(path))
                except Exception:
                    LOGGER.exception("Failed to clear failure state for %s", path)
                LOGGER.info("Watcher: successfully processed %s -> id=%s", path, record.id)
            except Exception as exc:  # pragma: no cover - runtime failure handling
                LOGGER.exception("Watcher: processing %s failed", path)
                try:
                    info = self.markdown_repo.record_failure(str(path), str(exc), self.settings.max_process_attempts)
                    if info.get("blacklisted"):
                        LOGGER.warning("File %s blacklisted after %s attempts", path, info.get("attempts"))
                    else:
                        LOGGER.info("Recorded failure for %s (attempt %s)", path, info.get("attempts"))
                except Exception:
                    LOGGER.exception("Watcher: failed to record failure for %s", path)
