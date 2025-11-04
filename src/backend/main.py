from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Settings
from .processor import PDFProcessor

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process PDFs into markdown and embeddings")
    parser.add_argument("pdf", type=Path, help="Path to the PDF file to process")
    parser.add_argument("--title", type=str, help="Optional title override for the document")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Settings()
    processor = PDFProcessor(settings)
    record = processor.process_pdf(args.pdf, title=args.title)
    LOGGER.info("Stored markdown for document %s (id=%s)", record.title, record.id)


if __name__ == "__main__":
    main()
