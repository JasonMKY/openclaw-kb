import os

from fastapi import APIRouter, HTTPException

from server.models.schemas import (
    DeleteResponse,
    DocumentListResponse,
    HealthResponse,
)
from server.services.vectorstore import delete_document, health_check, list_documents

router = APIRouter()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
PINECONE_INDEX  = os.getenv("PINECONE_INDEX", "openclaw-kb")


@router.get("/documents", response_model=DocumentListResponse)
async def list_docs(namespace: str = "default"):
    """List all documents in a namespace with metadata."""
    try:
        docs = await list_documents(namespace)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to list documents: {e}")
    return DocumentListResponse(documents=docs, namespace=namespace, total=len(docs))


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_doc(doc_id: str, namespace: str = "default"):
    """Delete all vector chunks for a document."""
    try:
        deleted = await delete_document(doc_id, namespace)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to delete document: {e}")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in namespace '{namespace}'.")
    return DeleteResponse(doc_id=doc_id, deleted=True, namespace=namespace)


@router.get("/health", response_model=HealthResponse)
async def health():
    """Check Pinecone connectivity and service status."""
    status = await health_check()
    return HealthResponse(
        status="ok" if status == "connected" else "degraded",
        pinecone=status,
        index=PINECONE_INDEX,
        embedding_model=EMBEDDING_MODEL,
    )
