"""
Vercel entrypoint for the FastAPI app.

Vercel's **FastAPI** framework preset looks for `main.py` at the repo root with an ASGI
`app`. Local development should keep using: `uvicorn server.main:app`
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server.main import app  # noqa: E402
