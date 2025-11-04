from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BasePDFParser(ABC):
    """Abstract parser interface for converting PDFs to markdown."""

    @abstractmethod
    def parse_to_markdown(self, pdf_path: Path) -> str:
        """Return a markdown representation of the PDF."""

    @staticmethod
    def _ensure_path(pdf_path: Path) -> Path:
        resolved = pdf_path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"PDF not found: {resolved}")
        if resolved.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a PDF file, received: {resolved.suffix}")
        return resolved
