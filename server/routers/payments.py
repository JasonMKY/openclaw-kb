import logging
import os
from typing import Any

import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from server.services.supabase_admin import (
    sb_patch,
    sb_select_many,
    sb_select_single,
    sb_upsert_row,
)

logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
FRONTEND_ORIGIN = os.getenv("KB_API_URL", "http://localhost:8000")

PLATFORM_FEE_PERCENT = 5


def _stripe_to_dict(obj: object) -> dict:
    """Stripe SDK v8+ may return objects without ``.get()``; normalize to a dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            raw = to_dict()
            return dict(raw) if isinstance(raw, dict) else {}
        except Exception:
            pass
    try:
        return {k: obj[k] for k in obj}  # type: ignore[index,union-attr]
    except Exception:
        return {}


# ── Schemas ──────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    kb_id: str
    buyer_id: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class ConnectRequest(BaseModel):
    user_id: str


class ConnectResponse(BaseModel):
    onboarding_url: str


class DashboardRequest(BaseModel):
    user_id: str


class DashboardResponse(BaseModel):
    dashboard_url: str


class EarningsRequest(BaseModel):
    user_id: str


class ReconcileRequest(BaseModel):
    user_id: str


class EarningsResponse(BaseModel):
    """Seller-side sales for KBs you authored. Amounts are in cents (USD)."""
    gross_sales_cents: int = Field(description="Total buyer payments on completed sales")
    platform_fee_cents: int
    net_earned_cents: int = Field(description="Your share after platform fee")
    total_sales: int = Field(description="Count of completed purchases")
    pending_sales: int = Field(description="Checkouts not yet paid or not synced")
    refunded_sales: int = Field(default=0, description="Count of refunded purchases")
    total_earned_cents: int = Field(default=0, description="Same as gross_sales_cents (legacy alias)")


def _checkout_session_paid(sd: dict) -> bool:
    if sd.get("payment_status") == "paid":
        return True
    if sd.get("status") == "complete" and sd.get("payment_status") in ("paid", "no_payment_required"):
        return True
    return False


async def _reconcile_stripe_checkout_rows(rows: list[dict[str, Any]]) -> int:
    """Mark kb_purchases completed when Stripe Checkout already succeeded (webhook may have missed)."""
    if not stripe.api_key:
        return 0
    updated = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if row.get("status") != "pending":
            continue
        sid = row.get("stripe_session_id")
        buyer_id = row.get("buyer_id")
        kb_id = row.get("kb_id")
        if not sid or not buyer_id or not kb_id:
            continue
        key = (str(buyer_id), str(kb_id))
        if key in seen:
            continue
        seen.add(key)
        try:
            sess = stripe.checkout.Session.retrieve(sid)
        except stripe.StripeError as exc:
            logger.warning("Stripe session retrieve %s: %s", sid, exc)
            continue
        sd = _stripe_to_dict(sess)
        if _checkout_session_paid(sd):
            await sb_patch(
                "kb_purchases",
                eq={"buyer_id": str(buyer_id), "kb_id": str(kb_id)},
                body={"status": "completed"},
            )
            updated += 1
            logger.info("Reconciled purchase to completed session=%s buyer=%s kb=%s", sid, buyer_id, kb_id)
    return updated


async def reconcile_purchases_for_user(user_id: str) -> int:
    """Reconcile pending rows where this user is the buyer or the author of the KB."""
    kbs = await sb_select_many(
        "knowledge_bases",
        select="id",
        eq={"author_id": user_id},
    )
    kb_ids = [kb["id"] for kb in kbs]

    rows_buyer = await sb_select_many(
        "kb_purchases",
        select="buyer_id,kb_id,stripe_session_id,status",
        eq={"buyer_id": user_id, "status": "pending"},
    )
    rows_seller: list[dict[str, Any]] = []
    if kb_ids:
        rows_seller = await sb_select_many(
            "kb_purchases",
            select="buyer_id,kb_id,stripe_session_id,status",
            eq={"status": "pending"},
            in_={"kb_id": kb_ids},
        )

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows_buyer + rows_seller:
        key = (str(r["buyer_id"]), str(r["kb_id"]))
        merged[key] = r
    return await _reconcile_stripe_checkout_rows(list(merged.values()))


# ── POST /create-checkout ────────────────────────────────────────────────────

@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(body: CheckoutRequest) -> CheckoutResponse:
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    kb = await sb_select_single(
        "knowledge_bases",
        select="id,name,price_cents,author_id",
        eq={"id": body.kb_id},
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    price = kb.get("price_cents", 0)
    if price <= 0:
        raise HTTPException(status_code=400, detail="This KB is free — no checkout needed")

    author = await sb_select_single(
        "profiles",
        select="stripe_account_id",
        eq={"id": kb["author_id"]},
    )
    seller_stripe = (author or {}).get("stripe_account_id")
    if not seller_stripe:
        raise HTTPException(status_code=400, detail="Seller has not connected Stripe yet")

    try:
        acct = stripe.Account.retrieve(seller_stripe)
    except stripe.StripeError as exc:
        logger.warning("Could not load seller Connect account %s: %s", seller_stripe, exc)
        raise HTTPException(
            status_code=400,
            detail="The seller's Stripe account could not be verified. They may need to reconnect under Account settings.",
        )

    acct_d = _stripe_to_dict(acct)
    caps = _stripe_to_dict(acct_d.get("capabilities"))
    transfers = caps.get("transfers")
    if transfers is not None and transfers != "active":
        raise HTTPException(
            status_code=400,
            detail=(
                "This knowledge base's seller has not finished Stripe Connect onboarding, so paid checkout is disabled. "
                "They must open Account → Connect Stripe and complete all steps until Stripe enables payouts "
                f"(transfers capability is '{transfers}', not active yet)."
            ),
        )

    fee = int(price * PLATFORM_FEE_PERCENT / 100)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price,
                    "product_data": {"name": kb["name"]},
                },
                "quantity": 1,
            }],
            payment_intent_data={
                "application_fee_amount": fee,
                "transfer_data": {"destination": seller_stripe},
            },
            metadata={"kb_id": body.kb_id, "buyer_id": body.buyer_id},
            success_url=f"{FRONTEND_ORIGIN}/?checkout=success&kb_id={body.kb_id}",
            cancel_url=f"{FRONTEND_ORIGIN}/?checkout=cancel",
        )
    except stripe.StripeError as exc:
        logger.error("Stripe session creation failed: %s", exc)
        msg = getattr(exc, "user_message", None) or str(exc)
        if "stripe_transfers" in msg or (
            "destination" in msg.lower() and "transfer" in msg.lower()
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The seller's Stripe account cannot receive payouts yet. "
                    "They must finish Connect onboarding (Account → Connect Stripe) until Stripe activates transfers."
                ),
            )
        raise HTTPException(status_code=502, detail=msg)

    await sb_upsert_row(
        "kb_purchases",
        {
            "buyer_id": body.buyer_id,
            "kb_id": body.kb_id,
            "stripe_session_id": session.id,
            "amount_cents": price,
            "fee_cents": fee,
            "status": "pending",
        },
        on_conflict="buyer_id,kb_id",
    )

    return CheckoutResponse(checkout_url=session.url)


# ── POST /stripe-webhook ────────────────────────────────────────────────────

@router.post("/stripe-webhook")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session_raw = event["data"]["object"]
        session = session_raw if isinstance(session_raw, dict) else _stripe_to_dict(session_raw)
        meta = session.get("metadata") or {}
        kb_id = meta.get("kb_id")
        buyer_id = meta.get("buyer_id")

        if kb_id and buyer_id:
            await sb_patch(
                "kb_purchases",
                eq={"buyer_id": str(buyer_id), "kb_id": str(kb_id)},
                body={"status": "completed"},
            )
            logger.info("Purchase completed: buyer=%s kb=%s", buyer_id, kb_id)

    return {"received": True}


# ── POST /connect-stripe ────────────────────────────────────────────────────

@router.post("/connect-stripe", response_model=ConnectResponse)
async def connect_stripe(body: ConnectRequest) -> ConnectResponse:
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    profile = await sb_select_single(
        "profiles",
        select="stripe_account_id",
        eq={"id": body.user_id},
    )
    existing = (profile or {}).get("stripe_account_id")

    if existing:
        try:
            link = stripe.AccountLink.create(
                account=existing,
                refresh_url=f"{FRONTEND_ORIGIN}/?stripe=refresh",
                return_url=f"{FRONTEND_ORIGIN}/?stripe=connected",
                type="account_onboarding",
            )
            return ConnectResponse(onboarding_url=link.url)
        except stripe.StripeError:
            pass

    try:
        account = stripe.Account.create(type="express")
        await sb_patch(
            "profiles",
            eq={"id": body.user_id},
            body={"stripe_account_id": account.id},
        )

        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{FRONTEND_ORIGIN}/?stripe=refresh",
            return_url=f"{FRONTEND_ORIGIN}/?stripe=connected",
            type="account_onboarding",
        )
    except stripe.StripeError as exc:
        logger.error("Stripe Connect onboarding failed: %s", exc)
        msg = getattr(exc, "user_message", None) or str(exc)
        if "signed up for connect" in msg.lower():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Stripe Connect is not activated for your Stripe account. "
                    "In the Stripe Dashboard (same mode as your API key: Test or Live), open "
                    "https://dashboard.stripe.com/connect and finish Connect onboarding for your platform. "
                    "Then try Connect again."
                ),
            )
        raise HTTPException(status_code=502, detail=msg)

    return ConnectResponse(onboarding_url=link.url)


# ── POST /stripe-dashboard ──────────────────────────────────────────────────

@router.post("/stripe-dashboard", response_model=DashboardResponse)
async def stripe_dashboard(body: DashboardRequest) -> DashboardResponse:
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    profile = await sb_select_single(
        "profiles",
        select="stripe_account_id",
        eq={"id": body.user_id},
    )
    account_id = (profile or {}).get("stripe_account_id")
    if not account_id:
        raise HTTPException(status_code=400, detail="No Stripe account connected")

    try:
        login_link = stripe.Account.create_login_link(account_id)
    except stripe.StripeError as exc:
        logger.error("Stripe dashboard link failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    return DashboardResponse(dashboard_url=login_link.url)


# ── POST /reconcile-kb-purchases ─────────────────────────────────────────────

@router.post("/reconcile-kb-purchases")
async def reconcile_kb_purchases_endpoint(body: ReconcileRequest) -> dict:
    """Sync kb_purchases with Stripe when webhooks are unavailable (e.g. local dev)."""
    n = await reconcile_purchases_for_user(body.user_id)
    return {"updated": n}


# ── POST /seller-earnings ───────────────────────────────────────────────────

@router.post("/seller-earnings", response_model=EarningsResponse)
async def seller_earnings(body: EarningsRequest) -> EarningsResponse:
    await reconcile_purchases_for_user(body.user_id)

    kbs = await sb_select_many(
        "knowledge_bases",
        select="id",
        eq={"author_id": body.user_id},
    )
    kb_ids = [kb["id"] for kb in kbs]

    if not kb_ids:
        return EarningsResponse(
            gross_sales_cents=0,
            platform_fee_cents=0,
            net_earned_cents=0,
            total_sales=0,
            pending_sales=0,
            refunded_sales=0,
            total_earned_cents=0,
        )

    rows = await sb_select_many(
        "kb_purchases",
        select="amount_cents,fee_cents,status,kb_id",
        in_={"kb_id": kb_ids},
    )

    completed = [r for r in rows if r.get("status") == "completed"]
    pending = [r for r in rows if r.get("status") == "pending"]
    refunded = [r for r in rows if r.get("status") == "refunded"]
    gross = sum(int(r["amount_cents"]) for r in completed)
    total_fees = sum(int(r["fee_cents"]) for r in completed)

    return EarningsResponse(
        gross_sales_cents=gross,
        total_earned_cents=gross,
        platform_fee_cents=total_fees,
        net_earned_cents=gross - total_fees,
        total_sales=len(completed),
        pending_sales=len(pending),
        refunded_sales=len(refunded),
    )
