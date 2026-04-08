"""Supabase PostgREST access with the service role key (bypasses RLS).

Uses httpx instead of supabase-py to avoid import/shadowing issues on some setups.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _strip_env(value: str) -> str:
    s = value.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


SUPABASE_URL = _strip_env(os.getenv("SUPABASE_URL", "")).rstrip("/")
SUPABASE_SERVICE_KEY = _strip_env(os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))


def require_supabase_config() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=500,
            detail="Supabase is not configured (set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)",
        )


def _rest_base() -> str:
    return f"{SUPABASE_URL}/rest/v1"


def _headers(
    *,
    accept_object: bool = False,
    prefer: str | None = None,
) -> dict[str, str]:
    h: dict[str, str] = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if accept_object:
        h["Accept"] = "application/vnd.pgrst.object+json"
    if prefer:
        h["Prefer"] = prefer
    return h


def _raise_if_sb_error(r: httpx.Response, *, context: str) -> None:
    if r.is_success:
        return
    if r.status_code == 401:
        logger.warning("Supabase rejected API key (%s): %s", context, r.text)
        raise HTTPException(
            status_code=502,
            detail=(
                "Supabase rejected the server API key. Set SUPABASE_SERVICE_ROLE_KEY in .env "
                "to the service_role secret from Supabase Dashboard → Project Settings → API "
                "(not the anon key). Remove extra spaces or quotes, save .env, and restart Uvicorn."
            ),
        )
    logger.warning("Supabase request failed (%s): %s %s", context, r.status_code, r.text)
    detail = r.text[:800] if r.text else r.reason_phrase
    try:
        payload = r.json()
        if isinstance(payload, dict):
            msg = payload.get("message") or payload.get("error_description")
            hint = payload.get("hint")
            if msg:
                detail = f"{msg}" + (f" ({hint})" if hint else "")
    except Exception:
        pass
    raise HTTPException(
        status_code=502,
        detail=f"Database error ({context}): {detail}",
    )


async def sb_select_single(
    table: str,
    *,
    select: str,
    eq: dict[str, str],
) -> dict[str, Any] | None:
    """Return one row or None (0 rows / not found)."""
    require_supabase_config()
    params: dict[str, str] = {"select": select}
    for col, val in eq.items():
        params[col] = f"eq.{val}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{_rest_base()}/{table}",
            params=params,
            headers=_headers(accept_object=True),
        )
    if r.status_code in (406, 404):
        return None
    _raise_if_sb_error(r, context=f"GET {table} single")
    data = r.json()
    return data if isinstance(data, dict) else None


async def sb_select_many(
    table: str,
    *,
    select: str,
    eq: dict[str, str] | None = None,
    in_: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    require_supabase_config()
    params: dict[str, str] = {"select": select}
    if eq:
        for col, val in eq.items():
            params[col] = f"eq.{val}"
    if in_:
        for col, ids in in_.items():
            inner = ",".join(ids)
            params[col] = f"in.({inner})"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            f"{_rest_base()}/{table}",
            params=params,
            headers=_headers(),
        )
    _raise_if_sb_error(r, context=f"GET {table} many")
    data = r.json()
    return data if isinstance(data, list) else []


async def sb_patch(
    table: str,
    *,
    eq: dict[str, str],
    body: dict[str, Any],
) -> None:
    require_supabase_config()
    params: dict[str, str] = {}
    for col, val in eq.items():
        params[col] = f"eq.{val}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.patch(
            f"{_rest_base()}/{table}",
            params=params,
            json=body,
            headers=_headers(prefer="return=minimal"),
        )
    _raise_if_sb_error(r, context=f"PATCH {table}")


async def sb_upsert_row(
    table: str,
    row: dict[str, Any],
    *,
    on_conflict: str,
) -> None:
    require_supabase_config()
    # PostgREST: merge duplicates on unique constraint
    prefer = "resolution=merge-duplicates,return=minimal"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{_rest_base()}/{table}",
            params={"on_conflict": on_conflict},
            json=row,
            headers=_headers(prefer=prefer),
        )
    _raise_if_sb_error(r, context=f"POST {table} upsert")
