# Deploy OpenClaw KB to Vercel

This repo is a **FastAPI** app that also serves the **vanilla HTML** frontend. Vercel’s official **FastAPI** preset expects a **`main.py` at the repository root** that exposes an ASGI **`app`**. This repo uses a thin root **`main.py`** that imports **`server.main:app`** (same app you run locally with Uvicorn).

The old **`api/index.py` + `functions` + `rewrites`** setup is **not** used: Vercel often reports *“pattern doesn’t match any Serverless Functions”* for `api/**/*.py` when the FastAPI builder only registers the root **`main.py`** entry.

---

## Prerequisites

- A [Vercel](https://vercel.com) account (CLI optional: `npm i -g vercel`).
- All **environment variables** you use locally (OpenAI, Pinecone, Supabase, Stripe, etc.) copied into the Vercel project settings.

---

## One-time setup

1. **Connect the Git repo** to Vercel (Dashboard → Add New → Project → import repo).

2. **Framework preset**: Choose **FastAPI**, or rely on **`vercel.json`** (`"framework": "fastapi"`). Do **not** use Next.js or another preset that steals routing.

3. **Root directory**: repository root (where `vercel.json` and `main.py` live).

4. **Environment variables** (Vercel → Project → Settings → Environment Variables). Set at least:

   | Variable | Notes |
   |----------|--------|
   | `OPENAI_API_KEY` | Required for embeddings / RAG |
   | `PINECONE_API_KEY` | Required for vector store |
   | `PINECONE_INDEX` | Your index name (if used) |
   | `SUPABASE_URL` | KBHub |
   | `SUPABASE_ANON_KEY` | Written into `frontend/config.json` on cold start |
   | `SUPABASE_SERVICE_ROLE_KEY` | Payments / server-side Supabase |
   | `STRIPE_SECRET_KEY` | Test or live |
   | `STRIPE_WEBHOOK_SECRET` | Signing secret for `POST /stripe-webhook` |
   | **`KB_API_URL`** | **Public URL of this Vercel deployment**, e.g. `https://your-project.vercel.app` (no trailing slash). Used for Stripe return URLs and Checkout redirects. |

   Add any other vars from your local `.env` / `.env.example` that the app reads.

5. **Function duration (optional)**  
   Heavy **ingest** may exceed the default timeout. In Vercel → Project → **Settings** → **Functions**, increase **max duration** for Python / serverless if your plan allows (e.g. Pro).

6. **Stripe webhook (production)**  
   Endpoint: `https://<your-vercel-domain>/stripe-webhook`  
   Event: `checkout.session.completed`  
   Put the **signing secret** into `STRIPE_WEBHOOK_SECRET`.

7. **Deploy** — push to the connected branch or run `vercel` / `vercel --prod` from the repo root.

---

## Files used for Vercel

| File | Purpose |
|------|--------|
| **`main.py`** (repo root) | Vercel entry: `from server.main import app`. |
| **`vercel.json`** | Sets `"framework": "fastapi"`. |
| **`requirements.txt`** (root) | Full dependency list (Vercel does not reliably support `-r` includes). |
| **`runtime.txt`** | `python-3.12`. |
| **`.vercelignore`** | Skips `.venv`, `.env`, etc. from uploads. |

**Local development** (unchanged):

```bash
pip install -r server/requirements.txt
uvicorn server.main:app --reload --host 127.0.0.1 --port 8000
```

---

## Limits and trade-offs

- **Execution time**: Serverless **max duration** depends on your Vercel plan. Large PDF ingest may need a higher limit or a non-serverless host (Railway, Fly, Render, Docker).
- **Cold starts**: First request after idle can be slower while Python loads dependencies (Pinecone, OpenAI, etc.).
- **File system**: Ephemeral and read-only except `/tmp`. This app does not rely on durable local disk for core flows.

---

## After deploy

1. Open `https://<your-project>.vercel.app` — you should see the UI (`GET /`).
2. Check `GET /health`.
3. Set **`KB_API_URL`** to that same origin (or your custom domain) and redeploy if you had a placeholder.
4. For **live Stripe**, follow `docs/stripe-production.md` using your Vercel URL.

---

## Custom domain

Add the domain in Vercel → Project → Settings → Domains, then set **`KB_API_URL`** to `https://your-custom-domain.com` and update the Stripe webhook URL if needed.

---

## Troubleshooting

- **`functions` pattern errors**: Remove any custom `functions` / `api/**/*.py` config; this project uses root **`main.py`** + **`framework: "fastapi"`** only.
- **Import errors** (`No module named 'server'`): deploy root must be the repo root; **`server/`** must be in the deployment.
- **Build fails on `lxml` / native deps**: check the Vercel build log; consider a container-based host if needed.
- **`requirements.txt`**: Keep a **flat** list at the repo root (no `-r` includes). Local dev can still run `pip install -r server/requirements.txt`, which delegates to the root file.

---

## Related

- Stripe live keys and webhooks: `docs/stripe-production.md`
