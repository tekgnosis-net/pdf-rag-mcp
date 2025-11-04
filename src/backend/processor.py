from __future__ import annotations

import datetime as dt
import hashlib
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import Settings
from .embeddings import EmbeddingManager
from .logging_config import configure_logging
from .parsers import BasePDFParser, DoclingParser, PyMuPDFParser
from .storage import MarkdownRecord, MarkdownRepository, VectorStore

LOGGER = logging.getLogger(__name__)


StartCallback = Callable[["ProcessingTask"], None]
ProgressCallback = Callable[["ProcessingTask", float, str], None]
SuccessCallback = Callable[["ProcessingTask", MarkdownRecord], None]
ErrorCallback = Callable[["ProcessingTask", Exception], None]


@dataclass
class ProcessingTask:
    job_id: str
    source_path: Path
    title: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    on_start: Optional[StartCallback] = None
    on_progress: Optional[ProgressCallback] = None
    on_success: Optional[SuccessCallback] = None
    on_error: Optional[ErrorCallback] = None


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
        self._task_queue: "queue.Queue[ProcessingTask]" = queue.Queue(maxsize=max(1, self.settings.processor_queue_maxsize))
        self._workers: List[threading.Thread] = []
        self._start_workers()
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

    def submit_task(self, task: ProcessingTask, *, block: bool = True, timeout: Optional[float] = None) -> None:
        LOGGER.debug("Queueing task %s for %s", task.job_id, task.source_path)
        put_kwargs: Dict[str, object] = {}
        if not block:
            put_kwargs["block"] = False
        if timeout is not None:
            put_kwargs["timeout"] = timeout
        self._task_queue.put(task, **put_kwargs)

    def process_pdf(self, pdf_path: Path, title: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> MarkdownRecord:
        task = ProcessingTask(
            job_id=f"sync:{hashlib.sha1(str(pdf_path).encode()).hexdigest()}",
            source_path=Path(pdf_path).expanduser().resolve(),
            title=title or Path(pdf_path).stem,
            metadata=metadata or {},
        )
        return self._execute_pipeline(task)

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

    def _start_workers(self) -> None:
        worker_count = max(1, self.settings.processor_workers)
        for idx in range(worker_count):
            thread = threading.Thread(target=self._worker_loop, name=f"pdf-worker-{idx+1}", daemon=True)
            thread.start()
            self._workers.append(thread)
        LOGGER.info("Started %s processing worker(s)", worker_count)

    def _worker_loop(self) -> None:
        while True:
            task = self._task_queue.get()
            try:
                if task.job_id == "__shutdown__":
                    return
                if task.on_start:
                    task.on_start(task)
                record = self._execute_pipeline(task)
                if task.on_success:
                    task.on_success(task, record)
            except Exception as exc:  # pragma: no cover - defensive worker loop handling
                LOGGER.exception("Processing task %s failed", task.job_id)
                if task.on_error:
                    task.on_error(task, exc)
            finally:
                self._task_queue.task_done()

    def _execute_pipeline(self, task: ProcessingTask) -> MarkdownRecord:
        path = task.source_path.expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        LOGGER.info("Processing PDF %s (job %s)", path, task.job_id)
        metadata = self._collect_metadata(path, task.metadata)
        self._emit_progress(task, 15.0, "metadata")
        markdown = self._extract_markdown(path)
        self._emit_progress(task, 45.0, "parsed")
        content_hash = self._compute_hash(markdown)

        duplicate = self.markdown_repository.get_by_hash(content_hash)
        if duplicate:
            LOGGER.info("Skipping ingestion for %s; duplicate content hash matches document %s", path, duplicate.id)
            self._emit_progress(task, 100.0, "duplicate")
            return duplicate

        record = self.markdown_repository.save(
            title=task.title,
            source_path=path,
            markdown=markdown,
            content_hash=content_hash,
            metadata=metadata,
        )

        chunks = self._chunk_markdown(markdown)
        self._emit_progress(task, 65.0, "chunked")
        embeddings = self.embedding_manager.embed_documents(chunks)
        self._emit_progress(task, 85.0, "embedded")
        self.vector_store.add_embeddings(record.id, embeddings)
        LOGGER.info("Persisted markdown and embeddings for %s (job %s)", task.title, task.job_id)
        self._emit_progress(task, 100.0, "completed")
        return record

    def _collect_metadata(self, path: Path, base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        metadata: Dict[str, Any] = dict(base or {})
        try:
            stat = path.stat()
            metadata.setdefault("source_path", str(path))
            metadata.setdefault("file_size", stat.st_size)
            metadata.setdefault("modified_at", dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat())
            metadata.setdefault("created_at", dt.datetime.fromtimestamp(stat.st_ctime, tz=dt.timezone.utc).isoformat())
        except FileNotFoundError:
            pass
        return metadata

    def _extract_markdown(self, path: Path) -> str:
        return self.parser.parse_to_markdown(path)

    def _chunk_markdown(self, markdown: str) -> List[str]:
        chunks = list(EmbeddingManager.chunk_markdown(markdown))
        LOGGER.debug("Generated %d chunks for embeddings", len(chunks))
        return chunks

    def _compute_hash(self, markdown: str) -> str:
        return hashlib.sha256(markdown.encode("utf-8")).hexdigest()

    def _emit_progress(self, task: ProcessingTask, progress: float, stage: str) -> None:
        if task.on_progress:
            try:
                task.on_progress(task, progress, stage)
            except Exception:  # pragma: no cover - defensive callback guard
                LOGGER.exception("Progress callback failed for task %s", task.job_id)

    def shutdown(self, wait: bool = False) -> None:
        for _ in self._workers:
            sentinel = ProcessingTask(job_id="__shutdown__", source_path=Path("."), title="", metadata={})
            self._task_queue.put(sentinel)
        if wait:
            for thread in self._workers:
                thread.join()


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
        try:
            candidates = watch_dir.rglob("*.pdf")
        except OSError:
            LOGGER.exception("Watcher: failed to traverse %s", watch_dir)
            return
        for path in candidates:
            if not path.is_file():
                continue
            absolute_path = path.expanduser().resolve()
            # skip if we already have a record for this source path
            try:
                existing = self.markdown_repo.get_by_source_path(str(absolute_path))
            except Exception:  # pragma: no cover - defensive db issue
                LOGGER.exception("Failed to query repository for %s", absolute_path)
                existing = None
            if existing:
                continue
            # skip if blacklisted
            try:
                if self.markdown_repo.is_blacklisted(str(absolute_path)):
                    LOGGER.debug("Skipping blacklisted file %s", absolute_path)
                    continue
            except Exception:
                LOGGER.exception("Failed to check blacklist for %s", absolute_path)

            # Attempt processing
            LOGGER.info("Watcher: attempting to process %s", absolute_path)
            task = ProcessingTask(
                job_id=f"watcher:{absolute_path}",
                source_path=absolute_path,
                title=absolute_path.stem,
                metadata={"ingest_source": "watcher"},
                on_start=lambda task, watched_path=str(absolute_path): LOGGER.info("Watcher: queued task for %s", watched_path),
                on_progress=lambda task, progress, stage, watched_path=str(absolute_path): LOGGER.debug(
                    "Watcher: %s progress %.1f%% at %s", watched_path, progress, stage
                ),
                on_success=lambda task, record, watched_path=str(absolute_path): self._on_success(watched_path, record),
                on_error=lambda task, exc, watched_path=str(absolute_path): self._on_error(watched_path, exc),
            )
            try:
                self.processor.submit_task(task, block=False)
            except queue.Full:
                LOGGER.warning("Processing queue full, deferring file %s", absolute_path)
                time.sleep(self.settings.watch_poll_interval)

    def _on_success(self, path: str, record: MarkdownRecord) -> None:
        try:
            self.markdown_repo.clear_failures(path)
        except Exception:
            LOGGER.exception("Watcher: failed to clear failure state for %s", path)
        LOGGER.info("Watcher: successfully processed %s -> id=%s", path, record.id)

    def _on_error(self, path: str, exc: Exception) -> None:
        LOGGER.exception("Watcher: processing %s failed", path)
        try:
            info = self.markdown_repo.record_failure(path, str(exc), self.settings.max_process_attempts)
            if info.get("blacklisted"):
                LOGGER.warning("File %s blacklisted after %s attempts", path, info.get("attempts"))
            else:
                LOGGER.info("Recorded failure for %s (attempt %s)", path, info.get("attempts"))
        except Exception:
            LOGGER.exception("Watcher: failed to record failure for %s", path)
