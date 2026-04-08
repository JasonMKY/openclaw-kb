# Deploy OpenClaw KB to Vercel

This repo is a **FastAPI** app that also serves the **vanilla HTML** frontend. Vercel runs it as a **single Python serverless function** with **Mangum** (ASGI adapter) and **rewrites** so all routes (`/`, `/ingest`, `/health`, …) hit that function.

---

## Prerequisites

- A [Vercel](https://vercel.com) account (CLI optional: `npm i -g vercel`).
- All **environment variables** you use locally (OpenAI, Pinecone, Supabase, Stripe, etc.) copied into the Vercel project settings.

---

## One-time setup

1. **Connect the Git repo** to Vercel (Dashboard → Add New → Project → import repo).

2. **Framework preset**: Vercel may auto-detect nothing useful — leave defaults; the important pieces are `vercel.json`, `api/index.py`, and root `requirements.txt`.

3. **Root directory**: repository root (where `vercel.json` lives).

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

5. **Stripe webhook (production)**  
   Endpoint: `https://<your-vercel-domain>/stripe-webhook`  
   Event: `checkout.session.completed`  
   Put the **signing secret** into `STRIPE_WEBHOOK_SECRET`.

6. **Deploy** — push to the connected branch or run `vercel` / `vercel --prod` from the repo root.

---

## Files added for Vercel

| File | Purpose |
|------|--------|
| `api/index.py` | Exports ASGI `app` (Mangum + `server.main:app`). |
| `vercel.json` | Rewrites all traffic to `/api/index`; optional `maxDuration` / memory. |
| `requirements.txt` | Root install: includes `server/requirements.txt` + **mangum**. |
| `runtime.txt` | `python-3.12` (Vercel Python version). |
| `.vercelignore` | Skips `.venv`, `.env`, etc. from uploads. |

Local development is unchanged: use `uvicorn server.main:app` and `pip install -r server/requirements.txt` as before.

---

## Limits and trade-offs

- **Execution time**: Serverless functions have a **maximum duration** (Hobby is short; **Pro** allows longer runs, e.g. 60s — see `vercel.json`). Heavy **ingest** / large PDFs may **time out** on Hobby. If that happens, increase the plan/limit or run the API on a long-timeout host (Railway, Fly, Render, Docker) and use Vercel only for the static frontend.
- **Cold starts**: First request after idle can be slower while Python loads dependencies (Pinecone, OpenAI, etc.).
- **File system**: Ephemeral and read-only except `/tmp`. This app does not rely on durable local disk for core flows.
- **WebSockets**: Not used by this stack; no change needed.

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

- **Import errors** (`No module named 'server'`): ensure deploy root is the repo root and `api/index.py` is present.
- **Build fails on `lxml` / native deps**: Vercel’s Python image usually includes build tools; if it fails, open a Vercel build log and consider pinning versions or using a container-based host for the API.
- **`requirements.txt` / `-r server/requirements.txt`**: Both files must exist in the repo; the root `requirements.txt` delegates to `server/requirements.txt`.

---

## Related

- Stripe live keys and webhooks: `docs/stripe-production.md`
