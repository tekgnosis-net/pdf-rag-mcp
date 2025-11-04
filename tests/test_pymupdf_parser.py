from __future__ import annotations

from pathlib import Path
import sys

import pytest

try:
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - dependency guard
    pytest.skip("PyMuPDF not available", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend.parsers.pymupdf_parser import PyMuPDFParser  # noqa: E402


def test_pymupdf_parser_extracts_markdown(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PyMuPDF")
    doc.save(pdf_path)
    doc.close()

    parser = PyMuPDFParser()
    markdown = parser.parse_to_markdown(pdf_path)

    assert "Hello PyMuPDF" in markdown