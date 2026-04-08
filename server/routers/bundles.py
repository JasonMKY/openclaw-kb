import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from server.models.schemas import (
    ExportBundleRequest,
    ExportBundleResponse,
    ImportBundleRequest,
    ImportBundleResponse,
)
from server.services.vectorstore import get_index, _collect_ids

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/export-bundle", response_model=ExportBundleResponse)
async def export_bundle(req: ExportBundleRequest) -> ExportBundleResponse:
    """Export all vectors for a namespace as a portable bundle with chunks + embeddings."""
    index = get_index()
    ids = _collect_ids(index, req.namespace)
    if not ids:
        raise HTTPException(status_code=404, detail=f"No vectors found in namespace '{req.namespace}'.")

    documents: dict[str, dict[str, Any]] = {}
    total_chunks = 0

    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        fetch_result = index.fetch(ids=batch, namespace=req.namespace)
        vectors = getattr(fetch_result, "vectors", None) or fetch_result.get("vectors", {})

        for vec_id, vec_data in vectors.items():
            meta = getattr(vec_data, "metadata", None) or (vec_data.get("metadata", {}) if isinstance(vec_data, dict) else {})
            values = getattr(vec_data, "values", None) or (vec_data.get("values", []) if isinstance(vec_data, dict) else [])

            doc_id = meta.get("doc_id", "") if isinstance(meta, dict) else getattr(meta, "doc_id", "")
            if not doc_id:
                continue

            if doc_id not in documents:
                documents[doc_id] = {
                    "doc_id": doc_id,
                    "title": meta.get("title", "") if isinstance(meta, dict) else getattr(meta, "title", ""),
                    "tags": meta.get("tags", []) if isinstance(meta, dict) else getattr(meta, "tags", []),
                    "created_at": meta.get("created_at", "") if isinstance(meta, dict) else getattr(meta, "created_at", ""),
                    "chunks": [],
                }

            chunk_text = meta.get("chunk", "") if isinstance(meta, dict) else getattr(meta, "chunk", "")
            chunk_index = meta.get("chunk_index", 0) if isinstance(meta, dict) else getattr(meta, "chunk_index", 0)

            documents[doc_id]["chunks"].append({
                "index": chunk_index,
                "text": chunk_text,
                "embedding": list(values),
            })
            total_chunks += 1

    for doc in documents.values():
        doc["chunks"].sort(key=lambda c: c["index"])

    return ExportBundleResponse(
        meta={
            "slug": req.slug,
            "name": req.name,
            "namespace": req.namespace,
            "doc_count": len(documents),
            "chunk_count": total_chunks,
            "embedding_model": "text-embedding-3-small",
            "embedding_dim": 1536,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        documents=list(documents.values()),
    )


@router.post("/import-bundle", response_model=ImportBundleResponse)
async def import_bundle(req: ImportBundleRequest) -> ImportBundleResponse:
    """Import a bundle of chunks + pre-computed embeddings directly into Pinecone."""
    index = get_index()
    namespace = req.meta.get("namespace", "default") if isinstance(req.meta, dict) else "default"
    total_chunks = 0

    for doc in req.documents:
        doc_id = str(uuid.uuid4())
        title = doc.get("title", "Imported Document") if isinstance(doc, dict) else "Imported Document"
        tags = doc.get("tags", []) if isinstance(doc, dict) else []
        created_at = doc.get("created_at", datetime.now(timezone.utc).isoformat()) if isinstance(doc, dict) else datetime.now(timezone.utc).isoformat()
        chunks = doc.get("chunks", []) if isinstance(doc, dict) else []

        vectors = []
        for chunk in chunks:
            chunk_index = chunk.get("index", 0)
            chunk_text = chunk.get("text", "")
            embedding = chunk.get("embedding", [])

            if not embedding or len(embedding) != 1536:
                continue

            vectors.append({
                "id": f"{doc_id}#chunk#{chunk_index}",
                "values": embedding,
                "metadata": {
                    "doc_id": doc_id,
                    "title": title,
                    "chunk": chunk_text,
                    "chunk_index": chunk_index,
                    "tags": tags,
                    "created_at": created_at,
                    "namespace": namespace,
                },
            })

        for i in range(0, len(vectors), 100):
            index.upsert(vectors=vectors[i : i + 100], namespace=namespace)

        total_chunks += len(vectors)

    return ImportBundleResponse(
        imported=True,
        doc_count=len(req.documents),
        chunk_count=total_chunks,
        namespace=namespace,
    )
