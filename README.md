# PDF RAG MCP Server

Process large collections of PDFs into a Retrieval Augmented Generation (RAG) knowledge base with a queue-aware FastAPI backend, LanceDB vector search, SQLite metadata, and a Chakra UI dashboard. The Model Context Protocol (MCP) layer surfaces the same corpus to agents and IDEs, so search results stay consistent across clients.

## Features

- Configurable ingestion pipeline with PyMuPDF or Docling parsing and local/OpenAI embeddings.
- Bounded worker queue with progress callbacks, SHA-256 deduplication, and metadata enrichment.
- Thread-safe SQLite markdown repository and LanceDB vector store shared by REST, MCP, and the watcher.
- Recursive directory watcher for drop-and-process ingestion under `<DATA_DIR>/pdfs`.
- Unified FastAPI server providing REST endpoints, MCP transport, and static frontend assets.
- React + Chakra UI dashboard for queue monitoring and semantic search.

## Architecture

```
src/
  backend/
    api.py           # REST + MCP endpoints and job manager
    processor.py     # Queue, workers, parsing + embedding pipeline
    config.py        # Environment-driven settings
    storage/         # SQLite MarkdownRepository + LanceDB VectorStore
    parsers/         # PyMuPDF and Docling adapters
    embeddings/      # EmbeddingManager (local / OpenAI)
  frontend/
    src/             # React + Chakra UI SPA
    package.json
```

## Quick start

1. **Install prerequisites** – Python 3.11+, Node.js 20+, Docker (optional), NVIDIA Container Toolkit for GPU ingestion.
2. **Bootstrap backend**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3. **Build frontend**
    ```bash
    cd src/frontend
    npm install
    npm run build
    ```
4. **Run locally**
    ```bash
    uvicorn src.backend.api:app --host 0.0.0.0 --port 8000 --reload
    ```
    For hot reload UI development, run `npm run dev` in `src/frontend` (serves http://localhost:5173). Otherwise FastAPI serves the `frontend/dist` bundle directly.


## Configuration

All settings are environment-driven (see `.env.sample`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `PDF_PARSER` | `pymupdf` | Parser backend (`pymupdf` or `docling`). |
| `EMBEDDING_BACKEND` | `local` | `local` sentence-transformers or `openai` remote embeddings. |
| `SENTENCE_TRANSFORMER_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model name. |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` or `cuda`; when `cuda`, CUDA wheels install at runtime. |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` / `OPENAI_API_KEY` | – | Required when using remote embeddings. |
| `DATABASE_URL` | `sqlite:///data/markdown.db` | SQLite metadata store. |
| `VECTOR_STORE_PATH` | `data/vector_store` | LanceDB directory. |
| `DATA_DIR` | `data` | Base path for runtime artifacts. |
| `FRONTEND_DIST_PATH` | `frontend/dist` | Static assets served by FastAPI. |
| `PROCESS_WORKERS` | `4` | Worker thread count. |
| `PROCESS_QUEUE_MAXSIZE` | `100` | Max queued tasks before backpressure. |
| `WATCH_ENABLED` | `true` | Toggle directory watcher. |
| `WATCH_DIR` | `<DATA_DIR>/pdfs` | Root folder recursively scanned for PDFs. |
| `WATCH_POLL_INTERVAL` | `10` | Seconds between scans. |
| `MAX_PROCESS_ATTEMPTS` | `10` | Failures before a file is blacklisted. |

Store credentials such as `OPENAI_API_KEY` in `.env` (ignored by git) or a platform secret store.

## Processing pipeline

1. Queueing – uploads, watcher discoveries, and synchronous requests become `ProcessingTask`s in a bounded queue.
2. Worker pool – configurable daemon threads dequeue tasks, emit lifecycle callbacks, and isolate failures.
3. Metadata enrichment – filesystem stats merge with caller-provided metadata.
4. Parsing – PyMuPDF or Docling produces markdown.
5. Deduplication – SHA-256 hash lookups skip re-ingesting identical content.
6. Persistence – markdown saved to SQLite; embeddings chunked and added to LanceDB with cosine index.

REST endpoints, MCP tools, and the watcher all flow through this pipeline for consistent behavior.

## Directory watcher

- Enabled by default (`WATCH_ENABLED=true`).
- Recursively scans `WATCH_DIR` for `*.pdf` files.
- Skips paths already stored or blacklisted after repeated failures.
- Adds tasks to the shared queue so watcher processing respects backpressure and emits progress events.
- Disable by setting `WATCH_ENABLED=false` or adjust poll interval / retry thresholds via environment variables.

## REST + MCP interfaces

| Path | Method | Description |
| --- | --- | --- |
| `/api/process` | POST | Upload PDFs (multipart). Returns job descriptors. |
| `/api/process/status` | GET | Queue, in-progress, completed, and failed job summaries. |
| `/api/search` | GET | Semantic search (`?query=...&top_k=5`). |
| `/api/markdown` | GET | Fetch stored markdown by `document_id` or `title`. |
| `/.well-known/mcp/server` | GET | MCP discovery document. |
| `/mcp/tools/query_pdfs` | POST | MCP search tool (`{"query": "...", "top_k": 5}`). |
| `/mcp/tools/fetch_markdown` | POST | MCP tool to retrieve markdown (`{"document_id": 1}` or `{ "title": "..." }`). |

Claude Desktop configuration:
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
- `npm run build` – production bundle served by FastAPI.
- `npm run ci:build` – TypeScript type-check + build (matches CI).

The UI exposes a processing queue tab (live progress, retries, failures) and a search tab for semantic queries with metadata previews.

## Docker workflow

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

## Development workflow & CI parity

Run the same checks GitHub Actions enforces before pushing:

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
(cd src/frontend && npm ci && npm run ci:build)
docker build -t pdf-rag-mcp-local .
```

These steps mirror the `Test, Build and Publish` workflow (lint, pytest, frontend typecheck/build, Docker build).

## Troubleshooting

| Symptom | Suggested remedy |
| --- | --- |
| `sentence_transformers` missing | Install optional dependency or switch to `EMBEDDING_BACKEND=openai`. |
| Watcher ignores files | Confirm PDFs are under `WATCH_DIR`, not blacklisted, and the queue is not full. |
| Duplicate entries appear | Ensure source markdown differs; dedupe operates on parsed content hashes. |
| OpenAI errors | Verify `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `OPENAI_API_KEY` values. |
| Empty search results | Check logs for embedding creation and confirm LanceDB directory is writable. |

## License

MIT License © 2025 The Project Contributors
