# Testing guide

Step-by-step click paths for every major feature in VRT SPACE. Each section
is self-contained — work through them in order, or jump to the one you need.

Use this guide when:

- Onboarding a new developer.
- Verifying a deploy before announcing it.
- Reproducing a bug report with minimum setup.

> All paths assume you are testing against the deployed app. Replace
> `https://vrtspaceagency.onrender.com` with your environment's host if
> different.

---

## Table of contents

1. [Public free audit (anonymous)](#1-public-free-audit)
2. [Workspace signup + onboarding wizard](#2-workspace-signup--onboarding-wizard)
3. [AEO Visibility Index (public tool)](#3-aeo-visibility-index)
4. [Workspace dashboard + modules](#4-workspace-dashboard--modules)
5. [AEO workspace (P1 precision layer)](#5-aeo-workspace-p1-precision-layer)
6. [Team & client sharing (P3)](#6-team--client-sharing-p3)
7. [WordPress publishing (P4)](#7-wordpress-publishing-p4)
8. [Stripe subscription + credit grants](#8-stripe-subscription--credit-grants)
9. [Credit top-up packs](#9-credit-top-up-packs)
10. [Email + flash assertions](#10-email--flash-assertions)

---

## 1. Public free audit

Anonymous, no signup required. Drives top-of-funnel signups.

| # | Action | Expected |
|---|---|---|
| 1.1 | Go to `/` | Home page loads, hero copy + 3-pillar showcase visible |
| 1.2 | Scroll to the audit form, enter a real domain you own (e.g. `example.com`) | Form accepts the URL |
| 1.3 | Submit | Redirect to `/tools/audits/<pk>/` after 20-60s |
| 1.4 | On the result page | See overall score, performance metrics, "Save this audit" + "Now check if AI engines cite you" buttons |
| 1.5 | Click "Now check if AI engines cite you" | Lands on `/aeo-index/<your-domain>/` with the domain pre-filled |

**Red flags:** form 500s, audit stuck >2 minutes, "Couldn't complete the check" on the result page (means the audit job crashed).

---

## 2. Workspace signup + onboarding wizard

The hard-gated 3-step setup that creates the workspace.

### 2a. Fresh signup (no prior free audit)

| # | Action | Expected |
|---|---|---|
| 2a.1 | Go to `/workspace/start/` with a new email | Sign-up form renders |
| 2a.2 | Sign up | Lands on `/workspace/onboarding/` step 1 |
| 2a.3 | Fill in URL + business type + location, submit | HTMX swap to step 2 |
| 2a.4 | Click "Start the audit — uses 2 credits" | Step 2 running partial appears, scan steps advance every 3s as audit progresses |
| 2a.5 | Wait for COMPLETED | Step 3 partial appears with competitor suggestions pre-filled |
| 2a.6 | Edit / clear / accept competitors, submit | Redirect to `/workspace/` dashboard |

### 2b. Signup after a free audit (dedup path)

| # | Action | Expected |
|---|---|---|
| 2b.1 | Run a free audit at `/` for `mybrand.com` while logged out | Audit completes |
| 2b.2 | Click "Save this audit" on the result page | Sign-up form pre-fills the audit email |
| 2b.3 | Sign up | Lands on `/workspace/onboarding/` with step 3 already active (audit was adopted) |
| 2b.4 | Look for the flash message | "We found your previous audit — reusing it instead of running a duplicate." |

### 2c. Skip-to-dashboard paths

| # | Action | Expected |
|---|---|---|
| 2c.1 | At step 2, click "Skip — I'll run the audit later" | Lands on `/workspace/` (project exists, audit can run later) |
| 2c.2 | At step 2 (running), click "The audit runs in the background — go to dashboard" | Same — dashboard works while audit completes |

**Red flags:** "AttributeError: 'ClientProject' object has no attribute 'competitor_urls'" (means stale deploy without [commit 96002ea](../commit/96002ea)), step 3 shows Instagram or Tripadvisor as competitors (means SERP discovery is firing without proper business context).

---

## 3. AEO Visibility Index

Public, indexable, free tool. Drives organic SEO.

| # | Action | Expected |
|---|---|---|
| 3.1 | Go to `/aeo-index/` | Hero + search form + top performers + "How it works" |
| 3.2 | Enter a domain that's never been checked | Redirect to `/aeo-index/<domain>/` |
| 3.3 | Inspect the result page | Either: (a) full result with per-engine cards if LLM keys are set, (b) "AI engines not yet enabled" banner if not, or (c) "We're checking" if rate-limited |
| 3.4 | Header nav, footer, home page | "AEO Index" / "AEO Visibility Index" links visible |
| 3.5 | After a free audit completes | Result page shows "Now check if AI engines cite you" button pointing to `/aeo-index/<audited-domain>/` |

**Red flags:** "Couldn't complete the check" with no engines configured (means stale deploy — should say "AI engines not yet enabled" instead), 50/day quota exhausted without checks.

---

## 4. Workspace dashboard + modules

Logged-in user lands here after onboarding.

| # | Action | Expected |
|---|---|---|
| 4.1 | `/workspace/` | Audit score, SEO + AEO module cards, credit balance, audit history |
| 4.2 | Workspace nav rail | Tabs: Overview / SEO / AEO / Content / Team / Publishing |
| 4.3 | Click "Open SEO" | `/workspace/seo/` renders |
| 4.4 | Click "Open AEO" | `/workspace/aeo/` renders |
| 4.5 | Click "Content" | `/workspace/content/` renders |
| 4.6 | Click "Team" | `/workspace/team/` renders |
| 4.7 | Click "Publishing" | `/workspace/cms/credentials/` renders |
| 4.8 | Credit chip (top right of nav) | Shows remaining workspace credits |

---

## 5. AEO workspace (P1 precision layer)

| # | Action | Expected |
|---|---|---|
| 5.1 | `/workspace/aeo/` | Latest score, per-engine snapshots, competitor benchmark |
| 5.2 | Top of page | If any of `OPENAI_API_KEY` / `GEMINI_API_KEY` / `PERPLEXITY_API_KEY` are missing, a yellow banner names the missing engines |
| 5.3 | Submit "Run AEO Analysis" with a target keyword | Spends `aeo` credits (1-6 depending on plan band), creates an AEOAudit |
| 5.4 | Open the resulting audit | Three VisibilitySnapshot rows (ChatGPT / Gemini / Perplexity), each with citation count + notes |
| 5.5 | If LLM keys set | `precision_mode == "live"`, real responses appear in `queries_log` |
| 5.6 | Share link | `audit.share_token` accessible at `/aeo/share/<token>/` (public, read-only) |

**Red flags:** all engines show 0 citations + `precision_mode == "derived"` (means keys are missing), `precision_mode == "live"` but no citations (means brand-detection regex missed — check `competitor_visibility.totals` in the audit JSON).

---

## 6. Team & client sharing (P3)

### 6a. Invite a teammate (OWNER / MEMBER)

| # | Action | Expected |
|---|---|---|
| 6a.1 | `/workspace/team/` | Invite form + member list + seat count (e.g. "1/3 used" on Starter) |
| 6a.2 | Enter teammate email, role = Member, submit | Flash: "Invite emailed to ... they have 30 days to accept" |
| 6a.3 | Check the inbox (real SMTP only) | Email arrives with subject `[VRT SPACE] Invite to join <project>` and an accept link |
| 6a.4 | Click the accept link while signed in as the invitee | Membership flips to ACTIVE, redirect to dashboard |

### 6b. Client share link

| # | Action | Expected |
|---|---|---|
| 6b.1 | At `/workspace/team/`, choose role = Client, leave email blank, submit | Flash: "Client share link ready. Copy and send: <URL>" |
| 6b.2 | Open the share URL in an incognito window | Read-only project view at `/share/clients/<token>/` (no auth required) |
| 6b.3 | Confirm | Score + top recommendations visible; no edit buttons, no nav |

### 6c. Seat limit

| # | Action | Expected |
|---|---|---|
| 6c.1 | On the Free plan (1 seat), try to invite a second MEMBER | Error flash: "Your plan allows 1 seat(s). Upgrade to invite more team members." |
| 6c.2 | Upgrade via Stripe to Starter (3 seats) | Inviting works up to 2 additional members; CLIENT invites are seat-free at any plan |

**Red flags:** "Email could not be sent — share this link manually" flash on a server with SMTP configured (means SMTP creds are wrong — check `EMAIL_HOST_PASSWORD`), MEMBER invite consuming a seat for the Owner themselves (the owner counts as seat 1 implicitly — only invited Owner/Member count against the cap).

---

## 7. WordPress publishing (P4)

| # | Action | Expected |
|---|---|---|
| 7.1 | `/workspace/cms/credentials/` | Empty connection form |
| 7.2 | In WordPress: Users → Profile → Application Passwords → generate one named "VRT SPACE" | Get back a space-separated 24-char password |
| 7.3 | In VRT SPACE: enter site URL + WP username + the app password, submit | Saved confirmation flash + "Connected platforms" list shows the entry |
| 7.4 | Go to `/workspace/content/` and open any editorial task | "Push to WordPress" button visible |
| 7.5 | Click "Push to WordPress" | Spends 1 `publish` credit, flash: "Draft pushed to WordPress. Open it in your dashboard: <URL>" |
| 7.6 | Open the link in WP admin | Draft post present, title + body match the editorial task |
| 7.7 | Inspect `CMSPushLog` in Django admin | One row with `status=SUCCESS`, `remote_post_id`, `remote_post_url` populated |

**Red flags:** 401 from WordPress (means the username/app-password is wrong), 404 from the endpoint (means the site URL is missing `/wp-json/` access — install/enable the REST API plugin or remove security plugins blocking it).

---

## 8. Stripe subscription + credit grants

> Use **Stripe test mode** for these flows. Test card: `4242 4242 4242 4242`, any future expiry, any CVC, any ZIP.

| # | Action | Expected |
|---|---|---|
| 8.1 | At `/workspace/`, scroll to the plans panel | Three tiers visible: Starter $59 / Growth $149 / Authority $349 |
| 8.2 | Click "Upgrade to Starter" | Redirect to Stripe-hosted Checkout |
| 8.3 | Pay with test card | Redirect back to `/workspace/billing/success/?session_id=...` |
| 8.4 | Refresh `/workspace/` | Credit chip shows 60 credits, plan badge reads "Starter" |
| 8.5 | Inspect `WorkspaceCreditLedger` | One GRANT entry of +60 credits for the current cycle |
| 8.6 | Run any audit/AEO/SEO action | DEBIT entry recorded, remaining count drops |
| 8.7 | Stripe dashboard → Webhooks | Confirm the `/billing/stripe/webhook/` endpoint received the `checkout.session.completed` event |

**Red flags:** webhook returns 400 (signing secret mismatch — check `STRIPE_WEBHOOK_SECRET`), credit grant never appears (check `sync_workspace_plan_catalog()` was run), wrong credit amount (price ID doesn't match the catalog tier).

---

## 9. Credit top-up packs

| # | Action | Expected |
|---|---|---|
| 9.1 | Use a paid plan (so the top-up UI shows) | "Top up credits" button visible in account panel |
| 9.2 | Pick the $25 pack, complete Stripe checkout | Redirect to success page |
| 9.3 | Refresh balance | Credits increased by 30 (the pack's allotment) |
| 9.4 | `WorkspaceCreditLedger` | New GRANT entry tagged with the top-up reference key |

---

## 10. Email + flash assertions

Every flow listed above pairs a flash message with an email. Confirm both fire.

| Flow | Flash | Email subject |
|---|---|---|
| Team invite (member) | "Invite emailed to ... they have 30 days to accept" | `[VRT SPACE] Invite to join <project>` |
| Team invite (client) | "Client share link emailed to ..." | `[VRT SPACE] You have a read-only share for <project>` |
| Credit alert 50% | (none — silent until 75%) | `[VRT SPACE] You've used 50% of this month's credits` |
| Credit alert 100% | "You've used your full monthly credit allowance" | `[VRT SPACE] You've used all of this month's credits` |
| Audit completion (if email reports enabled) | (silent) | `[VRT SPACE] Your audit for <domain> is ready` |

**To verify without a real SMTP backend:** set `DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` and watch the dev log; the full message body is printed verbatim.

---

## Running the automated test suite

```bash
# From the repo root
python manage.py test --verbosity=1
```

Current state (as of the last green deploy):

- 7 pre-existing failures fixed; 7 remain (WorkspaceBilling × 4, workspace_seo profile form, fix_locations dashboard, email_reports share_links).
- The 7 remaining failures are tagged in the commit messages and need deeper product investigation, not assertion edits.
- All P1-P5 + Tier 1-3 specific tests pass.

## Common gotchas

- **The worktree at `.claude/worktrees/heuristic-villani-65d4da/`** is a parallel git checkout on the feature branch. If you `cd` into it accidentally, `manage.py test` will pick up its (older) test files. Always run tests from the repo root.
- **Cache-driven rate limits** for SERP discovery and the AEO index will silently mask test runs if you hit them. Clear with:
  ```bash
  python manage.py shell -c "from django.core.cache import cache; cache.clear()"
  ```
- **LLM keys must be set in the runtime environment**, not just `.env`. Render dashboard → Environment tab → add the three keys → trigger redeploy.
