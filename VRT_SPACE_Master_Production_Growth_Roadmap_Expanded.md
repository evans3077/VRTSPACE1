# VRT SPACE — Production, Growth & Scale Roadmap

**Prepared:** August 2026  
**Project:** `evans3077/VRTSPACE1`  
**Live application:** `https://vrtspaceagency.onrender.com`  
**Purpose:** Master roadmap for turning the existing VRT SPACE product into a trustworthy, commercially ready, scalable SaaS and then building the acquisition engine required for sustained growth.

---

## 0. How to use this document

This is the **master implementation roadmap**, not one coding task.

Each phase can later be expanded into individual coding prompts, engineering tickets, QA plans, marketing briefs, or launch checklists.

### Source hierarchy

1. **Current repository (`main`)** — source of truth for what is actually implemented.
2. **VRT SPACE Remediation & Customer Acquisition Strategy** — source of truth for audited gaps and approved growth direction.
3. **Claude project conversation** — source of truth for reasoning, decisions, assumptions and evolution.
4. **This roadmap** — organized execution plan derived from the above.

If this document conflicts with the current repository, re-inspect the relevant code before implementing.

> **Important:** The August 2026 audit is a snapshot. Re-verify paths and behavior against current `main` before generating a specific coding prompt.

---

# 1. Product North Star

VRT SPACE should not be positioned as merely another SEO audit tool.

The product direction is:

> **VRT SPACE is an SEO + AI visibility operating platform that helps businesses and agencies understand how they appear across traditional search and AI engines, identify visibility gaps, execute improvements, and measure whether visibility actually improves.**

The core product loop is:

```text
Discover
   ↓
Audit
   ↓
Understand
   ↓
Prioritize
   ↓
Execute
   ↓
Monitor
   ↓
Prove improvement
   ↓
Retain / Expand
   ↓
Refer
```

The commercial flywheel is:

```text
Free Audit
   ↓
Qualified Lead
   ↓
Workspace
   ↓
Paid Subscription
   ↓
More Sites / Prompts / Credits
   ↓
Recurring Monitoring
   ↓
Measurable Improvement
   ↓
Client Reporting
   ↓
Agency / Partner Expansion
   ↓
Referral
   ↓
More Customers
```

The project therefore has two connected systems:

- **Product:** SEO + AEO/AI visibility + execution + monitoring + reporting
- **Growth:** Organic + Free Audit + Curated Partners + Open Affiliates + Paid Acquisition

Marketing must amplify a product that delivers value; it must not be used to hide product weaknesses.

---

# 2. Current Product Foundation

The existing product is substantially built.

The August audit confirmed that the following should **not** be unnecessarily rebuilt:

- `robots.txt`
- `sitemap.xml`
- `llms.txt`
- Stripe webhook signature verification
- security headers
- secrets hygiene
- custom error pages
- Stripe Connect Express affiliate payouts
- 30-day affiliate payout hold
- fraud-flag scaffolding
- idempotent commission ledger
- broad meta-description coverage

The commercial foundation includes:

- Free audit funnel
- Free / Starter / Growth / Authority plans
- credit and feature gating
- SEO functionality
- AEO/AI visibility functionality
- competitor intelligence
- content functionality
- workspace functionality
- affiliate infrastructure
- Stripe subscriptions
- Stripe Connect payouts
- client/stakeholder functionality
- reporting/sharing infrastructure

### Operating rule

> **Preserve good foundations. Harden them. Do not rewrite working systems merely because a cleaner implementation is possible.**

---

# 3. Readiness Gates

VRT SPACE should pass through three readiness gates.

## Gate A — Safe to Sell

Required:

- legal/trust pages
- cookie consent
- honest AEO data disclosure
- functioning unsubscribe/preferences
- Stripe lifecycle handling
- reliable subscription state
- billing tests
- affiliate commission tests
- rate limiting
- admin hardening
- production logging
- CI compatibility
- Redis/background-job verification
- no known critical security or payment-integrity defects

## Gate B — Ready to Scale

Required:

- reliable onboarding
- strong free-audit conversion
- reliable AEO live data
- recurring monitoring
- agency/client workflows
- Partner system
- Affiliate system
- attribution integrity
- reporting
- customer support processes
- analytics instrumentation
- churn/retention visibility
- acquisition-channel measurement

## Gate C — Ready to Scale Aggressively

Required:

- repeatable acquisition
- known CAC
- known conversion rates
- acceptable payback period
- healthy retention
- measurable expansion revenue
- reliable referral engine
- scalable infrastructure
- sales/partner operations
- clear positioning
- proven customer outcomes

**Do not move aggressively into Gate C while Gate A remains incomplete.**

---

# PHASE 1 — TRUST, LEGAL & PRODUCTION HARDENING

## Objective

Make VRT SPACE trustworthy enough to expose to serious users, partners and paid traffic.

This phase has priority over growth campaigns.

---

## 1.1 Privacy Policy

The audited free-audit page links to `/privacy/`, but no corresponding route existed.

### Implement

1. Dedicated view.
2. Dedicated template.
3. URL.
4. Correct every existing privacy link.
5. Check footer and free-audit links.
6. Add appropriate title/meta description.
7. Ensure mobile usability.
8. Ensure content reflects actual data collection and integrations.

### Acceptance criteria

- `/privacy/` returns HTTP 200.
- No privacy link leads to 404.
- Content accurately describes actual VRT SPACE data handling.
- No fictional integrations are claimed.

---

## 1.2 Terms of Service

Implement `/terms/` using the same standard.

Cover, where applicable:

- accounts
- subscriptions
- payments
- cancellations
- credits
- usage limits
- acceptable use
- third-party integrations
- AI-generated/AI-derived results
- simulated/sample results
- reports
- affiliate/partner terms
- intellectual property
- disclaimers
- limitation of liability
- termination

Where professional legal review is required, mark the section for review rather than inventing legal certainty.

---

## 1.3 Cookie Consent

### Implement

1. Identify actual cookies/trackers.
2. Separate necessary from optional tracking.
3. Do not load optional tracking before required consent.
4. Persist consent.
5. Allow consent changes/revocation.
6. Do not break essential application functionality.
7. Explain the mechanism in the privacy policy.

### Acceptance criteria

- Consent persists.
- Required application cookies work.
- Optional tracking respects consent.
- Banner is responsive and accessible.

---

## 1.4 AEO Data Disclosure

This is a critical credibility requirement.

Every AEO result must have a clear provenance state:

- **Live**
- **Derived**
- **Simulated / Sample**

### Rules

- Live API data → clearly identified as live.
- Derived calculations → clearly identified as derived.
- Simulator/fallback data → clearly identified as simulated/sample.
- Never silently mix simulated and live results.
- Reports, exports and shared views preserve the disclosure.

### Launch rule

If live AEO is the commercial promise, either live integrations must be operational or simulated output must be impossible to mistake for production intelligence.

---

## 1.5 Email Preferences and Unsubscribe

Replace the digest unsubscribe stub with a real preference system.

Minimum capabilities:

- unsubscribe from weekly digest
- manage email categories
- preserve required transactional email
- confirm changes
- secure preference mechanism

A user must be able to unsubscribe without contacting support.

---

## 1.6 Security Hardening

### Rate limiting

Protect public/high-cost endpoints including:

- free audit
- AEO lookup
- expensive AI calls
- authentication-sensitive endpoints
- referral/attribution endpoints where appropriate

Account for:

- IP
- authenticated user
- workspace
- endpoint
- cost
- burst behavior

### Admin

Evaluate:

- changing `/admin/`
- IP restriction where practical
- MFA
- strong staff-account controls
- session controls
- audit logging
- least-privilege staff permissions

---

## 1.7 Logging and Monitoring

Replace application `print()` statements with structured logging.

Use appropriate levels:

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

Never log:

- API keys
- passwords
- tokens
- authorization headers
- payment credentials
- unnecessary personal data

Integrate meaningful failures with existing monitoring/error reporting.

---

## 1.8 Redis and Background Jobs

Verify production infrastructure.

Confirm:

- `REDIS_URL`
- Render configuration
- worker configuration
- Celery if enabled
- scheduled jobs
- weekly digests
- recurring audits
- cache behavior
- retries
- task-failure visibility

Do not silently rely on per-process cache behavior when multiple workers are running.

---

## 1.9 CI

Align CI with the actual supported Django/Python versions.

The audit identified a Python 3.7/3.8/3.9 matrix while the project uses Django 5.2.

CI should cover:

- installation
- migrations/checks
- unit tests
- billing tests
- affiliate tests
- relevant integration tests
- lint/static checks where configured

### Exit condition

A normal pull request produces a trustworthy green build.

---

# PHASE 2 — BILLING, STRIPE & MONEY INTEGRITY

## Objective

Make subscription and commission state authoritative and resilient.

Complete this before scaling Partners/Affiliates.

---

## 2.1 Stripe Event Coverage

The audited integration handles:

- `checkout.session.completed`
- `invoice.payment_succeeded`

Add appropriate handling for:

### `invoice.payment_failed`

- mark subscription appropriately
- record failure state
- stop inappropriate commission accrual
- initiate dunning/recovery if configured
- preserve audit trail

### `customer.subscription.updated`

- synchronize plan
- synchronize status
- handle upgrades
- handle downgrades
- handle recovery

### `customer.subscription.deleted`

- mark subscription cancelled
- stop future recurring commission generation
- preserve historical commissions
- preserve attribution history

---

## 2.2 Stripe State Model

Define a clear mapping between Stripe state and VRT SPACE state.

Example:

```text
Checkout
  ↓
Active
  ↓
Past Due
  ├── Payment succeeds → Active
  └── Subscription cancelled → Cancelled
```

Every transition must be idempotent.

---

## 2.3 Webhook Security and Idempotency

Preserve the existing signature verification.

For every important webhook:

- verify signature
- validate event type
- identify event ID
- process idempotently
- record processing state where appropriate
- safely retry
- avoid duplicate commissions
- avoid duplicate state transitions

---

## 2.4 Stripe SDK Decision

The current system uses hand-rolled Stripe HTTP/signature logic.

Do not rewrite automatically.

Evaluate:

- correctness
- maintenance burden
- number of Stripe endpoints
- error handling
- retry behavior
- future complexity

If migration is justified, treat it as a separate refactor with tests.

---

## 2.5 Billing Test Matrix

Test:

- first subscription
- recurring payment
- failed payment
- recovery
- upgrade
- downgrade
- cancellation
- webhook replay
- duplicate webhook
- invalid signature
- missing metadata
- unknown plan
- missing user
- commission with no referral
- rejected fraud flag
- first-payment commission
- recurring commission

Money-moving code receives higher test priority than cosmetic code.

---

# PHASE 3 — PARTNER & AFFILIATE GROWTH INFRASTRUCTURE

## Objective

Turn the existing affiliate foundation into the proposed two-program referral system without damaging the proven payout architecture.

---

## 3.1 Preserve Existing Mechanics

Do not rebuild:

- Stripe Connect onboarding
- Stripe Connect transfers
- 30-day payout hold
- fraud flags
- idempotent commission ledger
- payment signal architecture
- commission notifications

Plug the new business rules into these systems.

---

## 3.2 Program Types

Introduce:

```text
PARTNER
AFFILIATE
```

### Partner

Curated, invited, vetted and relationship-driven.

### Affiliate

Open, self-service and low-friction.

---

## 3.3 Partner Commission Tiers

Implement the approved structure:

| Lifetime paying customers referred | First payment | Recurring |
|---|---:|---:|
| 0–9 | 25% | 15% |
| 10–24 | 30% | 18% |
| 25–49 | 35% | 20% |
| 50+ | 40% | 22% + Founding Partner status |

Founding Partners receive the approved launch-window bonus where applicable.

### Critical rule

Commission rates must be calculated centrally.

Use one authoritative function such as:

```python
get_commission_rate(affiliate, kind)
```

Do not scatter tier logic across the application.

---

## 3.4 Founding Partner Bonus

Store the bonus explicitly.

Do not infer it from signup date.

This allows:

- auditing
- correction
- historical preservation
- transparent calculations

---

## 3.5 Open Affiliate Program

Implement:

- self-service application
- simple approval flow
- 20% first-payment commission
- 10% recurring commission
- 90-day last-click attribution
- 30-day payout hold
- milestone bonuses

Milestones:

- 5 paying referrals → $150
- 25 paying referrals → $500

Ensure a milestone cannot be paid twice.

---

## 3.6 Affiliate Application Routing

Support requested program:

- Partner
- Affiliate

The admin/review flow should make approval/rejection/routing obvious.

---

## 3.7 Referral Attribution

Implement and test:

- 90-day attribution
- last-click
- cookie/session persistence
- authenticated-user association
- attribution locking after first payment where appropriate
- fraud checks
- same-domain detection
- same-IP detection
- suspicious behavior handling

Document edge cases.

---

## 3.8 Commission Integrity

Never generate recurring commission for:

- failed invoices
- cancelled subscriptions
- rejected fraud
- duplicate events
- transactions excluded by refund/chargeback policy

Define refund/chargeback behavior before partner volume becomes material.

---

## 3.9 Partner Dashboard

Expose:

- clicks
- signups
- qualified referrals
- paying referrals
- conversion rate
- first-payment earnings
- recurring earnings
- pending commissions
- released commissions
- next payout
- current tier
- referrals to next tier
- milestone progress

Avoid unnecessary customer PII.

---

# PHASE 4 — CORE PRODUCT ACTIVATION

## Objective

Make the existing product easier to understand and harder to abandon.

Core loop:

```text
Audit
 ↓
Insight
 ↓
Priority
 ↓
Action
 ↓
Tracking
 ↓
Improvement
```

---

## 4.1 Free Audit

The free audit is the front door to VRT SPACE.

It should answer:

1. What is wrong?
2. Why does it matter?
3. How serious is it?
4. How does the business compare?
5. What should be fixed first?
6. What can VRT SPACE do next?

Avoid dumping raw technical data on the user.

---

## 4.2 Audit-to-Workspace Transition

Preferred flow:

```text
Free Audit
 ↓
Result
 ↓
Create Workspace
 ↓
Save Site
 ↓
Unlock deeper SEO/AEO intelligence
 ↓
Track
```

Preserve audit context and avoid asking for duplicate information.

---

## 4.3 Activation Metric

Define a measurable activation event.

A candidate:

> User completes an audit, creates/saves a workspace, and performs a second meaningful product action.

Track:

- audit started
- audit completed
- account created
- workspace created
- site added
- AEO run
- SEO run
- prompt tracked
- recommendation viewed
- action executed
- subscription started

Validate the final activation definition against actual customer behavior.

---

# PHASE 5 — AEO / AI VISIBILITY TRUST & PRODUCT DEPTH

## Objective

Make AI visibility the category-defining capability of VRT SPACE.

Prioritize accuracy and trust over feature count.

---

## 5.1 Result Provenance

Every result must have a reliable provenance state.

Preserve that state in:

- dashboard
- reports
- exports
- shared views

---

## 5.2 Prompt Tracking

Track meaningful customer questions:

- prompt
- intent
- engine
- run date
- visibility
- citation
- position where available
- competitors
- evidence where available
- change over time

---

## 5.3 Competitor Intelligence

Minimize:

- irrelevant domains
- social platforms
- unrelated businesses
- false positives

Allow users to correct/refine competitors.

---

## 5.4 Visibility Over Time

Move beyond one-time scores.

```text
Baseline
 ↓
Run
 ↓
Improvement
 ↓
Competitor movement
 ↓
Citation gains/losses
 ↓
Trend
```

The goal is recurring monitoring, not a one-time audit.

---

## 5.5 AI Recommendations

Recommendations should be:

- evidence-backed
- prioritized
- actionable
- linked to relevant findings
- clear about confidence
- traceable to source data

Avoid generic advice.

---

# PHASE 6 — AGENCY PRODUCTIZATION

## Objective

Make VRT SPACE an operating system for agencies managing SEO + AI visibility across clients.

---

## 6.1 Multi-Client Workspace

Support:

- multiple client sites
- client separation
- internal team access
- client access
- client status
- health indicators
- last audit
- trend
- alerts

---

## 6.2 Client Sharing

Clients should see useful information without gaining unnecessary access.

Minimum:

- score
- trend
- major findings
- recommendations
- progress
- reports

---

## 6.3 Reporting

Reports should answer:

- Where were we?
- Where are we now?
- What changed?
- What did we do?
- What should happen next?

Reports must work for marketers, agency owners, executives and clients.

---

## 6.4 White-Label / Agency Branding

Potential capabilities:

- agency logo
- agency colors
- custom report branding
- custom sender identity
- client-facing URLs
- white-label exports

Validate agency demand before building the complete enterprise version.

---

## 6.5 WordPress / Execution Loop

Treat publishing as part of the execution loop:

```text
Recommendation
 ↓
Editorial Task
 ↓
Draft
 ↓
WordPress
 ↓
Publish
 ↓
Re-audit
 ↓
Measure
```

Reduce the distance between finding a problem and fixing it.

---

# PHASE 7 — SEO, CONTENT & ORGANIC ACQUISITION

## Objective

Build an organic acquisition engine that compounds.

The existing strategy identifies eight industry landing pages as the near-term wedge:

- Agencies
- B2B SaaS
- Fintech
- Ecommerce
- Healthcare
- Real Estate
- Legal
- Local Service Businesses

---

## 7.1 Industry Pages

Each page should have:

- specific search intent
- unique value
- relevant examples
- internal links
- clear CTA
- free-audit CTA
- AEO relevance
- useful FAQ content
- appropriate structured data

Avoid thin programmatic SEO.

---

## 7.2 Content Pillars

### SEO

Technical SEO, content, rankings, competitors and performance.

### AEO / AI Visibility

AI search, citations, prompts, entities, AI visibility and answer engine optimization.

### Agency Operations

Client reporting, SEO workflows, AI visibility and retention.

### Execution

How to fix visibility problems.

### Measurement

How to prove SEO/AEO improvement.

### Commercial Intelligence

Connecting visibility to business outcomes.

---

## 7.3 Free Tools

Potential acquisition tools:

- AI visibility checker
- SEO quick audit
- robots.txt checker
- sitemap checker
- schema checker
- AI citation checker

Each tool must have a natural path into the paid product.

---

## 7.4 Internal Linking

Build deliberate paths:

```text
Blog
 ↓
Industry Page
 ↓
Free Audit
 ↓
Audit Result
 ↓
Product
```

and:

```text
AEO Guide
 ↓
AEO Tool
 ↓
AEO Audit
 ↓
Workspace
```

---

# PHASE 8 — CASE STUDIES & PROOF

## Objective

Replace claims with evidence.

The current fictional case studies are placeholders and must not be presented as real customer results.

Before serious growth:

1. Acquire real customers.
2. Measure before/after.
3. Obtain permission.
4. Produce real case studies.
5. Replace placeholders.

Case studies should show:

- starting point
- problem
- intervention
- timeline
- measurable change
- business relevance

Only publish numbers that can be substantiated.

---

# PHASE 9 — PARTNER LAUNCH

## Objective

Make curated Partners the first serious referral engine.

The strategy proposes an initial group of roughly 30–50 reputable marketers/partners.

Prioritize:

- SEO consultants
- agencies
- digital marketers
- web developers
- growth consultants
- content specialists
- AI/search consultants

Measure:

- approved
- activated
- first referral
- first paying referral
- 5 referrals
- 10 referrals
- 25 referrals
- retained referred customers

An inactive partner is not a growth channel.

---

# PHASE 10 — OPEN AFFILIATE LAUNCH

Launch the open program after the core Partner engine and product economics are validated.

The open program should be:

- simple
- transparent
- self-service
- easy to explain
- easy to track

Use the approved:

**20% first payment / 10% recurring**

structure and milestone bonuses.

The open program must not become a support-heavy manual operation.

---

# PHASE 11 — PAID ACQUISITION

## Objective

Scale channels that have demonstrated conversion.

Paid acquisition should not be the first growth engine.

Before serious spend, know:

- visitor → audit conversion
- audit → signup
- signup → activation
- activation → paid
- ARPU
- churn
- LTV
- CAC
- CAC payback
- refund rate

The strategy recommends a CAC ceiling around **$500–$550** and warns against blindly applying a percentage-of-profit rule.

### Potential channels

- high-intent search
- LinkedIn
- Meta where appropriate
- retargeting
- other channels supported by measured economics

Every channel needs kill/scale rules.

Stop or reduce a channel when:

- CAC exceeds ceiling
- conversion quality is poor
- retention is poor
- refund/chargeback rate is high
- payback becomes unacceptable

---

# PHASE 12 — INTERNATIONALIZATION

## Objective

Prepare VRT SPACE for genuine international growth.

The audited strategy recommends real Django localization rather than a client-side translation widget.

Potential structure:

```text
/en/
/es/
/fr/
```

Localized pages should have:

- localized content
- canonical
- `hreflang`
- localized metadata
- localized structured data where appropriate
- correct internal linking

Only implement when demand justifies it.

---

# PHASE 13 — DOMAIN & BRAND CONSISTENCY

Resolve inconsistent contact emails when the final production domain is selected.

The canonical identity should be consistent across:

- website
- email
- Stripe
- legal documents
- `llms.txt`
- social profiles
- documentation
- support
- partner communications

Do not scale paid campaigns while core brand identity is inconsistent.

---

# PHASE 14 — ANALYTICS & BUSINESS INTELLIGENCE

## Acquisition events

Track:

- landing page visit
- industry page visit
- audit started
- audit completed
- signup
- workspace created
- first AEO run
- first SEO run
- first recommendation
- first action
- subscription
- upgrade
- cancellation
- referral click
- referral signup
- referral payment

## Product metrics

Track:

- activation
- WAU/MAU
- audits per user
- prompts per workspace
- tracked domains
- recommendations executed
- recurring audits
- reports
- WordPress publishing
- credits consumed
- credit top-ups

## Revenue metrics

Track:

- MRR
- ARR
- new MRR
- expansion MRR
- contraction MRR
- churned MRR
- GRR
- NRR
- ARPU
- plan distribution
- credit revenue
- commission expense
- refunds
- chargebacks

## Acquisition metrics

By channel:

- traffic
- leads
- activated users
- paying users
- CAC
- conversion
- payback
- retention
- LTV

Never evaluate channels using traffic alone.

---

# PHASE 15 — RETENTION & EXPANSION

## Objective

Turn VRT SPACE from an audit product into a recurring operating system.

Core loop:

```text
Monitor
 ↓
Detect change
 ↓
Recommend action
 ↓
Execute
 ↓
Re-run
 ↓
Show improvement
 ↓
Report
 ↓
Monitor again
```

---

## 15.1 Monthly Value Moment

Customers should have a reason to return for:

- new AI visibility results
- competitor movement
- citations
- SEO changes
- recommendations
- completed actions
- score improvement
- scheduled reports

---

## 15.2 Expansion

Natural expansion triggers:

- more websites
- more prompts
- more users
- more audits
- recurring monitoring
- more content
- more publishing
- additional credits
- more agency clients
- reporting needs

Upgrade prompts should be based on actual usage and value.

---

# PHASE 16 — ENTERPRISE / HIGH-VALUE ACCOUNTS

Potential capabilities:

- higher limits
- multiple teams
- multi-market tracking
- API access
- advanced reporting
- SSO
- audit logs
- custom retention
- dedicated support
- custom integrations
- security/procurement documentation

Build against demonstrated demand rather than speculation.

---

# PHASE 17 — CONTINUOUS SECURITY PROGRAM

Security does not end after launch.

Maintain ongoing review of:

### Authentication

- sessions
- password policy
- recovery
- MFA where appropriate
- staff security

### Authorization

- workspace isolation
- role permissions
- client access
- partner access
- admin access

### Data

- encryption in transit
- safe storage
- minimal sensitive-data collection
- retention
- deletion

### Integrations

- Stripe secrets
- AI provider keys
- search APIs
- WordPress credentials
- OAuth/application passwords

### Abuse

- rate limiting
- scraping
- API abuse
- prompt abuse
- credit abuse
- referral fraud
- payment fraud

### Monitoring

- authentication anomalies
- billing anomalies
- API spikes
- error spikes
- abuse signals

---

# PHASE 18 — RELEASE MANAGEMENT

Every meaningful feature should follow:

```text
Plan
 ↓
Inspect current code
 ↓
Implement
 ↓
Unit Tests
 ↓
Integration Tests
 ↓
Security Review
 ↓
Manual QA
 ↓
Production Deploy
 ↓
Smoke Test
 ↓
Monitor
 ↓
Document
```

For money-moving features:

```text
Implementation
 ↓
Stripe Test Mode
 ↓
Webhook Replay
 ↓
Idempotency Tests
 ↓
Commission Reconciliation
 ↓
Production Rollout
 ↓
Monitor Ledger
```

Do not combine a major billing rewrite with an unrelated major redesign.

---

# PHASE 19 — MARKETING SYSTEM

## Positioning

Core positioning:

> **Measure and improve how your business appears in search and AI.**

Agency positioning:

> **Manage SEO and AI visibility for every client from one workspace.**

Avoid reducing VRT SPACE to:

- an SEO audit
- an AI chatbot
- an AI content generator
- another dashboard

The differentiator is:

**visibility → intelligence → action → measurement**

---

## Marketing funnel

```text
Content / Search / Partner / Paid
              ↓
        Free Audit
              ↓
       Audit Result
              ↓
          Signup
              ↓
         Activation
              ↓
       Paid Workspace
              ↓
      Expansion / Retention
              ↓
          Referral
```

Every stage needs a measurable owner metric.

---

# PHASE 20A — MONETIZATION, CREDIT ECONOMICS & REFERRAL COMMISSION GOVERNANCE

## Objective

Design VRT SPACE pricing so that larger credit purchases create value without destroying margin, annual subscriptions improve cash flow and retention, and Partner/Affiliate commissions remain sustainable. Final pricing must be based on measured unit economics before launch.

## 20A.1 Subscription Pricing

Support monthly and annual subscriptions. The annual option may target **up to 45% savings**, but the exact annual price must be calculated from the genuine monthly-equivalent price.

Annual billing can improve upfront cash flow, retention, CAC payback, predictability and LTV. Annual subscription revenue remains commissionable under the applicable referral rules.

## 20A.2 Credit Top-Up Model

Use larger-purchase bonus credits to create a clear value incentive. Initial examples:

| Customer pays | Credits received | Bonus |
|---:|---:|---:|
| $10 | 10 | 0% |
| $20 | 22 | +10% |
| $30 | 33 | +10% |
| $50 | 56 | +12% |
| $100 | 115 | +15% |
| $200 | 240 | +20% |

These are **illustrative starting points, not final pricing**. Final packages must be determined from actual API, AI, infrastructure and support costs.

Commercial principle:

> The larger the legitimate commitment, the better the effective value — without allowing the bonus to destroy gross margin.

## 20A.3 Credit Unit Economics — Mandatory Before Launch

Before production pricing is finalized, calculate the real cost of every important credit-consuming operation. A working target is that a 1-credit run should ideally cost materially less than $1 in direct variable cost; the current planning target is **below $0.20 per credit/run**, subject to actual measurement.

For every operation, calculate:

- AI provider cost
- search/API cost
- crawling/proxy/browser cost where applicable
- storage and background-job cost where material
- bandwidth/third-party service cost
- retries and failed attempts
- average and worst-case usage

Required model:

```text
Credit Value
    ↓
Actual Variable Cost
    ↓
Gross Contribution
    ↓
Gross Margin %
```

If 1 credit is valued at approximately $1 and costs less than $0.20 to fulfil, the illustrative contribution is approximately $0.80 before other business costs. This is a target model, not an assumed final margin.

## 20A.4 Cost by Operation

Create a central cost model before launch:

| Operation | Credits | Variable cost | Maximum safe frequency |
|---|---:|---:|---:|
| SEO check | TBD | TBD | TBD |
| AEO prompt run | TBD | TBD | TBD |
| AI analysis | TBD | TBD | TBD |
| Competitor analysis | TBD | TBD | TBD |
| Content analysis | TBD | TBD | TBD |
| Full audit | TBD | TBD | TBD |
| Report generation | TBD | TBD | TBD |

The objective is to know exactly what VRT SPACE spends when a customer spends one credit.

## 20A.5 Credit Economics Rules

Define explicitly:

- purchased credits
- bonus credits
- promotional credits
- subscription-included credits
- consumption order
- rollover/expiration
- refunds and chargebacks
- cancellation and plan changes
- abuse and excessive usage
- failed operations

Do not leave credit-consumption priority ambiguous.

## 20A.6 Prevent Credit Arbitrage

Test the smallest and largest packages, maximum bonus package, heavy AEO/AI usage, retries, bulk operations, simultaneous jobs and abnormal API usage. The maximum theoretical variable cost of a package must remain comfortably below the amount paid.

## 20A.7 Commissionable vs Non-Commissionable Revenue

### Commissionable

Eligible subscription revenue:

- monthly subscriptions
- annual subscriptions
- eligible subscription upgrades
- eligible recurring subscription payments

### Non-Commissionable

Credit purchases/top-ups must **not** generate Partner or Affiliate commissions. Neither should:

- welcome/promotional/referral credits
- bonus credits
- refunds
- chargebacks
- fraudulent/reversed transactions
- future non-subscription transactions unless explicitly classified as commissionable

Core principle:

> Partners and Affiliates are rewarded for acquiring and retaining subscription customers, not for generating arbitrary transaction volume.

## 20A.8 Why Credit Purchases Are Non-Commissionable

This protects VRT SPACE from creating an uncontrolled acquisition cost on usage revenue. A customer may generate eligible subscription commission for a Partner and later purchase $500 in credits; the credit purchase itself generates no additional referral commission.

## 20A.9 Partner Dashboard Presentation

The dashboard should report **Subscription Earnings**, rather than implying that every transaction generates commission. Credit purchases do not need to appear as earnings.

Recommended disclosure:

> Subscription earnings are calculated from eligible subscription payments attributable to your referrals. Credit purchases, promotional credits, refunds, chargebacks and other non-subscription transactions do not generate referral commissions. See Partner Terms for full details.

Do **not** intentionally conceal the exclusion from Partners. The dashboard can simply report the category on which they earn.

## 20A.10 Partner Terms

Partner and Affiliate Terms must explicitly define commissionable and non-commissionable revenue, including credit purchases/top-ups, promotional/bonus credits, refunds, chargebacks and fraudulent/reversed transactions. Also define attribution, qualifying events, payment holds, cancellation, refunds, chargebacks and fraud handling.

## 20A.11 Referral Commission Accounting

The commission engine must classify revenue explicitly before calculating commission:

```text
Payment Received
       ↓
Classify Revenue
       ↓
Subscription / Credit / Promotion / Refund / Chargeback / Other
       ↓
Commission Eligibility
       ↓
Commission Ledger
       ↓
30-Day Hold
       ↓
Fraud / Refund Check
       ↓
Release
```

Commissionability must never be inferred from payment amount alone.

## 20A.12 Data Model Concept

Where practical, store an explicit transaction/revenue classification such as:

```text
SUBSCRIPTION
CREDIT_PURCHASE
PROMOTIONAL_CREDIT
REFUND
CHARGEBACK
OTHER
```

This makes reconciliation, auditing and future pricing changes safer.

## 20A.13 Annual Subscription + Referral Economics

Model annual subscriptions together with payment fees, variable service cost, Partner/Affiliate commission, support cost and expected retention. Do not evaluate a 45% annual discount in isolation.

## 20A.14 Pricing Experiments

Measure:

- average top-up size
- top-up conversion
- credit utilization
- effective revenue per credit
- variable cost per credit
- gross margin
- annual-plan adoption
- annual churn
- upgrades
- refunds
- referred-customer behavior

Optimize for contribution margin, retention, customer value and sustainable acquisition rather than immediate revenue alone.

## 20A.15 Monetization Safety Gate

Before launch, VRT SPACE must be able to answer:

1. What does one credit cost us?
2. What is average and worst-case cost?
3. What is gross margin?
4. What happens when bonus credits are used heavily?
5. What happens on refund or chargeback?
6. What does a Partner earn from an annual subscription?
7. What does a Partner earn from a credit purchase?
8. Can discount + commission + usage make a customer unprofitable?
9. Can a customer or Partner exploit the pricing model?

Do not enter aggressive paid acquisition until these questions have defensible answers.

# PHASE 20 — THREE-YEAR SCALE STRATEGY

The long-term operating target is:

> **Build toward $1M MRR within approximately 36 months while maintaining healthy retention and sustainable acquisition economics.**

This is an ambitious target, not a guaranteed forecast.

## Year 1 — Product-Market Fit

Focus:

- production hardening
- free audit
- onboarding
- AEO accuracy
- real case studies
- organic content
- first Partners
- early agencies
- retention
- analytics

Question:

> Can VRT SPACE reliably turn strangers into paying customers who remain customers?

## Year 2 — Distribution

Focus:

- Partner program
- Open Affiliates
- agency sales
- SEO/content
- outbound
- paid acquisition
- international testing
- agency functionality
- reporting
- customer success

## Year 3 — Scale

Focus:

- partner network
- affiliate network
- agency expansion
- higher-value accounts
- international markets
- enterprise
- stronger sales
- automation
- infrastructure
- customer success
- expansion revenue

The target is not simply `$1M MRR`.

It is:

> **$1M MRR with healthy retention, defensible acquisition economics and a product customers depend on.**

---

# PHASE 21 — FINANCIAL GOVERNANCE

Track:

```text
MRR
+
NRR
+
GRR
+
CAC
+
LTV
+
CAC Payback
+
Gross Margin
+
Commission Cost
+
Infrastructure Cost
=
Actual SaaS Health
```

Paid acquisition must be governed by CAC and payback.

Partner commissions are a customer-acquisition expense.

Separate subscription MRR from one-time credit/top-up revenue where appropriate.

Never use one-time revenue to make recurring revenue appear stronger than it is.

---

# PHASE 22 — CUSTOMER SUCCESS

## Onboarding

### First session

- add site
- run audit
- understand score
- identify priorities

### First week

- run AEO
- add tracked prompts
- review competitors
- execute first recommendation

### First month

- review change
- produce report
- identify next actions
- establish recurring monitoring

## Churn prevention

Detect:

- no login
- no new audits
- no prompt tracking
- no action execution
- low credit consumption
- failed payment
- unused seats
- declining usage

Respond with appropriate:

- education
- reminders
- reports
- support
- downgrade/upgrade assistance

Do not spam inactive users.

---

# PHASE 23 — WHAT NOT TO BUILD

Resist feature sprawl.

Before adding a feature, ask:

1. Does it improve acquisition?
2. Does it improve activation?
3. Does it improve retention?
4. Does it increase expansion revenue?
5. Does it strengthen differentiation?
6. Does it reduce operational cost?
7. Is there evidence customers want it?

If the answer is no, defer it.

---

# PHASE 24 — IMPLEMENTATION PROMPT STANDARD

Every future coding prompt derived from this roadmap should use:

## 1. Context

Explain VRT SPACE, current architecture, relevant module and business reason.

## 2. Objective

State exactly what must change.

## 3. Current State

Identify existing:

- models
- views
- services
- URLs
- templates
- settings
- tests

Do not assume.

## 4. Required Changes

List implementation steps in order.

## 5. Data Model

Define:

- fields
- relationships
- indexes
- constraints
- migrations

## 6. Business Logic

Define exact behavior and edge cases.

## 7. Security

Define:

- authorization
- validation
- rate limiting
- secrets
- sensitive data

## 8. Payments

When relevant:

- Stripe events
- idempotency
- ledger behavior
- refunds
- failed payments
- payout rules

## 9. UI/UX

Define:

- journey
- states
- errors
- loading
- empty states
- mobile behavior
- accessibility

## 10. SEO/AEO

For public-facing work:

- title
- description
- canonical
- schema
- indexing
- internal links
- AI disclosure

## 11. Tests

Require:

- happy path
- edge cases
- failure cases
- authorization
- idempotency
- regression coverage

## 12. Acceptance Criteria

Use explicit checkboxes.

## 13. Files to Inspect First

List likely files, but require verification against current `main`.

## 14. Do Not Change

Explicitly protect unrelated systems.

## 15. Output

Require:

- files changed
- migrations
- tests
- deployment considerations
- unresolved risks

---

# PHASE 25 — MASTER EXECUTION ORDER

## Stage 1 — Trust

- Privacy
- Terms
- Cookies
- AEO disclosure
- Email preferences

## Stage 2 — Money Integrity

- Stripe webhook coverage
- subscription state
- payment failure
- cancellation
- upgrade/downgrade
- billing tests

## Stage 3 — Production Reliability

- CI
- Redis
- rate limiting
- admin hardening
- logging
- monitoring

## Stage 4 — Referral Infrastructure

- Partner/Affiliate programs
- tiering
- founding bonus
- milestone bonuses
- attribution
- commission tests

## Stage 5 — Product Activation

- free audit
- onboarding
- audit-to-workspace
- activation analytics
- AEO trust

## Stage 6 — Agency Product

- multi-client
- client sharing
- reporting
- white-label
- execution workflows

## Stage 7 — Proof

- real customers
- real outcomes
- case studies
- testimonials
- measurable improvements

## Stage 8 — Organic Growth

- industry pages
- content
- free tools
- internal linking
- AEO content
- case studies

## Stage 9 — Partner Launch

- recruit
- activate
- measure
- optimize

## Stage 10 — Open Affiliates

- self-service
- tracking
- milestones
- support

## Stage 11 — Paid Acquisition

- only after unit economics are understood
- controlled CAC
- channel testing
- retargeting
- scale winners

## Stage 12 — International

- domain/brand consistency
- i18n
- localized URLs
- hreflang
- localized content

## Stage 13 — Scale

- agency expansion
- enterprise
- higher ARPU
- partner network
- customer success
- infrastructure
- international growth

---

# PHASE 26 — DEFINITION OF DONE

## Customer

A new user can:

1. Discover VRT SPACE.
2. Run a free audit.
3. Understand the result.
4. Create an account.
5. Create a workspace.
6. Run deeper SEO/AEO analysis.
7. Track prompts.
8. Identify competitors.
9. Receive useful recommendations.
10. Execute actions.
11. Monitor progress.
12. Produce a report.
13. Upgrade naturally when value increases.

## Agency

An agency can:

1. Manage multiple clients.
2. Monitor multiple sites.
3. Track AI visibility.
4. Produce client reports.
5. Share client views.
6. Execute improvements.
7. Demonstrate measurable progress.
8. Expand VRT SPACE usage as its client base grows.

## Partner

A Partner can:

1. Join.
2. Refer.
3. See attribution.
4. Earn commissions.
5. Advance tiers.
6. Receive recurring revenue.
7. Monitor performance.
8. Understand how to create more successful referrals.

## VRT SPACE

The company can:

1. Accept payments reliably.
2. Handle payment failure.
3. Handle cancellation.
4. Calculate commissions accurately.
5. Prevent duplicate payouts.
6. Detect referral abuse.
7. Measure acquisition.
8. Measure retention.
9. Measure expansion.
10. Scale infrastructure.
11. Acquire customers through multiple channels.
12. Prove customer outcomes.

---

# Final Operating Principle

The project should now move from:

> **"What else can we build?"**

to:

> **"What is the highest-value constraint preventing VRT SPACE from acquiring, activating, retaining and expanding real customers?"**

Every phase should answer that question.

The product already has a substantial technical foundation.

The transformation is:

```text
Codebase
   ↓
Product
   ↓
Reliable Product
   ↓
Sellable Product
   ↓
Repeatably Acquired Product
   ↓
Retained Product
   ↓
Compounding SaaS Business
```

The durable loop is:

```text
VISIBILITY
    ↓
INSIGHT
    ↓
ACTION
    ↓
MEASUREMENT
    ↓
BUSINESS VALUE
    ↓
RETENTION
    ↓
EXPANSION
    ↓
REFERRAL
    ↓
MORE CUSTOMERS
```

**That loop is the core of VRT SPACE.**


---

# APPENDIX A — AUDIT ADDITIONS & BUILD-READY TECHNICAL SPECS

This appendix incorporates the later audit-pass findings from the original remediation strategy. These items are preserved at implementation-detail level so they can be converted directly into coding-agent prompts.

## A.1 Critical Database Persistence Verification

### Finding

There is an unresolved contradiction in the deployment documentation and repository history around the production database.

The critical risk is that `config/settings.py` may fall back to SQLite when `DATABASE_URL` is absent. On ephemeral hosting storage, that can make the application appear healthy while user signups, audit history and subscription state disappear after redeploy/restart.

### Required immediate check

1. Open Render.
2. Open the production web service.
3. Open Environment.
4. Confirm `DATABASE_URL` exists.
5. Confirm it points to the intended persistent Postgres provider.
6. Confirm the application is actually using Postgres.
7. Confirm migrations are applied.
8. Verify a real record persists across redeploy.

### Required remediation

If the variable is missing:

- provision a persistent Neon or Supabase Postgres database;
- configure `DATABASE_URL`;
- migrate the application;
- redeploy;
- verify persistence;
- update `docs/DEPLOY.md`.

### Acceptance criteria

- Production database is persistent.
- `DATABASE_URL` is explicitly configured.
- No production data depends on ephemeral SQLite storage.
- A test record survives redeploy.
- Deployment documentation matches reality.

---

# APPENDIX B — INFRASTRUCTURE & API COST PLANNING

## B.1 Operating Cost Model

Every paid integration must have a documented cost model before significant scale.

The expanded audit's planning ranges are:

| Scenario | Monthly operating cost |
|---|---:|
| Lean launch | ~$0–15/mo |
| Real launch | ~$60–120/mo |
| At scale | ~$300–800+/mo |

These are planning figures, not guarantees. Actual usage must be measured.

Key cost drivers:

- hosting;
- database;
- Redis/background infrastructure at scale;
- email;
- Sentry;
- SerpAPI;
- Stripe transaction fees.

AI-engine cost should be tracked separately.

---

## B.2 AI Provider Coverage

| Engine | Current state | Direction |
|---|---|---|
| OpenAI / ChatGPT | Real integration | Existing |
| Google Gemini | Real integration | Existing |
| Perplexity | Real integration | Existing |
| Google AI Overviews | Partial through existing SerpAPI parsing | Verify surfaced/scored in UI |
| Google AI Mode | Not covered | Add through SerpAPI |
| Bing Copilot | Stubbed | Add through SerpAPI |
| Claude | Not integrated | New provider + env var |
| Grok | Not integrated | New provider + env var |

Prioritize reliability and customer value before breadth.

---

## B.3 Provider Abstraction

Every AI provider should use a consistent internal contract.

Conceptually:

```python
run_ai_visibility_check(
    engine=...,
    prompt=...,
    context=...,
) -> normalized_result
```

Normalize:

- response text;
- citations;
- cited domains;
- entity/brand mentions;
- position where available;
- token usage where available;
- provider/model;
- timestamp;
- success/failure;
- retry/error metadata.

Keep provider-specific response formats behind the adapter.

---

## B.4 API Cost Instrumentation

For paid AI/search calls, capture where available:

- provider;
- model/engine;
- input tokens;
- output tokens;
- request type;
- workspace/user;
- audit/run ID;
- credit charge;
- failure/retry status.

The required financial chain is:

```text
API Cost
   ↓
Credit Consumption
   ↓
Customer Revenue
   ↓
Gross Contribution
```

The goal is to know which operations are profitable.

---

# APPENDIX C — AI ENGINE COVERAGE ROADMAP

## C.1 Google AI Overviews

Existing code already parses AI Overview-related SerpAPI fields.

Verify:

1. parsed data reaches scoring;
2. scoring reaches the UI;
3. it appears in reports where appropriate;
4. tests cover presence/absence;
5. signals are not double-counted.

This is a verification/completion task, not a new vendor relationship.

## C.2 Google AI Mode

Implement through the existing SerpAPI relationship.

Requirements:

- normalized result;
- citations;
- response text;
- engine metadata;
- error handling;
- cost tracking;
- tests;
- clear UI/source labeling.

## C.3 Bing Copilot

Replace the hardcoded stub with a real SerpAPI-backed provider path where supported.

Capture:

- answer text;
- citations;
- source URLs/domains;
- timestamp;
- failures;
- cost;
- normalized results.

## C.4 Claude

Add a dedicated provider function and environment variable.

Requirements:

- provider adapter;
- key validation;
- normalized response;
- token/cost capture;
- retries/timeouts;
- safe failure;
- rate/cost controls;
- tests.

## C.5 Grok

Follow the same provider abstraction and test standards.

---

# APPENDIX D — AI CONTENT OPTIMIZER PRODUCT STRATEGY

## D.1 Current State

`apps/aeo/content_optimizer.py` intentionally does not call an AI API.

It relies on heuristic analysis such as:

- answer-first patterns;
- fact/number density;
- citation-language detection;
- structural/content signals.

This is useful for a near-zero-marginal-cost free tool, but explains accuracy limits.

## D.2 Tiered Model

### Anonymous/free

Keep the heuristic scorer.

Purpose:

- fast;
- cheap;
- useful;
- teaser-quality;
- acquisition-focused.

### Registered free

Keep the heuristic experience within free-plan limits.

### Paying users

Add an LLM-assisted semantic pass evaluating:

- citation-worthiness;
- factual clarity;
- answer completeness;
- evidence quality;
- entity/context strength;
- semantic relevance;
- usefulness to AI answers.

The paid tier should buy **better intelligence**, not merely more attempts.

---

# APPENDIX E — FREE-TOOL GATEKEEPER SYSTEM

## E.1 Objective

Free tools are acquisition assets, but unlimited anonymous use can create:

- API abuse;
- scraping;
- infrastructure cost;
- repeated audits;
- automated content analysis;
- denial-of-wallet behavior;
- low-quality traffic.

The gatekeeper preserves useful free access while protecting economics.

## E.2 Tiers

### Anonymous

Allow approximately 2–3 free uses per tool.

Track by:

- IP;
- target domain where applicable;
- content hash where a domain is unavailable.

Use a monthly reset rather than a permanent lifetime ban.

### Registered Free

Use the existing VRT SPACE credit system and plan catalogue.

Do not create parallel quota infrastructure unless necessary.

### Paying

Allow usage within plan-appropriate economic limits.

"Unlimited" should not mean economically unlimited when third-party costs are material.

## E.3 Free Audit Gate

The existing audit throttle is short-window anti-spam protection:

- 3 requests / 15 minutes;
- IP-keyed.

That is different from persistent monthly usage.

Use existing `AuditRun.normalized_domain` plus IP.

Conceptually:

```text
Anonymous request
      ↓
IP check
      ↓
Target-domain check
      ↓
Monthly quota
      ↓
Allowed?
  ├── Yes → Run audit
  └── No  → Show upgrade path
```

## E.4 Content Optimizer Gate

Add lightweight tracking based on:

- IP;
- content hash;
- target domain when supplied.

Prefer hashes for repeat-detection rather than storing unnecessary raw content.

## E.5 Gatekeeper UX

Show remaining uses before the wall:

> **2 of 3 free audits remaining this month**

At the wall:

- explain the limit;
- show reset timing;
- give the registration/upgrade path;
- avoid generic error messages.

## E.6 Reusable Quota Policy

Create a reusable quota helper rather than embedding limits in each view.

It should document:

- tier;
- count;
- reset window;
- keying method;
- exemptions;
- failure behavior.

Conceptually:

```python
check_tool_quota(
    tool="free_audit",
    user=request.user,
    ip=client_ip,
    target=normalized_domain,
)
```

Return explicit state such as:

```text
allowed
remaining
reset_at
reason
```

---

# APPENDIX F — COST-AWARE PRODUCT GUARDRAILS

Every expensive operation should define:

1. authentication requirement;
2. quota;
3. credit cost;
4. maximum input;
5. timeout;
6. retry policy;
7. concurrency limit;
8. provider cost;
9. logging/metrics;
10. abuse behavior.

Preferred pattern:

```text
Anonymous
  ↓
Cheap heuristic
  ↓
Free result
  ↓
Register
  ↓
Credits
  ↓
LLM semantic analysis
  ↓
Paid value
```

The free layer proves value; the paid layer provides depth and expensive intelligence.

---

# APPENDIX G — UPDATED BUILD ORDER

## Step 0 — Persistence

Verify the production database and eliminate any possibility of silent SQLite fallback.

## Step 1 — Trust

- Privacy
- Terms
- Cookies
- AEO disclosure
- Email preferences

## Step 2 — Money integrity

- Stripe lifecycle webhooks
- billing state
- commission correctness
- CI compatibility

## Step 3 — Referral infrastructure

- Partner/Affiliate programs
- tiering
- founding bonus
- milestone bonuses
- attribution
- commission tests

## Step 4 — Remaining reliability

- Redis
- rate limiting
- admin hardening
- logging

## Step 5 — SEO/AEO polish

- sitemap `lastmod`
- structured data

## Step 6 — Gatekeeper system

Complete before partner/paid outreach sends meaningful traffic into the free tools.

## Step 7 — AI engine coverage

- verify Google AI Overviews;
- Google AI Mode;
- Bing Copilot.

## Step 8 — Paid intelligence providers

- Claude;
- Grok.

## Step 9 — Content Optimizer semantic upgrade

Introduce the paid-tier semantic pass after cost and gatekeeper controls exist.

## Step 10 — Growth infrastructure

- partner launch;
- open affiliate program;
- analytics;
- paid acquisition tooling.

## Step 11 — Internationalization

Only when the real domain and international demand justify it.

---

# APPENDIX H — PRE-LAUNCH COST & SAFETY CHECK

- [ ] Persistent production Postgres verified.
- [ ] No production dependence on ephemeral SQLite.
- [ ] AI provider keys and limits configured.
- [ ] Cost tracking exists for major paid API operations.
- [ ] Every free expensive tool has a quota.
- [ ] Every paid expensive action has a credit cost.
- [ ] Maximum input sizes enforced.
- [ ] Retry behavior cannot create runaway API spend.
- [ ] Concurrent-job limits defined where needed.
- [ ] Simulated AEO output clearly labeled.
- [ ] Subscription revenue and credit revenue classified separately.
- [ ] Credit purchases are non-commissionable.
- [ ] Partner/Affiliate terms state commission exclusions.
- [ ] Billing and commission tests pass.
- [ ] Real customer case studies replace fictional placeholders before public proof claims.
- [ ] Deployment documentation reflects actual infrastructure.

---

# APPENDIX I — FREE TOOLS AS CONTROLLED ACQUISITION PRODUCTS

Free tools should be treated as **marketing products with economic guardrails**, not unrestricted versions of the paid platform.

The intended funnel is:

```text
Useful Free Tool
      ↓
Trust
      ↓
Insight
      ↓
Registration
      ↓
Paid Intelligence
      ↓
Workspace
      ↓
Recurring Value
```

The free layer should create the belief:

> **"This product understands my problem."**

The paid layer should answer:

> **"Now give me the depth, monitoring and execution capability to solve it."**

The distinction should be commercial, technical and economic — not merely an arbitrary paywall.

---

# APPENDIX J — AUDIT-SOURCED REVISIONS TO EARLIER ASSUMPTIONS

The expanded audit corrected several earlier assumptions:

- Google AI Overviews are already partially wired through the existing SerpAPI integration.
- The free-audit tool already has a 3 requests / 15 minutes IP throttle.
- The AI Content Optimizer's inaccuracy is caused by intentional heuristic-only scoring, not missing API keys.
- Bing Copilot and Google AI Mode are buildable through the existing SerpAPI relationship.
- Claude and Grok require genuinely new model integrations.
- The free tools lack persistent domain/tier-aware quota controls and therefore need the gatekeeper system.

These corrections should supersede older statements in earlier audit drafts.



---

## Roadmap Revision Note — Expanded Audit Integration

This expanded roadmap incorporates the newly uploaded remediation strategy sections covering the critical database-persistence check, infrastructure/API cost planning, AI-engine coverage, Content Optimizer tiering, free-tool gatekeepers, and updated build order. The uploaded source explicitly identifies these as Sections 7–9 and states they are intended to be turned into implementation prompts. fileciteturn23file0L5-L8
