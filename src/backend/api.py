from __future__ import annotations

import datetime as dt
import logging
import queue
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .processor import PDFProcessor, ProcessingTask
from .mcp_server import create_mcp_router

LOGGER = logging.getLogger(__name__)


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


@dataclass
class ProcessingJob:
    id: str
    filename: str
    status: JobStatus
    progress: float
    queued_at: dt.datetime
    updated_at: dt.datetime
    error: Optional[str] = None
    document_id: Optional[int] = None
    title: Optional[str] = None
    source_path: Optional[Path] = None

    def to_payload(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["queued_at"] = self.queued_at.isoformat()
        payload["updated_at"] = self.updated_at.isoformat()
        if self.source_path is not None:
            payload["source_path"] = str(self.source_path)
        return payload


class ProcessingManager:
    """Handle the lifecycle of PDF processing jobs."""

    def __init__(self, processor: PDFProcessor, settings: Settings) -> None:
        self.processor = processor
        self.settings = settings
        self.upload_dir = settings.data_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, ProcessingJob] = {}
        self._lock = Lock()

    async def enqueue(self, file: UploadFile, background_tasks: BackgroundTasks) -> ProcessingJob:
        job_id = str(uuid4())
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        destination = self.upload_dir / f"{job_id}_{file.filename}"
        contents = await file.read()
        destination.write_bytes(contents)

        job = ProcessingJob(
            id=job_id,
            filename=file.filename,
            status=JobStatus.queued,
            progress=0.0,
            queued_at=now,
            updated_at=now,
            title=Path(file.filename).stem,
            source_path=destination,
        )

        with self._lock:
            self._jobs[job_id] = job

        task = ProcessingTask(
            job_id=job_id,
            source_path=destination,
            title=job.title or destination.stem,
            metadata={"ingest_source": "upload", "original_filename": file.filename},
            on_start=lambda task: self._update_job(job_id, status=JobStatus.processing, progress=5.0),
            on_progress=lambda task, progress, stage: self._update_job(job_id, status=JobStatus.processing, progress=progress),
            on_success=lambda task, record: self._on_success(job_id, record),
            on_error=lambda task, exc: self._on_failure(job_id, exc),
        )
        try:
            self.processor.submit_task(task)
        except queue.Full as exc:  # pragma: no cover - defensive, queue is blocking by default
            LOGGER.error("Processing queue is full; cannot enqueue job %s", job_id)
            raise HTTPException(status_code=503, detail="Processing queue is full, try again later") from exc

        LOGGER.info("Enqueued job %s for %s", job_id, file.filename)
        return job

    def _on_success(self, job_id: str, record) -> None:
        self._update_job(job_id, status=JobStatus.completed, progress=100.0, document_id=record.id)

    def _on_failure(self, job_id: str, exc: Exception) -> None:
        LOGGER.exception("Job %s failed: %s", job_id, exc)
        self._update_job(job_id, status=JobStatus.failed, progress=0.0, error=str(exc))

    def _update_job(
        self,
        job_id: str,
        *,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        document_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if status:
                job.status = status
            if progress is not None:
                job.progress = progress
            if document_id is not None:
                job.document_id = document_id
            if error is not None:
                job.error = error
            job.updated_at = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)

    def status_payload(self) -> Dict[str, List[Dict[str, object]]]:
        with self._lock:
            jobs = list(self._jobs.values())
        queue = [job.to_payload() for job in jobs if job.status == JobStatus.queued]
        in_progress = [job.to_payload() for job in jobs if job.status == JobStatus.processing]
        completed = [job.to_payload() for job in jobs if job.status == JobStatus.completed]
        failed = [job.to_payload() for job in jobs if job.status == JobStatus.failed]
        return {
            "queue": queue,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
        }


def create_api(settings: Optional[Settings] = None) -> FastAPI:
    config = settings or Settings()
    processor = PDFProcessor(config)
    manager = ProcessingManager(processor, config)

    app = FastAPI(title="PDF RAG MCP API", version=config.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok", "version": config.app_version}

    @app.get("/api/meta")
    async def meta() -> Dict[str, str]:
        return {"version": config.app_version}

    @app.post("/api/process")
    async def upload_pdfs(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)) -> Dict[str, List[Dict[str, object]]]:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        jobs = []
        for upload in files:
            if not upload.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail=f"Only PDF files are supported ({upload.filename})")
            job = await manager.enqueue(upload, background_tasks)
            jobs.append(job.to_payload())
        return {"jobs": jobs}

    @app.get("/api/process/status")
    async def process_status() -> Dict[str, List[Dict[str, object]]]:
        return manager.status_payload()

    @app.get("/api/search")
    async def search(query: str, top_k: int = 5) -> Dict[str, object]:
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
        results = processor.search(query, top_k=top_k)
        return {"matches": results}

    @app.get("/api/markdown")
    async def fetch_markdown(document_id: Optional[int] = None, title: Optional[str] = None) -> Dict[str, object]:
        if document_id is not None:
            markdown = processor.fetch_markdown_by_id(document_id)
        elif title:
            markdown = processor.fetch_markdown_by_title(title)
        else:
            raise HTTPException(status_code=400, detail="Provide document_id or title")
        if markdown is None:
            raise HTTPException(status_code=404, detail="Markdown not found")
        return {"markdown": markdown}

    if config.frontend_dist.exists():
        LOGGER.info("Serving frontend assets from %s", config.frontend_dist)
        app.mount("/", StaticFiles(directory=config.frontend_dist, html=True), name="frontend")
    else:
        LOGGER.warning("Frontend assets not found at %s", config.frontend_dist)

    app.include_router(create_mcp_router(settings=config, processor=processor))

    return app


app = create_api()
