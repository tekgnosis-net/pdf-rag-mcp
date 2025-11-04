from __future__ import annotations

import logging
from pathlib import Path

from .base import BasePDFParser

LOGGER = logging.getLogger(__name__)


class DoclingParser(BasePDFParser):
    """Parse PDFs into markdown using the Docling document converter."""

    def __init__(self) -> None:
        try:
            from docling.document_converter import DocumentConverter  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise ImportError("Docling is required for the Docling parser. Install docling.") from exc

        self._converter = DocumentConverter()

    def parse_to_markdown(self, pdf_path: Path) -> str:
        path = self._ensure_path(pdf_path)
        LOGGER.debug("Converting PDF with Docling: %s", path)
        result = self._converter.convert(str(path))
        markdown = result.document.export_to_markdown()
        return markdown.strip()
