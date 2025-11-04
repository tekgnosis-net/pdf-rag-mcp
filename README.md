# PDF RAG MCP Server

An opinionated reference implementation for processing PDF documents into a Retrieval Augmented Generation (RAG) knowledge base exposed via [Model Context Protocol](https://modelcontextprotocol.io/) (MCP). The stack combines a FastAPI backend with configurable parsing and embedding pipelines, a LanceDB vector store, a lightweight SQLite document catalog, and a Chakra UI powered frontend for monitoring ingestion and running semantic search.

> **Key capabilities**
>
> - **Parser backends:** choose between PyMuPDF and Docling at runtime.
> - **Embeddings:** run local `sentence-transformers` on CPU/CUDA or send requests to a remote OpenAI-compatible endpoint.
> - **Storage:** persist markdown snapshots in SQLite and vectors in LanceDB.
> - **MCP interface:** expose `query_pdfs` and `fetch_markdown` tools via FastMCP.
> - **Frontend:** monitor upload queues, track progress, and explore search results in a browser.

---

## Project structure

```
src/
  backend/
    api.py               # FastAPI application with upload, status, search, markdown endpoints
    mcp_server.py        # FastMCP server exposing query & fetch tools
    processor.py         # Orchestrates parsing, embeddings, and persistence
    parsers/             # PyMuPDF and Docling parser adapters
    embeddings/          # Embedding manager (local/OpenAI)
    storage/             # SQLite markdown repo + LanceDB vector store
    logging_config.py    # Global logging helper
    config.py            # Environment-driven settings
  frontend/
    src/                 # React + Chakra UI app (queue dashboard + search view)
    package.json         # Vite configuration & deps
```

---

## Getting started

### 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional, for containerized deployment)
- System packages required by PyMuPDF / Docling (`libgl1`, `libglib2.0-0`, etc.)

### 2. Install backend dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd src/frontend
npm install
npm run build  # produces dist/ consumed by the backend
```

### 4. Configure environment

Create a `.env` (or set variables in your shell) to override defaults:

```bash
# Parser backend: pymupdf | docling
export PDF_PARSER=pymupdf

# Embedding backend: local | openai
export EMBEDDING_BACKEND=local
export SENTENCE_TRANSFORMER_MODEL=sentence-transformers/all-MiniLM-L6-v2
export EMBEDDING_DEVICE=cpu
export EMBEDDING_DIMENSION=384

# Remote embeddings (if EMBEDDING_BACKEND=openai)
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=text-embedding-3-large
# Override EMBEDDING_DIMENSION to match the chosen model (e.g. 3072 for text-embedding-3-large)

# Persistence
export DATABASE_URL=sqlite:///data/markdown.db
export VECTOR_STORE_PATH=data/vector_store
export DATA_DIR=data
export FRONTEND_DIST_PATH=frontend/dist
```

### 5. Run the development server

```bash
uvicorn src.backend.api:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://localhost:5173> while running `npm run dev` in `src/frontend` if you prefer hot reloading during UI development. Otherwise, the FastAPI app will serve the built frontend from `frontend/dist`.

---

## MCP integration

The FastAPI application hosts the MCP HTTP transport alongside the REST API (same process, same port `8000`).

Key endpoints:

- `GET /.well-known/mcp/server` – discover available tools and schemas.
- `POST /mcp/tools/query_pdfs` – invoke the `query_pdfs` tool (`{"query": "...", "top_k": 5}`).
- `POST /mcp/tools/fetch_markdown` – invoke the `fetch_markdown` tool (`{"document_id": 1}` or `{ "title": "..." }`).

#### Example tool payloads

```json
// POST /mcp/tools/query_pdfs
{
  "query": "Summarize the safety requirements in the uploaded manuals",
  "top_k": 5
}
```

```json
// POST /mcp/tools/fetch_markdown
{
  "document_id": 12
}
```

#### Claude Desktop configuration snippet

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

#### Cursor `cursor.json` snippet

```json
{
  "mcpServers": [
    {
      "name": "pdf-rag",
      "type": "http",
  "url": "http://localhost:8000",
      "tools": ["query_pdfs", "fetch_markdown"]
    }
  ]
}
```

---

## Docker workflow

Build and run the containerized stack:

```bash
# Use the published GHCR image (recommended)
docker run --rm -p 8000:8000 \
  -e PDF_PARSER=docling \
  ghcr.io/tekgnosis-net/pdf-rag-mcp:latest

# Or build and run locally
docker build -t pdf-rag-mcp .
docker run --rm -p 8000:8000 -e PDF_PARSER=docling pdf-rag-mcp

# Docker Compose (uses GHCR image by default in `docker-compose.yml`)
docker compose up --build
```

### GPU runtime toggle

The published image ships with the lighter CPU build of PyTorch. If you set `EMBEDDING_DEVICE=cuda`, the container entrypoint upgrades PyTorch (and any packages in `TORCH_CUDA_PACKAGES`) from the CUDA wheel index (`TORCH_CUDA_INDEX_URL`, default `https://download.pytorch.org/whl/cu124`) before launching the API. This keeps the base image slim while allowing GPU acceleration on demand.

To use GPUs with Docker Compose, install the NVIDIA Container Toolkit, uncomment the GPU block in `docker-compose.yml`, and set `EMBEDDING_DEVICE=cuda` (plus optional `GPU_COUNT`) in your `.env`. Alternatively, launch manually with:

```bash
docker run --rm -p 8000:8000 --gpus all -e EMBEDDING_DEVICE=cuda pdf-rag-mcp
```

Mount `data/` as a volume if you want persistent storage across container restarts.

---

## Extending the system

- **Additional parsers:** implement `BasePDFParser` and register it in `PDFProcessor` for alternative pipelines.
- **Custom chunking strategies:** replace `EmbeddingManager.chunk_markdown` with domain-specific logic (e.g., semantic sentences or headings).
- **LLM integrations:** augment the backend with summarization or QA endpoints leveraging the stored markdown and embeddings.

---

## Troubleshooting

| Symptom | Potential fix |
| --- | --- |
| PyMuPDF import errors | Ensure `pymupdf` compiled dependencies are installed (see Dockerfile for reference). |
# PDF RAG MCP Server

An opinionated reference implementation that ingests PDFs into a Retrieval Augmented Generation (RAG) knowledge base and exposes it through [Model Context Protocol](https://modelcontextprotocol.io/) (MCP). The backend is powered by FastAPI, LanceDB, and SQLite; the frontend is a Vite + React dashboard for monitoring ingestion and running semantic search.

## Highlights

- Switchable PDF parsing backends (PyMuPDF or Docling).
- Local or remote embedding pipelines with CPU/GPU support.
- LanceDB vector store and SQLite document catalog.
- Built-in directory watcher for drop-and-process workflows.
- MCP HTTP transport and REST API in the same FastAPI app.
- React/Chakra UI frontend for queue monitoring and search.

## Table of contents

1. [Quick start](#1-quick-start)
2. [Configuration](#2-configuration)
3. [Running locally](#3-running-locally)
4. [MCP integration](#4-mcp-integration)
5. [Docker workflow](#5-docker-workflow)
6. [Directory watcher](#6-directory-watcher)
7. [Extending the system](#7-extending-the-system)
8. [Troubleshooting](#8-troubleshooting)
9. [License](#9-license)

---

## 1. Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (optional)
- System libraries required by PyMuPDF / Docling (`libgl1`, `libglib2.0-0`, ...)

### Backend setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend build

```bash
cd src/frontend
npm install
npm run build  # produces frontend/dist used by the backend
```

### Project layout

```
src/
  backend/
    api.py           # FastAPI app with REST + MCP routes
    processor.py     # Orchestrates parsing, embeddings, persistence
    mcp_server.py    # Reusable MCP server helpers
    parsers/         # PyMuPDF and Docling adapters
    embeddings/      # Embedding manager (local/OpenAI)
    storage/         # SQLite markdown repo + LanceDB vector store
  frontend/
    src/             # React + Chakra UI SPA
    package.json
```

---

## 2. Configuration

All settings flow through environment variables (see `.env.sample`). Configure them via shell exports, `.env`, or `docker-compose.yml`.

### Core variables

| Variable | Default | Description |
| --- | --- | --- |
| `PDF_PARSER` | `pymupdf` | PDF parser (`pymupdf` or `docling`). |
| `EMBEDDING_BACKEND` | `local` | `local` for sentence-transformers, `openai` for API-based embeddings. |
| `SENTENCE_TRANSFORMER_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model. |
| `EMBEDDING_DEVICE` | `cpu` | Target device (`cpu` or `cuda`). When `cuda`, CUDA wheels are installed at runtime. |
| `EMBEDDING_DIMENSION` | `0` | Override embedding size; set when the chosen model differs from the default. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Base URL for OpenAI-compatible embedding APIs. |
| `OPENAI_MODEL` | `text-embedding-3-large` | Remote embedding model name. |
| `OPENAI_API_KEY` | – | API key for remote embeddings (keep secret). |
| `TORCH_CUDA_INDEX_URL` | `https://download.pytorch.org/whl/cu124` | CUDA wheel index for runtime upgrades. |
| `TORCH_CUDA_PACKAGES` | `torch torchvision torchaudio` | Packages installed from the CUDA index when enabling GPU. |
| `DATABASE_URL` | `sqlite:///data/markdown.db` | SQLite database storing parsed markdown. |
| `VECTOR_STORE_PATH` | `data/vector_store` | LanceDB directory for embeddings. |
| `DATA_DIR` | `data` | Base directory for runtime data. The watcher watches `<DATA_DIR>/pdfs` by default. |
| `FRONTEND_DIST_PATH` | `frontend/dist` | Location of built frontend assets served by FastAPI. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. |

### Directory watcher variables

| Variable | Default | Description |
| --- | --- | --- |
| `WATCH_ENABLED` | `true` | Start the polling watcher when the API boots. |
| `WATCH_DIR` | `${DATA_DIR}/pdfs` | Folder monitored for incoming PDFs. |
| `WATCH_POLL_INTERVAL` | `10` | Polling interval in seconds. |
| `MAX_PROCESS_ATTEMPTS` | `10` | Maximum failed attempts before a file is blacklisted. |

> **Tip:** keep `OPENAI_API_KEY` out of source control. Use secrets in CI/CD and `.env` locally.

---

## 3. Running locally

### Backend API

```bash
uvicorn src.backend.api:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend with hot reload

```bash
cd src/frontend
npm run dev
```

Visit <http://localhost:5173> for the Vite dev server. Without `npm run dev`, the FastAPI app serves the built assets from `frontend/dist`.

---

## 4. MCP integration

The REST and MCP transports share the same FastAPI instance (`:8000`).

**Endpoints**

- `GET /.well-known/mcp/server` — discovery metadata.
- `POST /mcp/tools/query_pdfs` — semantic search (`{"query": "...", "top_k": 5}`).
- `POST /mcp/tools/fetch_markdown` — fetch markdown by ID/title.

**Example payloads**

```json
// POST /mcp/tools/query_pdfs
{
  "query": "Summarize safety requirements",
  "top_k": 5
}
```

```json
// POST /mcp/tools/fetch_markdown
{
  "document_id": 12
}
```

**Client snippets**

Claude Desktop (`claude_desktop_config.json`):

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

Cursor (`cursor.json`):

```json
{
  "mcpServers": [
    {
      "name": "pdf-rag",
      "type": "http",
      "url": "http://localhost:8000",
      "tools": ["query_pdfs", "fetch_markdown"]
    }
  ]
}
```

---

## 5. Docker workflow

```bash
# Recommended: use the published GHCR image
docker run --rm -p 8000:8000 \
  -e PDF_PARSER=docling \
  ghcr.io/tekgnosis-net/pdf-rag-mcp:latest

# Build locally if needed
docker build -t pdf-rag-mcp .
docker run --rm -p 8000:8000 pdf-rag-mcp

# Compose (uses GHCR image by default)
docker compose up --build
```

### GPU toggle

Set `EMBEDDING_DEVICE=cuda` to trigger a runtime upgrade of PyTorch (and packages listed in `TORCH_CUDA_PACKAGES`) from `TORCH_CUDA_INDEX_URL`. With the NVIDIA Container Toolkit installed you can enable GPUs in Compose by uncommenting the provided stanza or with:

```bash
docker run --rm --gpus all -p 8000:8000 -e EMBEDDING_DEVICE=cuda ghcr.io/tekgnosis-net/pdf-rag-mcp:latest
```

### Persistent data & watcher mapping

```yaml
services:
  app:
    image: ghcr.io/tekgnosis-net/pdf-rag-mcp:latest
    volumes:
      - ./data:/app/data            # persists DB + vectors
      - ./pdfs:/app/data/pdfs       # exposes the default WATCH_DIR
    env_file: .env
```

### Docker image size

```bash
docker image inspect ghcr.io/tekgnosis-net/pdf-rag-mcp:latest --format='{{.Size}}'
# or
docker images | grep tekgnosis-net/pdf-rag-mcp
```

---

## 6. Directory watcher

- Enabled by default (`WATCH_ENABLED=true`).
- Polls `WATCH_DIR` (default `<DATA_DIR>/pdfs`) every `WATCH_POLL_INTERVAL` seconds.
- Each file is processed once; existing entries in the Markdown repository are skipped.
- Failures are tracked in SQLite. After `MAX_PROCESS_ATTEMPTS` the file is blacklisted.
- Successful ingests clear the failure counter.

Customize the watcher via environment variables or Compose overrides:

```yaml
services:
  app:
    environment:
      - WATCH_DIR=/app/data/incoming
      - WATCH_POLL_INTERVAL=15
      - MAX_PROCESS_ATTEMPTS=5
```

When `DATA_DIR` is moved (e.g. `DATA_DIR=/var/lib/pdf-rag`), the watcher automatically watches `/var/lib/pdf-rag/pdfs` unless `WATCH_DIR` is explicitly set.

---

## 7. Extending the system

- **Custom parsers:** implement `BasePDFParser` and register it with `PDFProcessor`.
- **Chunking strategies:** replace `EmbeddingManager.chunk_markdown` for domain-specific segments.
- **LLM augmentations:** add REST/MCP endpoints that use stored markdown + embeddings.

---

## 8. Troubleshooting

| Symptom | Suggested fix |
| --- | --- |
| PyMuPDF import errors | Confirm required system libraries are installed (see `Dockerfile`). |
| Docling OCR issues | Ensure models download successfully and disk space is available. |
| Empty search results | Check logs for embedding creation and ensure LanceDB contains vectors (`data/vector_store`). |
| OpenAI/remote errors | Verify `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. |

---

## 9. License

MIT License © 2025 The Project Contributors
