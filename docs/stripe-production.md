# Stripe: moving from Test to Live (production)

You do **not** need to change application code to use Stripe in production. The same API routes work; only **environment variables**, the **Stripe Dashboard (Live mode)**, and your **public site URL** change.

---

## 1. Production `.env`

Set these on the server that runs FastAPI (restart the process after saving).

| Variable | Test (typical) | Production |
|----------|----------------|------------|
| `STRIPE_SECRET_KEY` | `sk_test_...` | **`sk_live_...`** from Stripe Dashboard → **Developers** → **API keys** (toggle **Live**) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from a **Test** webhook | **`whsec_...` from a Live webhook** (see section 2 — it is different from test) |
| `KB_API_URL` | `http://localhost:8000` | **Public HTTPS URL** users use to open the app, e.g. `https://yourdomain.com` or `https://api.yourdomain.com` |

`KB_API_URL` is used by the backend as the base for:

- Stripe Checkout **success** and **cancel** URLs  
- Stripe Connect **return** and **refresh** URLs  

It must match the URL in the browser (no wrong host or `http` in production if you serve over HTTPS).

There is no separate “Stripe production API URL” — Stripe’s API is always `https://api.stripe.com`; **test vs live** is determined only by **`sk_test_`** vs **`sk_live_`**.

---

## 2. Stripe Dashboard — Live mode

1. Turn off **Test mode** (use **Live** in the Dashboard).

2. **Developers → Webhooks**  
   - Add endpoint: `https://<your-production-host>/stripe-webhook`  
   - Subscribe at least to **`checkout.session.completed`**.  
   - Copy the endpoint **Signing secret** (`whsec_...`) into **`STRIPE_WEBHOOK_SECRET`** in production `.env`.

3. **Connect**  
   - Complete **Live** Connect onboarding for your platform (same kind of setup as in test, but under Live).

4. **API keys**  
   - Use the **Live** secret key (`sk_live_...`) only in production; never commit it to git.

---

## 3. Deploy and HTTPS

- Restart **Uvicorn** (or your process manager) after updating `.env`.
- Use **HTTPS** in production for your site and API if users pay with real cards.

---

## 4. Supabase (unchanged for Stripe specifically)

Point `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` at your **production** Supabase project if you use a separate project from development. Stripe does not require extra Supabase variables.

---

## 5. Sellers and Stripe Connect (important)

- Connected accounts created in **Test** mode (`acct_...` with test keys) **do not** work with **`sk_live_...`**.
- In production, each seller should go through **Account → Connect Stripe** again so Stripe creates **Live** Express accounts and your `profiles.stripe_account_id` values are **live** account IDs.

---

## 6. OpenClaw / agents

In `openclaw.json` (or your agent config), set **`KB_API_URL`** to your **production** API base URL so skills call the right server.

---

## Quick checklist

- [ ] `STRIPE_SECRET_KEY` = `sk_live_...` on production  
- [ ] Live **webhook** registered; `STRIPE_WEBHOOK_SECRET` = that endpoint’s signing secret  
- [ ] `KB_API_URL` = public HTTPS URL of the app  
- [ ] Live **Connect** finished for the platform account  
- [ ] Server restarted  
- [ ] Sellers re-onboard **Connect** in Live  
- [ ] Supabase env vars point at production DB if applicable  
- [ ] Agent `KB_API_URL` updated for production  

---

## Reference (code)

- Stripe key and webhook: `server/routers/payments.py` (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `KB_API_URL` via `FRONTEND_ORIGIN`)  
- Example env names: `.env.example`

## Deploying on Vercel

Set **`KB_API_URL`** to your production hostname (e.g. `https://your-app.vercel.app`). See **`docs/vercel-deployment.md`** for the full Vercel checklist.
