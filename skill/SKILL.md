---
name: knowledge-base
emoji: 🧠
description: Semantic knowledge base with vector search and RAG. Ingest text, PDFs, Markdown, or URLs — then search by meaning or ask questions and get grounded AI answers with citations.
version: 1.0.0
author: openclaw
requires:
  env:
    - KB_API_URL
primaryEnv: KB_API_URL
---

# Knowledge Base Skill

## Overview

This skill gives your OpenClaw agent a persistent, searchable memory. You can ingest documents, search by semantic meaning, and ask questions to get AI-generated answers grounded in your knowledge base.

The skill talks to a self-hosted FastAPI server backed by Pinecone (vector store) and OpenAI (embeddings + RAG).

---

## Setup

1. Deploy the server (`docker-compose up` from the project root)
2. Set `KB_API_URL` in your `openclaw.json` env (e.g. `http://localhost:8000`)
3. Start a new OpenClaw session — the agent can now use all endpoints below

---

## Agent Instructions

When a user asks you to save, remember, or store information — use **POST /ingest**.
Before answering any question that might be in the knowledge base — try **POST /ask** first.
If the user asks to search or find something — use **POST /search**.
To list what's stored — use **GET /documents**.

---

## Endpoints

### POST /ingest
Save a document to the knowledge base.

**When to use:** User says "remember this", "save this", "add this to my KB", or pastes content to store.

**Request:**
```json
{
  "content": "string — the raw content",
  "type": "text | markdown | pdf_base64 | url",
  "title": "optional title",
  "tags": ["optional", "tags"],
  "namespace": "default"
}
```

**Response:**
```json
{
  "doc_id": "uuid",
  "title": "detected or provided title",
  "chunk_count": 12,
  "namespace": "default"
}
```

**Examples:**
- User: "Remember that our refund window is 30 days"
  → POST /ingest with type "text", namespace "default"
- User: "Save this URL to my work KB: https://docs.example.com"
  → POST /ingest with type "url", namespace "work"

---

### POST /search
Semantic similarity search — find chunks by meaning, not keywords.

**When to use:** User asks to "find", "search for", or "look up" something in the KB.

**Request:**
```json
{
  "query": "refund policy",
  "top_k": 5,
  "namespace": "default",
  "tags": ["optional", "filter"]
}
```

**Response:** Array of scored results with `doc_id`, `title`, `chunk`, `score`, `tags`.

---

### POST /ask
RAG Q&A — retrieve context and generate a grounded answer.

**When to use:** User asks ANY question that might be answerable from the knowledge base. Always try /ask before giving a general answer.

**Request:**
```json
{
  "question": "What is our P1 response time?",
  "namespace": "default",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "Based on your SLA document, P1 incidents require a 4-hour response time. [1]",
  "sources": [{ "index": 1, "doc_id": "...", "title": "SLA Agreement 2026" }],
  "question": "...",
  "namespace": "default"
}
```

---

### GET /documents
List all documents in a namespace.

**When to use:** User asks "what's in my knowledge base?" or "show me my documents".

**Query params:** `?namespace=default`

---

### DELETE /documents/{doc_id}
Remove a document and all its chunks.

**When to use:** User asks to "delete", "remove", or "forget" a document.

**Query params:** `?namespace=default`

---

### GET /health
Check if the service is running.

---

## Namespaces

Use namespaces to separate knowledge domains:
- `default` — general knowledge
- `work` — work-related documents
- `personal` — personal notes
- `project-x` — project-specific knowledge

If the user doesn't specify a namespace, use `default`.

---

## Agent Tips

- Always call `/ask` before answering factual questions — the KB may have the answer.
- When ingesting a URL, let the user know how many chunks were saved.
- When answering via RAG, always include the source citations in your response.
- If `/ask` returns "I couldn't find that in the knowledge base", fall back to your own knowledge and tell the user.
- Suggest relevant namespaces based on context (e.g., work emails → "work" namespace).
