import logging
import os
from typing import Any

from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX   = os.getenv("PINECONE_INDEX", "openclaw-kb")
PINECONE_CLOUD   = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION  = os.getenv("PINECONE_REGION", "us-east-1")
VECTOR_DIMENSION = 1536  # text-embedding-3-small

_pc: Pinecone | None = None
_index = None


async def init_pinecone() -> None:
    """Create index if it doesn't exist, then connect."""
    global _pc, _index
    _pc = Pinecone(api_key=PINECONE_API_KEY)
    existing = {idx.name for idx in _pc.list_indexes()}
    if PINECONE_INDEX not in existing:
        logger.info("Creating Pinecone index '%s'…", PINECONE_INDEX)
        _pc.create_index(
            name=PINECONE_INDEX,
            dimension=VECTOR_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
    _index = _pc.Index(PINECONE_INDEX)
    logger.info("Pinecone index '%s' connected.", PINECONE_INDEX)


def get_index():
    if _index is None:
        raise RuntimeError("Pinecone not initialized. Did init_pinecone() run?")
    return _index


async def upsert_chunks(
    doc_id: str,
    title: str,
    chunks: list[str],
    embeddings: list[list[float]],
    tags: list[str],
    namespace: str,
    created_at: str,
) -> None:
    """Upsert all chunks for a document into the index."""
    index = get_index()
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vectors.append({
            "id": f"{doc_id}#chunk#{i}",
            "values": embedding,
            "metadata": {
                "doc_id": doc_id,
                "title": title,
                "chunk": chunk,
                "chunk_index": i,
                "tags": tags,
                "created_at": created_at,
                "namespace": namespace,
            },
        })
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i : i + 100], namespace=namespace)


async def query_vectors(
    embedding: list[float],
    namespace: str,
    top_k: int = 5,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Query the index and return matches with metadata."""
    index = get_index()
    filter_dict = {"tags": {"$in": tags}} if tags else None
    result = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True,
        filter=filter_dict,
    )
    matches = getattr(result, "matches", None) or result.get("matches", [])
    out = []
    for m in matches:
        meta = getattr(m, "metadata", None) or (m.get("metadata", {}) if isinstance(m, dict) else {})
        score = getattr(m, "score", None) or (m.get("score", 0.0) if isinstance(m, dict) else 0.0)
        out.append({"metadata": meta, "score": score})
    return out


def _collect_ids(index, namespace: str) -> list[str]:
    """Collect all vector IDs from paginated list(), compatible with v3-v6."""
    ids: list[str] = []
    for page in index.list(namespace=namespace, limit=100):
        if isinstance(page, str):
            ids.append(page)
        elif isinstance(page, list):
            ids.extend(page)
        elif hasattr(page, "vectors"):
            ids.extend(v.id if hasattr(v, "id") else v for v in page.vectors)
        else:
            ids.extend(page)
    return ids


async def list_documents(namespace: str) -> list[dict[str, Any]]:
    """List unique documents in a namespace by aggregating metadata."""
    index = get_index()
    ids = _collect_ids(index, namespace)
    if not ids:
        return []

    seen_docs: dict[str, dict] = {}
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        fetch_result = index.fetch(ids=batch, namespace=namespace)
        vectors = getattr(fetch_result, "vectors", None) or fetch_result.get("vectors", {})
        for vec_id, vec_data in vectors.items():
            meta = getattr(vec_data, "metadata", None) or (vec_data.get("metadata", {}) if isinstance(vec_data, dict) else {})
            doc_id = meta.get("doc_id", "") if isinstance(meta, dict) else getattr(meta, "doc_id", "")
            if not doc_id:
                continue
            if doc_id not in seen_docs:
                seen_docs[doc_id] = {
                    "doc_id": doc_id,
                    "title": meta.get("title", "") if isinstance(meta, dict) else getattr(meta, "title", ""),
                    "tags": meta.get("tags", []) if isinstance(meta, dict) else getattr(meta, "tags", []),
                    "chunk_count": 0,
                    "namespace": namespace,
                    "created_at": meta.get("created_at", "") if isinstance(meta, dict) else getattr(meta, "created_at", ""),
                }
            seen_docs[doc_id]["chunk_count"] += 1

    return list(seen_docs.values())


async def delete_document(doc_id: str, namespace: str) -> bool:
    """Delete all vectors for a document using prefix deletion."""
    index = get_index()
    ids_to_delete = [
        vid for vid in _collect_ids(index, namespace)
        if vid.startswith(f"{doc_id}#chunk#")
    ]
    if ids_to_delete:
        for i in range(0, len(ids_to_delete), 100):
            index.delete(ids=ids_to_delete[i : i + 100], namespace=namespace)
        return True
    return False


async def health_check() -> str:
    """Return 'connected' or an error message."""
    try:
        get_index()
        return "connected"
    except Exception as e:
        return f"error: {e}"
