import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from server.models.schemas import IngestRequest, IngestResponse
from server.services.embeddings import chunk_text, embed_texts
from server.services.ingestion import parse_content
from server.services.vectorstore import upsert_chunks

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(req: IngestRequest):
    """
    Parse, chunk, embed, and store a document.

    Content types:
    - text       — plain text
    - markdown   — markdown (stripped before chunking)
    - pdf_base64 — base64-encoded PDF
    - url        — fetched and parsed web page
    """
    try:
        text, detected_title = await parse_content(req.content, req.type)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse content: {e}")

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the content.")

    title = req.title or detected_title or f"Document {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
    doc_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=422, detail="Text produced no chunks after processing.")

    try:
        embeddings = await embed_texts(chunks)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    try:
        await upsert_chunks(
            doc_id=doc_id,
            title=title,
            chunks=chunks,
            embeddings=embeddings,
            tags=req.tags,
            namespace=req.namespace,
            created_at=created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vector store upsert failed: {e}")

    return IngestResponse(
        doc_id=doc_id,
        title=title,
        chunk_count=len(chunks),
        namespace=req.namespace,
    )
