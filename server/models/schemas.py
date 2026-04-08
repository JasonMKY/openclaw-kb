from typing import Optional
from pydantic import BaseModel


# ── Ingest ──────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    content: str
    type: str = "text"          # text | markdown | pdf_base64 | url
    title: Optional[str] = None
    tags: list[str] = []
    namespace: str = "default"


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    chunk_count: int
    namespace: str


# ── Search ───────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    namespace: str = "default"
    tags: Optional[list[str]] = None   # filter by tags ($in)


class SearchResult(BaseModel):
    doc_id: str
    title: str
    chunk: str
    score: float
    tags: list[str]
    namespace: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    namespace: str


# ── Ask (RAG) ────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str
    namespace: str = "default"
    top_k: int = 5


class SourceDoc(BaseModel):
    index: int
    doc_id: str
    title: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceDoc]
    question: str
    namespace: str


# ── Documents ────────────────────────────────────────────────────────────────

class DocumentMeta(BaseModel):
    doc_id: str
    title: str
    tags: list[str]
    chunk_count: int
    namespace: str
    created_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentMeta]
    namespace: str
    total: int


class DeleteResponse(BaseModel):
    doc_id: str
    deleted: bool
    namespace: str


# ── Bundles (Export / Import) ─────────────────────────────────────────────────

class ExportBundleRequest(BaseModel):
    namespace: str = "default"
    slug: str
    name: str


class ExportBundleResponse(BaseModel):
    meta: dict
    documents: list[dict]


class ImportBundleRequest(BaseModel):
    meta: dict
    documents: list[dict]


class ImportBundleResponse(BaseModel):
    imported: bool
    doc_count: int
    chunk_count: int
    namespace: str


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    pinecone: str
    index: str
    embedding_model: str
