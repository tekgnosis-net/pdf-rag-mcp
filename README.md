# PDF RAG MCP Serverdocker run --rm -p 8000:8000 --gpus all -e EMBEDDING_DEVICE=cuda pdf-rag-mcp

docker run --rm -p 8000:8000 \

Process large collections of PDFs into a Retrieval Augmented Generation (RAG) knowledge base with a queue-aware FastAPI backend, LanceDB vector search, SQLite metadata, and a Chakra UI dashboard. The project also exposes the corpus through the Model Context Protocol (MCP) so agents and IDEs can query the same documents used by the web UI.docker build -t pdf-rag-mcp .

docker run --rm -p 8000:8000 pdf-rag-mcp

## Featuresdocker compose up --build

Set `EMBEDDING_DEVICE=cuda` to trigger a runtime upgrade of PyTorch (and packages listed in `TORCH_CUDA_PACKAGES`) from `TORCH_CUDA_INDEX_URL`. With the NVIDIA Container Toolkit installed you can enable GPUs in Compose by uncommenting the provided stanza or with:

- Configurable ingestion pipeline with PyMuPDF or Docling parsing and local/OpenAI embeddings.

- Bounded task queue with worker threads, progress callbacks, and SHA-256 deduplication.```bash

- Thread-safe SQLite markdown repository and LanceDB vector store shared by REST, MCP, and the watcher.docker run --rm --gpus all -p 8000:8000 -e EMBEDDING_DEVICE=cuda ghcr.io/tekgnosis-net/pdf-rag-mcp:latest

- Recursive directory watcher for drop-and-process workflows under `<DATA_DIR>/pdfs`.```

- Unified FastAPI server providing REST endpoints, MCP transport, and static frontend assets.

- React + Chakra UI dashboard for queue monitoring and semantic search.### Persistent data & watcher mapping



## Architecture at a glance```yaml

services:

```  app:

src/    image: ghcr.io/tekgnosis-net/pdf-rag-mcp:latest

  backend/    volumes:

    api.py           # REST + MCP endpoints and job manager      - ./data:/app/data            # persists DB + vectors

    processor.py     # Queue, workers, parsing and embedding pipeline      - ./pdfs:/app/data/pdfs       # exposes the default WATCH_DIR

    config.py        # Environment-driven settings    env_file: .env

    storage/         # SQLite MarkdownRepository + LanceDB VectorStore```

    parsers/         # PyMuPDF and Docling adapters (BasePDFParser)

    embeddings/      # EmbeddingManager (local sentence-transformers or OpenAI)### Docker image size

  frontend/

    src/             # React + Chakra UI SPA```bash

    package.jsondocker image inspect ghcr.io/tekgnosis-net/pdf-rag-mcp:latest --format='{{.Size}}'

```# or

docker images | grep tekgnosis-net/pdf-rag-mcp

## Quick start```



1. **Install prerequisites**: Python 3.11+, Node.js 20+, Docker (optional), NVIDIA Container Toolkit for GPU ingestion.---

2. **Backend setup**

   ```bash## 6. Directory watcher

   python -m venv .venv

   source .venv/bin/activate- Enabled by default (`WATCH_ENABLED=true`).

   pip install -r requirements.txt- Polls `WATCH_DIR` (default `<DATA_DIR>/pdfs`) every `WATCH_POLL_INTERVAL` seconds.

   ```- Each file is processed once; existing entries in the Markdown repository are skipped.

3. **Frontend build**- Failures are tracked in SQLite. After `MAX_PROCESS_ATTEMPTS` the file is blacklisted.

   ```bash- Successful ingests clear the failure counter.

   cd src/frontend

   npm installCustomize the watcher via environment variables or Compose overrides:

   npm run build

   ``````yaml

4. **Run locally**services:

   ```bash  app:

   uvicorn src.backend.api:app --host 0.0.0.0 --port 8000 --reload    environment:

   ```      - WATCH_DIR=/app/data/incoming

   For hot reload UI development, run `npm run dev` in `src/frontend` (serves <http://localhost:5173>). Without it, FastAPI serves the built assets from `frontend/dist`.      - WATCH_POLL_INTERVAL=15

      - MAX_PROCESS_ATTEMPTS=5

## Configuration```



Settings are driven by environment variables (see `.env.sample`).When `DATA_DIR` is moved (e.g. `DATA_DIR=/var/lib/pdf-rag`), the watcher automatically watches `/var/lib/pdf-rag/pdfs` unless `WATCH_DIR` is explicitly set.



| Variable | Default | Purpose |---

| --- | --- | --- |

| `PDF_PARSER` | `pymupdf` | Parser backend (`pymupdf` or `docling`). |## 7. Extending the system

| `EMBEDDING_BACKEND` | `local` | `local` sentence-transformers or `openai` remote embeddings. |

| `SENTENCE_TRANSFORMER_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model name. |- **Custom parsers:** implement `BasePDFParser` and register it with `PDFProcessor`.

| `EMBEDDING_DEVICE` | `cpu` | `cpu` or `cuda`; when `cuda`, CUDA wheels install at runtime. |- **Chunking strategies:** replace `EmbeddingManager.chunk_markdown` for domain-specific segments.

| `OPENAI_BASE_URL` / `OPENAI_MODEL` / `OPENAI_API_KEY` | – | Required when using remote embeddings. |- **LLM augmentations:** add REST/MCP endpoints that use stored markdown + embeddings.

| `DATABASE_URL` | `sqlite:///data/markdown.db` | SQLite metadata store. |

| `VECTOR_STORE_PATH` | `data/vector_store` | LanceDB directory. |---

| `DATA_DIR` | `data` | Base path for runtime artifacts. |

| `FRONTEND_DIST_PATH` | `frontend/dist` | Static assets served by FastAPI. |## 8. Troubleshooting

| `PROCESS_WORKERS` | `4` | Worker thread count. |

| `PROCESS_QUEUE_MAXSIZE` | `100` | Max queued tasks before backpressure. || Symptom | Suggested fix |

| `WATCH_ENABLED` | `true` | Toggle directory watcher. || --- | --- |

| `WATCH_DIR` | `<DATA_DIR>/pdfs` | Origin folder recursively scanned for PDFs. || PyMuPDF import errors | Confirm required system libraries are installed (see `Dockerfile`). |

| `WATCH_POLL_INTERVAL` | `10` | Seconds between scans. || Docling OCR issues | Ensure models download successfully and disk space is available. |

| `MAX_PROCESS_ATTEMPTS` | `10` | Failures before a file is blacklisted. || Empty search results | Check logs for embedding creation and ensure LanceDB contains vectors (`data/vector_store`). |

| OpenAI/remote errors | Verify `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. |

Store credentials such as `OPENAI_API_KEY` in `.env` (ignored by git) or a platform secret store.

---

## Processing pipeline

## 9. License

1. **Queueing** – uploads, watcher discoveries, and synchronous calls become `ProcessingTask`s in a bounded queue.

2. **Worker pool** – configurable daemon threads dequeue tasks, fire lifecycle callbacks, and isolate failures.MIT License © 2025 The Project Contributors

3. **Metadata enrichment** – filesystem stats merge with caller-provided metadata.
4. **Parsing** – PyMuPDF or Docling produces markdown.
5. **Deduplication** – SHA-256 hash lookups skip re-ingesting identical content.
6. **Persistence** – markdown saved to SQLite; embeddings chunked and added to LanceDB with cosine index.

REST endpoints, MCP tools, and the watcher all use this pipeline for consistent behavior.

## Directory watcher

- Enabled by default (`WATCH_ENABLED=true`).
- Recursively scans `WATCH_DIR` for `*.pdf` files.
- Skips paths already stored or blacklisted after repeated failures.
- Adds tasks to the shared queue so watcher processing respects backpressure and emits progress events.
- Disable by setting `WATCH_ENABLED=false` or adjust poll interval and retry thresholds via environment variables.

## REST and MCP APIs

| Path | Method | Description |
| --- | --- | --- |
| `/api/process` | POST | Upload one or more PDFs (multipart). Returns job descriptors. |
| `/api/process/status` | GET | Current queue, in-progress, completed, and failed job summaries. |
| `/api/search` | GET | Semantic search (`?query=...&top_k=5`). |
| `/api/markdown` | GET | Fetch stored markdown by `document_id` or `title`. |
| `/.well-known/mcp/server` | GET | MCP discovery document. |
| `/mcp/tools/query_pdfs` | POST | MCP search tool (`{"query": "...", "top_k": 5}`). |
| `/mcp/tools/fetch_markdown` | POST | MCP tool to load markdown (`{"document_id": 1}` or `{ "title": "..." }`). |

Claude Desktop snippet:
```json
{
  "mcpServers": {
    "pdf-rag": {
      "type": "http",
      "url": "http://localhost:8000"
    }
  }
}
```

## Frontend dashboard

- `npm run dev` – Vite dev server with hot reload.
- `npm run build` – production build served by FastAPI.
- `npm run ci:build` – TypeScript type-check + production build (mirrors CI).

The UI provides a processing queue view (live job progress, retries, failures) and a semantic search view showing ranked chunks with metadata and markdown excerpts.

## Docker and Compose

```bash
# Pull published image (recommended)
docker run --rm -p 8000:8000 ghcr.io/tekgnosis-net/pdf-rag-mcp:latest

# Build locally
docker build -t pdf-rag-mcp .
docker run --rm -p 8000:8000 pdf-rag-mcp

# Docker Compose (uses GHCR image by default)
docker compose up --build
```

GPU acceleration:
```bash
docker run --rm -p 8000:8000 --gpus all \
  -e EMBEDDING_DEVICE=cuda \
  ghcr.io/tekgnosis-net/pdf-rag-mcp:latest
```

Mount `./data` to `/app/data` for persistent SQLite/LanceDB storage and map a host folder to `/app/data/pdfs` to feed the watcher.

## Development workflow and CI parity

Run the same checks GitHub Actions enforces before pushing:

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
(cd src/frontend && npm ci && npm run ci:build)
docker build -t pdf-rag-mcp-local .
```

These steps match the `Test, Build and Publish` workflow (lint, pytest, frontend typecheck/build, Docker image).

## Troubleshooting

| Symptom | Suggested remedy |
| --- | --- |
| `sentence_transformers` missing | Install optional dependency or switch to `EMBEDDING_BACKEND=openai`. |
| Watcher ignores files | Confirm PDFs live under `WATCH_DIR`, are not blacklisted, and the queue is not full. |
| Duplicate entries appear | Ensure source markdown differs; dedupe operates on parsed content hashes. |
| OpenAI errors | Verify `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` values. |
| Empty search results | Check logs for embedding creation and confirm LanceDB directory is writable. |

## License

MIT License © 2025 The Project Contributors
