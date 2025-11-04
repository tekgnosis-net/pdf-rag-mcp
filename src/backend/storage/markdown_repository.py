from __future__ import annotations

import datetime as dt
import sqlite3
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


class MarkdownRepository:
    """Persist markdown exports of PDFs in a lightweight SQLite database."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite"):
            raise ValueError("Only sqlite databases are supported in this reference implementation")

        self.database_url = database_url
        self._db_path = self._resolve_db_path(database_url)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
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
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, title: str, source_path: Path, markdown: str) -> MarkdownRecord:
        now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (title, source_path, markdown, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (title, str(source_path), markdown, now.isoformat()),
            )
            doc_id = int(cursor.lastrowid)
            conn.commit()
        return MarkdownRecord(id=doc_id, title=title, source_path=str(source_path), markdown=markdown, created_at=now)

    def get_by_id(self, document_id: int) -> Optional[MarkdownRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
            if not row:
                return None
            return MarkdownRecord(
                id=row["id"],
                title=row["title"],
                source_path=row["source_path"],
                markdown=row["markdown"],
                created_at=dt.datetime.fromisoformat(row["created_at"]),
            )

    def get_by_title(self, title: str) -> Optional[MarkdownRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE title = ?", (title,)).fetchone()
            if not row:
                return None
            return MarkdownRecord(
                id=row["id"],
                title=row["title"],
                source_path=row["source_path"],
                markdown=row["markdown"],
                created_at=dt.datetime.fromisoformat(row["created_at"]),
            )

    def list_all(self) -> list[MarkdownRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
            return [
                MarkdownRecord(
                    id=row["id"],
                    title=row["title"],
                    source_path=row["source_path"],
                    markdown=row["markdown"],
                    created_at=dt.datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]
