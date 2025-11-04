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
docker build -t pdf-rag-mcp .
docker run --rm -p 8000:8000 -e PDF_PARSER=docling pdf-rag-mcp
# or use docker compose for the full stack with persistent data volume
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
| Docling OCR pipeline issues | Confirm model downloads succeed and enough disk space is available. |
| Empty search results | Verify embeddings are created (check logs) and the LanceDB store contains vectors (`data/vector_store`). |
| OpenAI errors | Double-check `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and model name compatibility. |

---

## License

MIT License © 2025 The Project Contributors
