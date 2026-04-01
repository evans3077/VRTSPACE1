# SEO And AEO Change Plan

Use this plan before changing any route that can be crawled or shared.

## Step 1: Classify The Page

- `indexable-marketing`
  - Example: homepage, services, articles, case studies, landing pages.
- `indexable-programmatic`
  - Example: public report pages that are intentionally meant to rank or be cited.
- `utility-or-private`
  - Example: login, signup, workspace, in-progress states, exports, gated views.

If classification is unclear, decide indexability first. Do not defer the crawl decision.

## Step 2: Trace The Render Chain

Inspect:

1. URL registration
2. view or context builder
3. page data source
4. template
5. shared head tags in `../../../templates/base.html`

Do not patch only the template if the metadata belongs in the view or page-data model.

## Step 3: Set The Metadata Contract

For indexable pages, explicitly decide:

- page title
- meta description
- canonical URL
- robots directive
- Open Graph title and description
- Twitter card type
- schema payload

Do not let a public route inherit generic fallback metadata.

## Step 4: Apply The AEO Layer

For pages intended to earn citations or answer visibility:

- start with a direct answer or summary
- keep the heading stack aligned to intent
- add entity-rich supporting detail
- add FAQ or summary blocks only when the visible page content supports them
- use schema that matches the visible content

## Step 5: Check Internal Links And Discovery

- Add or update contextual internal links.
- Keep page relationships aligned to pillar and cluster logic.
- If the page is indexable, decide whether sitemap coverage or robots behavior must change in the same edit.

## Step 6: Validate Against The Repo's Own Rules

Compare the result with `../../../apps/tools/services.py`, especially checks for:

- missing title
- weak or missing meta description
- missing canonical
- missing schema
- weak social metadata
- low internal links
- FAQ-schema opportunity

## Definition Of Done

A change is ready when:

- every affected public page has an intentional indexation decision
- every indexable page has explicit metadata and matching schema
- every utility or private page has explicit crawl control
- headings, summary text, and schema tell the same story
- internal links support the intended content graph
- tests or targeted verification cover the metadata assembly path
