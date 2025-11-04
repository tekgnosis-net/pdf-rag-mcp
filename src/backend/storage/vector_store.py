from __future__ import annotations

import datetime as dt
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import lancedb
import pyarrow as pa
from pyarrow import types as pa_types

from ..embeddings.embedding_manager import EmbeddingResult


LOGGER = logging.getLogger(__name__)


@dataclass
class VectorStoreRecord:
    document_id: int
    chunk_index: int
    similarity: float
    text: str
    provider: str
    model: str


class VectorStore:
    """Vector store implementation backed by LanceDB for similarity search."""

    TABLE_NAME = "embeddings"

    def __init__(self, db_path: str, embedding_dim: Optional[int] = None) -> None:
        self._db_root = Path(db_path).expanduser().resolve()
        self._db_root.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._db_root))
        self._embedding_dim: Optional[int] = embedding_dim if embedding_dim and embedding_dim > 0 else None
        self._lock = threading.RLock()
        self._table = self._ensure_table()

    def _vector_field(self, dimension: int) -> pa.Field:
        return pa.field("vector", pa.list_(pa.float32(), list_size=dimension))

    def _ensure_table(self):
        with self._lock:
            if self.TABLE_NAME in self._db.table_names():
                table = self._db.open_table(self.TABLE_NAME)
                vector_field = table.schema.field("vector")
                if pa_types.is_list(vector_field.type) and not pa_types.is_fixed_size_list(vector_field.type):
                    LOGGER.warning("Detected legacy LanceDB schema; rebuilding embeddings table with fixed-size vectors")
                    rows = table.to_arrow().to_pylist()
                    self._db.drop_table(self.TABLE_NAME)
                    self._embedding_dim = self._embedding_dim or (len(rows[0]["vector"]) if rows else None)
                    table = self._create_table(self._embedding_dim)
                    if rows:
                        table.add(rows)
                else:
                    if self._embedding_dim is None and pa_types.is_fixed_size_list(vector_field.type):
                        self._embedding_dim = vector_field.type.list_size
                if table and not table.list_indices():
                    table.create_index(column="vector", metric="cosine")
                return table

            table = self._create_table(self._embedding_dim)
            return table

    def _create_table(self, dimension: Optional[int]):
        if dimension is None:
            return None

        schema = pa.schema(
            [
                pa.field("document_id", pa.int64()),
                pa.field("chunk_index", pa.int32()),
                self._vector_field(dimension),
                pa.field("provider", pa.string()),
                pa.field("model", pa.string()),
                pa.field("text", pa.string()),
                pa.field("created_at", pa.timestamp("us")),
            ]
        )
        table = self._db.create_table(self.TABLE_NAME, schema=schema)
        table.create_index(column="vector", metric="cosine")
        return table

    def add_embeddings(self, document_id: int, embeddings: Iterable[EmbeddingResult]) -> None:
        embeddings = list(embeddings)
        if not embeddings:
            return

        with self._lock:
            rows = []
            first_vector = embeddings[0].vector
            if self._embedding_dim is None:
                self._embedding_dim = len(first_vector)
                if self._table is None:
                    self._table = self._create_table(self._embedding_dim)

            if self._table is None and self._embedding_dim is not None:
                self._table = self._create_table(self._embedding_dim)

            if self._embedding_dim is None or self._table is None:
                raise ValueError("Embedding dimension could not be determined for LanceDB table creation")

            for chunk_index, embedding in enumerate(embeddings):
                if len(embedding.vector) != self._embedding_dim:
                    raise ValueError(
                        f"Embedding dimension mismatch: expected {self._embedding_dim}, got {len(embedding.vector)}"
                    )
                rows.append(
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "vector": embedding.vector,
                        "provider": embedding.provider,
                        "model": embedding.model,
                        "text": embedding.text,
                        "created_at": dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc),
                    }
                )
            if rows:
                self._table.add(rows)
                if not self._table.list_indices():
                    self._table.create_index(column="vector", metric="cosine")

    def similarity_search(self, query_vector: List[float], top_k: int = 5) -> List[VectorStoreRecord]:
        if not query_vector:
            return []

        with self._lock:
            if self._table is None or self._table.count_rows() == 0:
                return []

            results = self._table.search(query_vector).metric("cosine").limit(top_k).to_list()
            records: List[VectorStoreRecord] = []
            for row in results:
                distance = float(row.get("_distance", row.get("score", 1.0)))
                similarity = max(0.0, 1.0 - distance)
                records.append(
                    VectorStoreRecord(
                        document_id=int(row["document_id"]),
                        chunk_index=int(row["chunk_index"]),
                        similarity=similarity,
                        text=row.get("text", ""),
                        provider=row.get("provider", "unknown"),
                        model=row.get("model", "unknown"),
                    )
                )
            return records
