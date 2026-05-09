# VRTSPACE1 — Product Vision & Build Roadmap
*(Captured from /grill-me session — May 2026)*

---

## Vision

A fully self-serve SaaS platform for small SEO/AEO agencies (2–10 people managing multiple client sites).
No human support needed. Users login, run audits, subscribe, track progress, and see value independently.
Target: **5,000 paying users/month by end of month 12.**
Tagline: *"We don't just rank websites. We make brands answer engines trust."*

---

## Competitive Wedge

Two differentiators over Ahrefs/SEMrush:
1. **AI search visibility (AEO/GEO)** — tracking how a brand appears inside ChatGPT, Gemini, Perplexity. Neither incumbent owns this space yet.
2. **Change tracking over time** — agencies see how their client's scores shift as they implement suggestions. Automated weekly/monthly audits with score deltas drive habitual return visits.

---

## Ideal Customer

**Small agency (2–10 people) managing 3–15 client websites.**
- Has budget, bills tools back to clients
- Feels pain of context-switching between tools
- If they find value, they bring all their clients — fastest path to 5,000 users

---

## Conversion Funnel

### The "Aha Moment"
Running an audit and seeing a side-by-side AEO visibility comparison:
> "Your client is invisible in ChatGPT for 8 of their 10 target queries. Competitor X is cited in 7 of them."

That's a screenshot an agency sends their client to justify the subscription.

### Free Tier (tightened from current)
- 2 starter audits per cycle
- 1 tracked website
- **2 critical issues only** (currently 3 — reduce to create more mystery)
- Overall score + 4 category gauges
- **No PDF download** (move to Starter perk)
- Guided diagnosis CTA → "Create Free Workspace"

### Starter → Growth → Authority unlock path
| Tier | Price | Audits/mo | Websites | SEO | AEO | Content | Backlinks |
|------|-------|-----------|----------|-----|-----|---------|-----------|
| Free | $0 | 2 | 1 | 0 | 0 | 0 | 0 |
| Starter | $59 | 8 | 3 | 4 | 4 | 2 | 0 |
| Growth | $149 | 24 | 10 | 12 | 10 | 16 | 80 |
| Authority | $349 | 80 | 25 | 36 | 24 | 60 | 250 |

---

## Credit System

- **Monthly credits** are the currency for all actions (1 audit = 1 credit, 1 AEO scan = 1 credit, 1 content draft = 2 credits)
- When credits run out: **hard stop + top-up option** (starting at $10 for extra credits — no forced plan upgrade)
- **Credit alerts at 50%, 75%, 90%, and 0%** — email + in-app notifications
- Users must always know where their credits are going — transparent credit ledger in dashboard
- `WorkspaceCreditLedger` already exists in codebase — extend for alerts and top-ups

---

## Notifications

- **Users**: Email + in-app for credit alerts and audit completions
- **Influencers**: Email monthly statement (conversions + payout amount)
- Infrastructure exists (`send_audit_report_email_task`) — extend it

---

## AEO Data Collection

- **Phase 1 (now)**: SerpAPI as primary source — Google AI Overviews, related questions, citations. Already integrated in `apps/aeo/services.py` and `apps/seo/intelligence.py`
- **Phase 2 (Authority tier, v2)**: Real queries to ChatGPT, Gemini, Perplexity APIs for users paying $349/month. They deserve the real thing.

---

## Acquisition Strategy

### Phase 1 — Influencer Affiliate Launch
- 20 SEO niche influencers with free platform access
- Target: 30 conversions per influencer = **600 users to start**
- Commission: 20–30% on first payment (varies by plan), 15% recurring
- **Needs building**: Lightweight in-house affiliate tracking system
  - Referral code on signup → attributed to `Lead`
  - Commission calculated on Stripe webhook
  - Monthly payout statement emailed to influencer
  - No third-party tools — built inside the platform

### Phase 2 — Product-Led Virality
- Shared audit report links (`SharedAuditLink` already exists) — agency shares with client, client discovers platform
- SEO content targeting "AEO audit tool", "AI search visibility checker", "GEO optimization"

### Phase 3 — Broader Affiliate Program
- Scale to larger affiliate network after Phase 1 validates the funnel

---

## Agency Dashboard (FIRST BUILD TARGET)

**The single feature needed to show influencers the platform.**

### What it shows (bird's-eye view of all client projects):
- Client site name + domain
- Overall score with **color delta since last audit** (green ↑, red ↓, grey = no change)
- **Most at-risk category badge** (e.g. "AEO Critical", "Performance Warning")
- Last audit date with subtle warning if >30 days ago
- Quick "Run Audit" CTA per client card

### Data available today:
- `ClientProject` — client list
- `AuditRun` — scores, timestamps
- All 10 score dimensions already stored

**This is a pure UI/template build — all data exists in the database.**

---

## Retention Strategy (Biggest Risk)

Retention past month 1–2 is the hardest problem and the most important one.

**Retention levers to build:**
1. **Automated scheduled audits** (WEEKLY/MONTHLY) — `WorkspaceAuditSchedule` already exists, needs to be surfaced prominently
2. **Score delta notifications** — "Your client's AEO score dropped 12 points since last week"
3. **Credit alerts** — keeps users engaged between sessions
4. **Progress narrative** — show a timeline of improvements: "In 60 days, your client's SEO score improved from 54 → 71"
5. **Agency landing page** — dedicated page for influencer traffic that speaks directly to agencies

---

## For Agencies Landing Page

- Separate URL from homepage (homepage is too generic)
- Speaks directly to agency pain: "Manage all your clients' SEO + AI visibility in one place"
- Single CTA: "Run a free audit"
- Designed for influencer referral traffic — makes the influencer look credible

---

## Prioritized Build Order (Solo AI-Assisted Dev)

1. **Agency dashboard** — bird's-eye client health view (Week 1–2)
2. **Free tier tightening** — reduce issues to 2, remove PDF, sharpen Starter upgrade CTA (Week 2)
3. **Stripe plan alignment** — update plan definitions to match $59/$149/$349 pricing table (Week 2–3)
4. **Credit alerts** — 50/75/90/100% notifications via email + in-app (Week 3–4)
5. **Credit top-up flow** — one-time purchase starting at $10 (Week 4)
6. **Agency landing page** — influencer referral destination (Week 4–5)
7. **Affiliate tracking system** — referral codes, commission ledger, payout statements (Week 5–7)
8. **Scheduled audit UI** — surface `WorkspaceAuditSchedule` prominently in dashboard (Week 6–7)
9. **Score delta / progress timeline** — retention-driving history view (Week 7–9)
10. **Real AEO engine queries** — ChatGPT/Gemini/Perplexity direct queries for Authority tier (Month 3+)

---

## Critical Files

| Feature | File |
|---------|------|
| Plan/billing tiers | `apps/leads/billing.py` (AUDIT_RESULT_PROFILES, lines 75–146) |
| Free audit gating | `apps/tools/views.py` (AuditResultDetailView, lines 281–402) |
| Credit ledger | `apps/leads/models.py` (WorkspaceCreditLedger) |
| Scheduled audits | `apps/leads/models.py` (WorkspaceAuditSchedule) |
| AEO pipeline | `apps/aeo/services.py` |
| SEO intelligence | `apps/seo/intelligence.py`, `apps/seo/services.py` |
| Email tasks | `apps/tools/tasks.py` (send_audit_report_email_task) |
| Stripe webhooks | `apps/tools/billing_views.py` (StripeWebhookView) |
| Shared links | `apps/tools/models.py` (SharedAuditLink, SEOShareLink) |
| Dashboard | `apps/tools/views.py` (WorkspaceDashboardView) |
| Templates | `templates/tools/`, `templates/leads/` |
