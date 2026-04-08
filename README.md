# OpenClaw Knowledge Base

A semantic knowledge base service with vector search and RAG, built as an OpenClaw skill. Includes a community sharing marketplace (KBHub).

## Project Structure

```
openclaw-kb/
├── frontend/
│   └── index.html          # Combined homepage + KBHub marketplace (single file)
├── server/
│   ├── main.py             # FastAPI app entry point
│   ├── requirements.txt    # Python dependencies
│   ├── models/
│   │   └── schemas.py      # Pydantic request/response models
│   ├── routers/
│   │   ├── ingest.py       # POST /ingest
│   │   ├── query.py        # POST /search, POST /ask
│   │   └── documents.py    # GET /documents, DELETE /documents/{id}, GET /health
│   └── services/
│       ├── embeddings.py   # OpenAI embeddings + token-aware chunking
│       ├── vectorstore.py  # Pinecone upsert / query / delete
│       ├── ingestion.py    # Text / Markdown / PDF / URL parsing
│       └── rag.py          # Context building + GPT answer generation
├── skill/
│   └── SKILL.md            # OpenClaw AgentSkills spec
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Configure environment
```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and PINECONE_API_KEY
```

### 2. Start the API server
```bash
docker-compose up
# Server runs at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

### 3. Install the OpenClaw skill
```bash
cp -r skill/ ~/.openclaw/skills/knowledge-base/
```

### 4. Configure your agent
Add to your `openclaw.json`:
```json
{
  "skills": {
    "entries": {
      "knowledge-base": {
        "env": { "KB_API_URL": "http://localhost:8000" }
      }
    }
  }
}
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Ingest a document (text, markdown, PDF, URL) |
| POST | `/search` | Semantic vector search |
| POST | `/ask` | RAG question answering with citations |
| GET | `/documents` | List documents in a namespace |
| DELETE | `/documents/{id}` | Delete a document and all its chunks |
| GET | `/health` | Service health check |

---

## Frontend

Open `frontend/index.html` in any browser — no build step required.

- **Home page** — product overview, interactive dashboard preview, API reference, install steps
- **KBHub page** — community marketplace to publish, discover, and clone knowledge bases
- Switch between pages using the nav bar

---

## Environment Variables

See `.env.example` for all options. Required:

```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pcsk_...
```

---

## Tech Stack

- **API**: FastAPI + Uvicorn
- **Embeddings**: OpenAI `text-embedding-3-small` (1536-dim)
- **Vector Store**: Pinecone serverless
- **RAG**: OpenAI `gpt-4o-mini`
- **Parsing**: BeautifulSoup4 (URLs), pypdf (PDFs), tiktoken (chunking)
- **Frontend**: Vanilla HTML/CSS/JS — no framework, no build step

---

## Development (without Docker)

```bash
cd server
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## Cursor Continuation Notes

### What's built
- ✅ Full FastAPI backend with all endpoints
- ✅ OpenAI embeddings + token-aware chunking
- ✅ Pinecone vector store integration
- ✅ URL / PDF / Markdown / text ingestion
- ✅ RAG answer generation with citations
- ✅ Frontend: homepage + KBHub marketplace UI

### What to build next (suggested)
- [ ] Authentication (API keys or JWT)
- [ ] KBHub backend — real publish/clone/search API
- [ ] WebSocket streaming for `/ask` responses
- [ ] Agent connector (WhatsApp via Twilio / Telegram Bot API)
- [ ] Dashboard: wire up frontend to live API
- [ ] Auto-sync sources (cron job to re-ingest URLs)
- [ ] Multi-user support with per-user namespaces
- [ ] Metrics / analytics endpoint
