"""
Vercel serverless entry: ASGI adapter for the FastAPI app.

The repo root must be on PYTHONPATH so `server` imports resolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mangum import Mangum

from server.main import app as _fastapi_app

# Vercel's Python runtime expects a variable named `app` (ASGI/WSGI).
app = Mangum(_fastapi_app, lifespan="on")
