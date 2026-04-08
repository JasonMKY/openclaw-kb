import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.routers import ingest, query, documents, bundles, payments
from server.services.vectorstore import init_pinecone

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _write_frontend_config() -> None:
    """Write Supabase public config to frontend/config.json (best-effort).

    On read-only filesystems (e.g. Vercel) this will silently fail;
    the frontend falls back to the ``GET /frontend/config.json`` route.
    """
    config = {
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    }
    try:
        FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
        (FRONTEND_DIR / "config.json").write_text(json.dumps(config), encoding="utf-8")
    except OSError:
        logger.info("Could not write frontend/config.json (read-only FS); using API route fallback.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _write_frontend_config()
    try:
        await init_pinecone()
    except Exception:
        logger.exception("Pinecone init failed; vector operations will retry on first request.")
    yield


app = FastAPI(
    title="OpenClaw Knowledge Base API",
    description="Semantic knowledge base with vector search and RAG for OpenClaw agents.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return JSON on unexpected errors so the SPA can read `detail` (not HTML 500 pages)."""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if not isinstance(detail, (str, list, dict)):
            detail = str(detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    msg = str(exc).strip() or type(exc).__name__
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {msg}"[:2000]},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, tags=["Ingest"])
app.include_router(query.router, tags=["Query"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(bundles.router, tags=["Bundles"])
app.include_router(payments.router, tags=["Payments"])


@app.get("/frontend/config.json", include_in_schema=False)
async def frontend_config() -> JSONResponse:
    """Serve Supabase public config dynamically (works on read-only FS)."""
    return JSONResponse({
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    })


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Serve the frontend UI at the root URL."""
    return FileResponse(FRONTEND_DIR / "index.html")


if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
