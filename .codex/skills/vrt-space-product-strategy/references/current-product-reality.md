# Current Product Reality

## What The Repo Already Has

- Public audit flow in `apps/tools/` with async execution and result pages
- Authenticated workspace flow with project switching, reruns, audit history, and credits
- Separate SEO, AEO, and content workspaces
- Billing, subscriptions, credit ledger, checkout, and webhooks
- Automation, scheduling, exports, sharing, PDFs, and notifications

## What The Revamp Needs To Respect

- The implementation is deeper than the new public story.
- The revamp should simplify presentation, not erase useful systems.
- The product already behaves like a SaaS platform internally more than the public site suggests.

## Observed Tension In Current Files

### Public shell

`templates/base.html` still exposes extra product vocabulary and modules such as content and project-control concepts in the main navigation.

### Homepage

`templates/core/home.html` already has a working audit CTA and strong form foundation, but the page still mixes:

- technical language
- agency-service framing
- platform architecture exposition
- custom-work messaging

This competes with the tighter Audit/SEO/AEO story described in `prompts/new`.

### Workspace

`templates/tools/workspace_dashboard.html` already reflects the product loop well:

- active workspace
- reruns
- command center
- fix queue
- history
- credits

This means the public revamp should likely borrow from the workspace story instead of inventing a new one.

## Practical Product Guidance

- Hide excess complexity publicly before removing backend capability.
- Keep internal module depth available for authenticated users.
- Use the audit as the public entry point, the workspace as the retention home, and SEO/AEO as the value-expansion layers.
- Keep custom work as a secondary exception path, not the headline story.
