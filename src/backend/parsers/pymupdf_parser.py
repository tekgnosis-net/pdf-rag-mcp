from __future__ import annotations

import logging
from pathlib import Path

from .base import BasePDFParser

LOGGER = logging.getLogger(__name__)


class PyMuPDFParser(BasePDFParser):
    """Parse PDFs into markdown using the PyMuPDF backend."""

    def parse_to_markdown(self, pdf_path: Path) -> str:
        path = self._ensure_path(pdf_path)
        try:
            import fitz  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportError(
                "PyMuPDF (fitz) is required for the PyMuPDF parser. Install pymupdf."
            ) from exc

        LOGGER.debug("Opening PDF with PyMuPDF: %s", path)
        document = fitz.open(path)
        try:
            markdown_chunks = []
            for page in document:
                markdown = page.get_text("markdown")
                markdown_chunks.append(markdown.strip())
            LOGGER.debug("Extracted %d pages from %s", len(markdown_chunks), path)
            return "\n\n".join(chunk for chunk in markdown_chunks if chunk)
        finally:
            document.close()
