import os
from typing import List

import tiktoken
from openai import AsyncOpenAI

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", "400"))
CHUNK_OVERLAP_TOKENS = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def chunk_text(text: str) -> List[str]:
    """Split text into token-aware overlapping chunks."""
    enc = tiktoken.encoding_for_model("gpt-4")
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + MAX_CHUNK_TOKENS, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        if end == len(tokens):
            break
        start += MAX_CHUNK_TOKENS - CHUNK_OVERLAP_TOKENS
    return [c.strip() for c in chunks if c.strip()]


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch embed a list of strings using OpenAI."""
    client = get_openai_client()
    BATCH_SIZE = 100
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
        )
        all_embeddings.extend([item.embedding for item in response.data])
    return all_embeddings


async def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    embeddings = await embed_texts([query])
    return embeddings[0]
