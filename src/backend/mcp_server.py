from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import Settings
from .processor import PDFProcessor

LOGGER = logging.getLogger(__name__)


class MCPTool(BaseModel):
    """Metadata describing a tool exposed via the MCP HTTP transport."""

    name: str
    description: str
    input_schema: Dict[str, object]


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query to search the PDF corpus")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of matches to return")


class QueryResponse(BaseModel):
    matches: List[Dict[str, object]]


class FetchRequest(BaseModel):
    title: Optional[str] = Field(None, description="Title of the PDF to fetch")
    document_id: Optional[int] = Field(None, description="Document identifier returned by query")


class FetchResponse(BaseModel):
    found: bool
    markdown: Optional[str]


class MCPServerInfo(BaseModel):
    name: str
    description: str
    tools: List[MCPTool]


def _build_tools() -> List[MCPTool]:
    return [
        MCPTool(
            name="query_pdfs",
            description="Return the most relevant PDF snippets for a supplied query.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["query"],
            },
        ),
        MCPTool(
            name="fetch_markdown",
            description="Fetch stored markdown for a PDF by title or identifier.",
            input_schema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "integer"},
                    "title": {"type": "string"},
                },
                "oneOf": [
                    {"required": ["document_id"]},
                    {"required": ["title"]},
                ],
            },
        ),
    ]


def create_mcp_router(settings: Optional[Settings] = None, processor: Optional[PDFProcessor] = None) -> APIRouter:
    """Return an API router exposing MCP endpoints."""

    config = settings or Settings()
    proc = processor or PDFProcessor(config)
    tools = _build_tools()

    router = APIRouter()

    @router.get("/.well-known/mcp/server", response_model=MCPServerInfo, include_in_schema=False)
    def server_manifest() -> MCPServerInfo:
        return MCPServerInfo(name="pdf-rag-mcp", description="HTTP MCP transport for PDF RAG", tools=tools)

    tool_router = APIRouter(prefix="/mcp", tags=["mcp"])

    @tool_router.post("/tools/query_pdfs", response_model=QueryResponse)
    def query_pdfs(request: QueryRequest) -> QueryResponse:
        LOGGER.info("MCP HTTP query: %s", request.query)
        matches = proc.search(request.query, top_k=request.top_k)
        return QueryResponse(matches=matches)

    @tool_router.post("/tools/fetch_markdown", response_model=FetchResponse)
    def fetch_markdown(request: FetchRequest) -> FetchResponse:
        if request.document_id is None and not request.title:
            raise HTTPException(status_code=400, detail="Provide document_id or title")

        markdown: Optional[str] = None
        if request.document_id is not None:
            markdown = proc.fetch_markdown_by_id(request.document_id)
        elif request.title:
            markdown = proc.fetch_markdown_by_title(request.title)

        if markdown is None:
            LOGGER.warning("Markdown not found for title=%s, document_id=%s", request.title, request.document_id)
            return FetchResponse(found=False, markdown=None)
        return FetchResponse(found=True, markdown=markdown)

    router.include_router(tool_router)
    return router


def create_http_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create a standalone FastAPI app serving only the MCP HTTP transport."""

    config = settings or Settings()
    processor = PDFProcessor(config)
    app = FastAPI(title="PDF RAG MCP", version="1.0.0")
    app.include_router(create_mcp_router(settings=config, processor=processor))
    LOGGER.info("Starting MCP HTTP server with parser backend=%s", config.parser_backend)
    return app


__all__ = ["create_http_app", "create_mcp_router"]
