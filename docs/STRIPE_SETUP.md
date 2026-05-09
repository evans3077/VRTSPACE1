# Stripe setup guide

Everything you need to wire VRT SPACE up to Stripe in production. Follow the
sections in order — each one corresponds to a feature that depends on Stripe
being configured.

---

## 1. Create your Stripe account and API keys

1. Sign up / log in at https://dashboard.stripe.com.
2. Stay in **Test mode** while you verify the integration. Switch to Live once
   you have confirmed an end-to-end checkout works.
3. Go to **Developers → API keys** and copy:
   - **Publishable key** (starts with `pk_test_...` or `pk_live_...`)
   - **Secret key** (starts with `sk_test_...` or `sk_live_...`)

Set these in your environment:

```env
STRIPE_PUBLISHABLE_KEY=pk_test_xxx
STRIPE_SECRET_KEY=sk_test_xxx
```

> The platform automatically detects `STRIPE_ENABLED=True` when both keys are
> set. Without them, all checkout actions raise a clear `BillingError`.

---

## 2. Create the four subscription Prices

Each plan needs a **recurring monthly Price** in Stripe. The product names in
Stripe should match these labels and the amounts must match the public pricing.

| Plan      | Monthly amount | Env var to set         |
|-----------|----------------|------------------------|
| Starter   | $59            | `STRIPE_PRICE_STARTER` |
| Growth    | $149           | `STRIPE_PRICE_GROWTH`  |
| Authority | $349           | `STRIPE_PRICE_AUTHORITY` |
| Enterprise| Custom         | `STRIPE_PRICE_ENTERPRISE` (optional) |

For each plan:

1. Go to **Products → Add product** in Stripe.
2. Name it (e.g. "VRT SPACE Starter") and set a description.
3. Under **Pricing**, choose:
   - **Pricing model:** Standard pricing
   - **Recurring → Monthly**
   - **Amount:** the dollar value above (e.g. `59.00`)
4. Save the product. Stripe shows you the new **Price ID** (starts with
   `price_...`). Copy it.
5. Paste it into the matching env var in your deployment environment.

Final env block for subscriptions:

```env
STRIPE_PRICE_STARTER=price_xxx
STRIPE_PRICE_GROWTH=price_xxx
STRIPE_PRICE_AUTHORITY=price_xxx
STRIPE_PRICE_ENTERPRISE=price_xxx   # optional
```

After deploying, run this once so the WorkspacePlan rows in the database
mirror your Stripe configuration (the admin UI will then show which Price is
linked to which plan):

```bash
python manage.py shell -c "from apps.leads.billing import sync_workspace_plan_catalog; sync_workspace_plan_catalog()"
```

---

## 3. Create the three credit top-up Prices

Top-up packs are **one-off purchases** (`mode=payment`), distinct from
subscription Prices. Users buy these when they hit their monthly credit cap.

| Pack       | Credits | Amount | Env var to set         |
|------------|---------|--------|------------------------|
| Small      | 10      | $10    | `STRIPE_PRICE_TOPUP_10` |
| Medium     | 30      | $25    | `STRIPE_PRICE_TOPUP_30` |
| Large      | 70      | $50    | `STRIPE_PRICE_TOPUP_70` |

For each pack:

1. Go to **Products → Add product**.
2. Name it (e.g. "VRT SPACE 10 Credits Top-up").
3. Under **Pricing**:
   - **Pricing model:** Standard pricing
   - **One-time** (NOT recurring)
   - **Amount:** dollar value from the table above
4. Save. Copy the new **Price ID**.
5. Paste it into the matching env var.

Final env block for top-ups:

```env
STRIPE_PRICE_TOPUP_10=price_xxx
STRIPE_PRICE_TOPUP_30=price_xxx
STRIPE_PRICE_TOPUP_70=price_xxx
```

> The credit amounts (10 / 30 / 70) and the dollar labels are configured in
> code (`config/settings.py`). If you change the amounts in Stripe, update
> `STRIPE_TOPUP_PACKS` in settings.py to match.

The "Buy more credits" panel on the Account dashboard will only render packs
whose `STRIPE_PRICE_TOPUP_*` env var is set — so you can launch with one
pack and add the others later without touching code.

---

## 4. Configure the webhook

The platform listens for Stripe webhooks at:

```
POST  /billing/stripe/webhook/
```

Set this up in Stripe:

1. Go to **Developers → Webhooks → Add endpoint**.
2. **Endpoint URL:** `https://YOUR-DOMAIN/billing/stripe/webhook/`
3. **Events to send** — at minimum:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Save. Stripe shows the **Signing secret** (starts with `whsec_...`). Copy
   it and set in your environment:

```env
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

The webhook handler:
- Routes `mode=subscription` sessions through `sync_subscription_from_checkout_session` (sets the user's plan and grants monthly credits).
- Routes `mode=payment` sessions (top-ups) through `sync_topup_from_checkout_session` (grants the bonus credits idempotently via the Stripe session ID as the dedupe key).

---

## 5. Verify end-to-end

After all env vars are set and the webhook endpoint is reachable, do a smoke test:

1. **Subscription flow:**
   - Log in as a test user, click an upgrade button (e.g. Starter).
   - Complete the Stripe checkout with test card `4242 4242 4242 4242`.
   - Expect: redirect back to the workspace dashboard with a success message
     and the new plan's credit grant visible in the credit balance card.

2. **Top-up flow:**
   - Go to **Account → Buy more credits** and click "Buy 10 credits".
   - Complete checkout with a test card.
   - Expect: redirect back to the account dashboard, the credit balance jumps
     by 10, and a "Top-up: 10 credits" entry appears in the recent activity
     list.

If either step fails, check:
- Webhook delivery logs in Stripe (Developers → Webhooks → click endpoint → Recent deliveries).
- Django logs for `BillingError` or webhook signature failures.
- That the env var values exactly match what Stripe shows (no trailing whitespace, correct mode/test vs live).

---

## 6. Going live

When you are ready to switch from Test mode to Live mode:

1. Re-create all six prices (4 subscription + 3 top-up — or however many
   you've enabled) in Live mode. Stripe price IDs do **not** transfer between
   test and live.
2. Replace every `STRIPE_*` env var with the live version.
3. Re-create the webhook endpoint in Live mode and use the new
   `STRIPE_WEBHOOK_SECRET`.
4. Run `sync_workspace_plan_catalog()` again so the DB mirrors the live
   configuration.
5. Do another full smoke test with a real card (you can refund it
   immediately in the Stripe dashboard).

---

## Quick reference — full env block

```env
# Required for any Stripe activity
STRIPE_PUBLISHABLE_KEY=pk_xxx
STRIPE_SECRET_KEY=sk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Subscription plans
STRIPE_PRICE_STARTER=price_xxx
STRIPE_PRICE_GROWTH=price_xxx
STRIPE_PRICE_AUTHORITY=price_xxx
STRIPE_PRICE_ENTERPRISE=price_xxx   # optional

# Credit top-up packs (each is independent — set the ones you want to offer)
STRIPE_PRICE_TOPUP_10=price_xxx
STRIPE_PRICE_TOPUP_30=price_xxx
STRIPE_PRICE_TOPUP_70=price_xxx
```
