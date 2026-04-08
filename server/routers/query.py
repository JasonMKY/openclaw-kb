from fastapi import APIRouter, HTTPException

from server.models.schemas import (
    AskRequest,
    AskResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceDoc,
)
from server.services.embeddings import embed_query
from server.services.rag import build_context, generate_answer
from server.services.vectorstore import query_vectors

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """Semantic vector search — returns top-K scored chunks."""
    try:
        embedding = await embed_query(req.query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    try:
        matches = await query_vectors(
            embedding=embedding,
            namespace=req.namespace,
            top_k=req.top_k,
            tags=req.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vector query failed: {e}")

    results = []
    for match in matches:
        meta = match.get("metadata", {})
        results.append(
            SearchResult(
                doc_id=meta.get("doc_id", ""),
                title=meta.get("title", ""),
                chunk=meta.get("chunk", ""),
                score=match.get("score", 0.0),
                tags=meta.get("tags", []),
                namespace=meta.get("namespace", req.namespace),
            )
        )

    return SearchResponse(results=results, query=req.query, namespace=req.namespace)


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """RAG Q&A — retrieves context and generates a grounded answer."""
    try:
        embedding = await embed_query(req.question)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    try:
        matches = await query_vectors(
            embedding=embedding,
            namespace=req.namespace,
            top_k=req.top_k,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Vector query failed: {e}")

    if not matches:
        return AskResponse(
            answer="I couldn't find any relevant information in the knowledge base.",
            sources=[],
            question=req.question,
            namespace=req.namespace,
        )

    context, sources = build_context(matches)

    try:
        answer = await generate_answer(req.question, context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Answer generation failed: {e}")

    return AskResponse(
        answer=answer,
        sources=[SourceDoc(**s) for s in sources],
        question=req.question,
        namespace=req.namespace,
    )
