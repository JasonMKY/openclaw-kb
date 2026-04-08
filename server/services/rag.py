import os
from typing import Any, Dict, List

from openai import AsyncOpenAI

from server.services.embeddings import get_openai_client

RAG_MODEL      = os.getenv("RAG_MODEL", "gpt-4o-mini")
RAG_MAX_TOKENS = int(os.getenv("RAG_MAX_TOKENS", "1024"))

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using ONLY the provided context.
If the answer is not in the context, say "I couldn't find that in the knowledge base."
Always cite your sources using [N] notation where N is the source number."""


def build_context(matches: List[Dict[str, Any]]) -> tuple[str, list]:
    """Build a numbered context string and source list from Pinecone matches."""
    context_parts = []
    sources = []
    for i, match in enumerate(matches, 1):
        meta = match.get("metadata", {})
        title = meta.get("title", "Unknown")
        chunk = meta.get("chunk", "")
        doc_id = meta.get("doc_id", "")
        context_parts.append(f"[{i}] SOURCE: {title}\n{chunk}")
        sources.append({"index": i, "doc_id": doc_id, "title": title})
    context = "\n\n---\n\n".join(context_parts)
    return context, sources


async def generate_answer(question: str, context: str) -> str:
    """Generate a grounded answer using the RAG context."""
    client: AsyncOpenAI = get_openai_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        },
    ]
    response = await client.chat.completions.create(
        model=RAG_MODEL,
        messages=messages,
        max_tokens=RAG_MAX_TOKENS,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()
