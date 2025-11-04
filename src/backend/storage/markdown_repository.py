from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MarkdownRecord:
    id: int
    title: str
    source_path: str
    markdown: str
    created_at: dt.datetime
    content_hash: Optional[str] = None
    metadata: Optional[dict] = None


class MarkdownRepository:
    """Persist markdown exports of PDFs in a lightweight SQLite database."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite"):
            raise ValueError("Only sqlite databases are supported in this reference implementation")

        self.database_url = database_url
        self._db_path = self._resolve_db_path(database_url)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._ensure_schema()

    @staticmethod
    def _resolve_db_path(database_url: str) -> Path:
        if database_url.startswith("sqlite:///"):
            return Path(database_url.replace("sqlite:///", "")).expanduser().resolve()
        if database_url.startswith("sqlite://"):
            raise ValueError("Relative sqlite URLs are not supported. Use sqlite:///absolute/path.db")
        return Path(database_url)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content_hash TEXT,
                    metadata TEXT
                )
                """
            )
                columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
                if "content_hash" not in columns:
                    conn.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
                if "metadata" not in columns:
                    conn.execute("ALTER TABLE documents ADD COLUMN metadata TEXT")
                # Track failed processing attempts and blacklist status
                conn.execute(
                """
                CREATE TABLE IF NOT EXISTS failed_files (
                    source_path TEXT PRIMARY KEY,
                    attempts INTEGER NOT NULL,
                    last_error TEXT,
                    blacklisted INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
                conn.commit()

    def save(
        self,
        title: str,
        source_path: Path,
        markdown: str,
        *,
        content_hash: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> MarkdownRecord:
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        metadata_json = json.dumps(metadata, sort_keys=True) if metadata else None
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO documents (title, source_path, markdown, created_at, content_hash, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (title, str(source_path), markdown, now.isoformat(), content_hash, metadata_json),
                )
                doc_id = int(cursor.lastrowid)
                conn.commit()
        return MarkdownRecord(
            id=doc_id,
            title=title,
            source_path=str(source_path),
            markdown=markdown,
            created_at=now,
            content_hash=content_hash,
            metadata=metadata,
        )

    def get_by_id(self, document_id: int) -> Optional[MarkdownRecord]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
                if not row:
                    return None
                return self._row_to_record(row)

    def get_by_title(self, title: str) -> Optional[MarkdownRecord]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE title = ?", (title,)).fetchone()
                if not row:
                    return None
                return self._row_to_record(row)

    def get_by_source_path(self, source_path: str) -> Optional[MarkdownRecord]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE source_path = ?", (str(source_path),)).fetchone()
                if not row:
                    return None
                return self._row_to_record(row)

    def get_by_hash(self, content_hash: str) -> Optional[MarkdownRecord]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM documents WHERE content_hash = ?", (content_hash,)).fetchone()
                if not row:
                    return None
                return self._row_to_record(row)

    def record_failure(self, source_path: str, error: str, max_attempts: int) -> dict:
        """Increment failure counter for a file and mark blacklisted if attempts exceed max_attempts.

        Returns a dict with attempts and blacklisted status.
        """
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT attempts, blacklisted FROM failed_files WHERE source_path = ?", (str(source_path),)).fetchone()
                if not row:
                    attempts = 1
                    blacklisted = 0
                    conn.execute(
                        "INSERT INTO failed_files (source_path, attempts, last_error, blacklisted, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (str(source_path), attempts, error, blacklisted, now),
                    )
                else:
                    attempts = int(row["attempts"]) + 1
                    blacklisted = int(row["blacklisted"])
                    if attempts >= max_attempts:
                        blacklisted = 1
                    conn.execute(
                        "UPDATE failed_files SET attempts = ?, last_error = ?, blacklisted = ?, updated_at = ? WHERE source_path = ?",
                        (attempts, error, blacklisted, now, str(source_path)),
                    )
                conn.commit()
        return {"attempts": attempts, "blacklisted": bool(blacklisted)}

    def clear_failures(self, source_path: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM failed_files WHERE source_path = ?", (str(source_path),))
                conn.commit()

    def is_blacklisted(self, source_path: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT blacklisted FROM failed_files WHERE source_path = ?", (str(source_path),)).fetchone()
                if not row:
                    return False
                return bool(row["blacklisted"])

    def list_all(self) -> list[MarkdownRecord]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
                return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> MarkdownRecord:
        metadata = None
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                metadata = {"raw": row["metadata"]}
        return MarkdownRecord(
            id=row["id"],
            title=row["title"],
            source_path=row["source_path"],
            markdown=row["markdown"],
            created_at=dt.datetime.fromisoformat(row["created_at"]),
            content_hash=row["content_hash"],
            metadata=metadata,
        )
