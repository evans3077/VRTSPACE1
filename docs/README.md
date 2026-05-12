# VRT SPACE — documentation index

Where to look for what.

| File | Read when... |
|---|---|
| [`DEPLOY.md`](DEPLOY.md) | Setting up a fresh Render deploy or moving to a new host. Lists every env var grouped by feature with explicit "without this, X breaks" notes. |
| [`TESTING.md`](TESTING.md) | Click-through test plans for every major flow (free audit, onboarding, AEO precision, team invites, WordPress push, Stripe). Use to verify a deploy or onboard a new dev. |
| [`STRIPE_SETUP.md`](STRIPE_SETUP.md) | Wiring Stripe to the workspace billing flow — products, prices, webhooks, plan-catalog sync. |
| [`../.env.example`](../.env.example) | The full inventory of env vars with provider URLs, defaults, and "set this on Render" comments. |

## Quick links

- **First-time setup:** `DEPLOY.md` § 1, then `STRIPE_SETUP.md`, then `TESTING.md` § 1+2+8.
- **Verify a deploy:** `TESTING.md` § 1, 2a, 3, 8 (the four critical paths).
- **Add a new env var:** update both `.env.example` (with comment) and `DEPLOY.md` (with "without it" note).
