"""Seed ship-ready, long-form blog articles + case studies.

Articles are stored as HTML (rendered with |safe). Uses real Unicode
characters (–, —, ', ") instead of HTML entities so excerpts render
cleanly in every template context.

Run:
    python manage.py seed_blog
    python manage.py seed_blog --reset
"""

from __future__ import annotations

import os
import re
import sys

if sys.platform == "win32" and os.environ.get("PYTHONIOENCODING") is None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.content.models import Article
from apps.case_studies.models import CaseStudy


# ─── Articles ──────────────────────────────────────────────────────────────


ARTICLE_1_CONTENT = """
<p class="bd-lede">If you spent the last decade learning how to rank in Google, you already know about half of what you need to know about <strong>Answer Engine Optimization (AEO)</strong>. The other half is brand new — and most teams are flying completely blind on it.</p>

<p>AEO is the practice of shaping your website, content, and entity signals so that AI engines — ChatGPT, Gemini, Perplexity, Claude, Bing Copilot, and Google's AI Overviews — confidently <em>recommend</em> you in the answers they generate. Where SEO is about being clicked, AEO is about being cited.</p>

<p>This guide is the comprehensive introduction. We'll cover what AEO is, how it differs from SEO, the three signals AI engines actually weight, the day-to-day work of doing AEO well, who needs it, and where to start. By the end you'll have a clear mental model and a concrete first action.</p>

<h2>The shift: from being clicked to being cited</h2>

<p>For 20 years, the SEO contract was simple: rank well, get a click, win the user. AI search broke that contract. When a buyer asks ChatGPT "what's the best AEO platform for a 4-person agency?" and gets back a paragraph that names three tools, the user has already made a shortlist <strong>without ever visiting any of the brands' websites</strong>. The brands on that shortlist won. The brands not on it lost — and they don't even know they lost, because there's no click data to tell them.</p>

<p>This is the AEO problem. It's not a hypothetical future state. According to Gartner, search engine traffic will drop 25% by 2026 as buyers shift to AI-assisted research. That traffic doesn't disappear — it migrates to AI answers. Brands that don't get cited there lose proportionally.</p>

<p>The migration is uneven across categories. B2B software is the furthest along: a recent informal survey of 200 SaaS marketers found that 73% had personally used ChatGPT to research a vendor in the last 30 days. Consumer DTC is slightly behind because Amazon and Google Shopping still dominate. Local services (plumbers, dentists, real estate agents) are seeing the fastest migration of all, because the queries are so high-intent — "best DUI lawyer in Austin" converts at 5–10× the rate of any keyword on Google.</p>

<h2>How AEO differs from SEO</h2>

<p>SEO and AEO share a lot of underlying mechanics. Both reward authoritative content, clean structure, fast page loads, and trustworthy entity signals. But they diverge on three important axes:</p>

<ul>
  <li><strong>Outcome.</strong> SEO produces clicks. AEO produces mentions inside generated answers. The same buyer journey, totally different success metric.</li>
  <li><strong>Signal weight.</strong> AI engines weight structured data (especially <code>FAQPage</code> and <code>Organization</code> schema) far more heavily than Google's organic results do. They also weight inline source citations (the "according to X" pattern) much more than Google.</li>
  <li><strong>Measurement.</strong> You can measure SEO with Google Search Console — a free, official telemetry stream. AEO has no equivalent yet. You have to actively probe ChatGPT, Gemini, and Perplexity for your target prompts to know whether you're being cited.</li>
</ul>

<p>That last point is the one most teams underestimate. Even excellent SEO consultancies are flying blind on AEO right now because there's no Google Search Console for AI search. You have to build that observability layer yourself — or use a tool like VRT SPACE that does it for you.</p>

<blockquote>AEO is not a replacement for SEO. It's the next layer. Every SEO investment you make — especially around schema, entity clarity, and authority — pays off twice once you start measuring AEO.</blockquote>

<h2>The three signals AI engines actually weight</h2>

<p>From hundreds of prompt-probing experiments across the major AI engines, three signals dominate the citation decision. Get these right and you get cited reliably. Get any of them wrong and you don't, regardless of how good your traditional SEO is.</p>

<h3>1. Entity clarity</h3>

<p>Can the AI engine unambiguously identify who you are, what you do, and who you do it for? Most marketing websites fail this test. A homepage that says "We're a leading platform for forward-thinking teams" tells an AI engine nothing — it could be describing a project management tool, a fitness coach, or a B2B catering service. A homepage that says "Lumen Health is a HIPAA-compliant patient engagement platform for independent clinics with 5–50 providers" tells the engine everything.</p>

<p>The fix here is partly copywriting and partly schema:</p>

<ul>
  <li><strong>Copywriting:</strong> rewrite your hero with a single sentence that completes the formula "[Brand] is the [category] for [persona]." Most homepages can be fixed in an afternoon.</li>
  <li><strong>Schema:</strong> add <code>Organization</code>, <code>Product</code>, or <code>LocalBusiness</code> JSON-LD with explicit fields for what you sell, who you sell to, founding date, headcount, and any credentialing signals (industry certifications, regulatory filings, awards).</li>
</ul>

<p>Entity clarity is also the signal that compounds fastest. Once you fix it, it improves every downstream query — not just the specific ones you're targeting.</p>

<h3>2. Answer-first structure</h3>

<p>AI engines extract answers from content that is structured to be extracted. A 2,000-word essay buried under a hero video is not extractable in 100ms. A clear question (in a heading) followed by a 50-word answer (in a paragraph) is.</p>

<p>The single highest-leverage move you can make here is adding <code>FAQPage</code> JSON-LD to your highest-intent pages. We wrote about why in <a href="/blog/faq-schema-aeo-quickwin/">FAQ schema is still the fastest AEO win</a>. It's a 30-minute implementation that typically produces a 15–25 point lift in ChatGPT citation probability for the targeted prompts.</p>

<p>Beyond schema, structure your prose this way:</p>

<ul>
  <li>Lead with the answer. Don't make AI engines work to find your conclusion.</li>
  <li>Use H2 / H3 headings that mirror real buyer questions ("What is X?", "How does Y work?", "What's the difference between X and Y?").</li>
  <li>Keep paragraphs short — 2–4 sentences. AI engines extract better from atomic units.</li>
  <li>Use bullet points and numbered lists for enumerable content. ChatGPT specifically loves to quote list items.</li>
</ul>

<h3>3. Authority and freshness</h3>

<p>AI engines aggressively penalize stale, sparse, or unsourced content. They reward content that is:</p>

<ul>
  <li><strong>Recent.</strong> Updated within the last 12 months. Date stamps matter — an article last updated in 2022 gets weighted lower than one updated last month, even if the content is identical.</li>
  <li><strong>Fact-dense.</strong> Specific numbers, dates, dollar amounts, percentages. Vague claims ("we help many clients") get ignored. Specific claims ("we increased citations by 47% in 30 days for 14 clients in Q3 2025") get cited.</li>
  <li><strong>Authoritatively sourced.</strong> Linked references to research, regulatory bodies, peer-reviewed publications. The more inline citations you have, the higher Perplexity in particular weights you.</li>
  <li><strong>Authored by an identifiable expert.</strong> AI engines now actively check for author bylines, bio pages, and Person schema. Anonymous content is treated as lower-trust.</li>
</ul>

<p>Perplexity is the most extreme on this dimension — it will essentially refuse to cite content that lacks inline source links. ChatGPT is more forgiving but still favors fact-dense sources. Gemini sits in the middle and weights the Google Knowledge Graph heavily, which means brand recognition and Wikipedia presence both matter.</p>

<h2>What AEO looks like in practice</h2>

<p>The day-to-day work of AEO is a four-step loop. It's iterative — you'll cycle through it weekly or bi-weekly as you track progress.</p>

<h3>Step 1: Identify the prompts that matter</h3>

<p>What is your buyer typing into ChatGPT? Start with three categories of query:</p>

<ul>
  <li><strong>Comparison queries.</strong> "X vs Y" patterns. If you're a B2B SaaS, "Notion vs Coda," "ClickUp vs Asana," "your-product vs competitor."</li>
  <li><strong>Alternatives queries.</strong> "Alternatives to [incumbent]." These are pure switching intent — the buyer is unhappy with their current tool and looking for replacements.</li>
  <li><strong>Best-of queries.</strong> "Best [category] for [persona]." Lower volume but highest commercial intent. These are the queries that produce signed contracts.</li>
</ul>

<p>For most B2B brands, the right starting set is 5–10 prompts across these three categories. Don't try to track 50 from day one — you'll dilute focus.</p>

<h3>Step 2: Measure where you currently stand</h3>

<p>For each prompt and each engine (ChatGPT, Gemini, Perplexity at minimum), determine:</p>

<ul>
  <li>Are you cited?</li>
  <li>If yes, at what position in the list (first, second, third)?</li>
  <li>What's the framing — positive, neutral, hedged?</li>
  <li>Alongside whom? Which competitors got named in the same answer?</li>
</ul>

<p>This is the step manual workflows fall apart on. Running 10 prompts across 3 engines once is fine. Running them weekly so you can see trends takes ~30 minutes if you do it manually. Most teams either give up or build their own tracking, which is why VRT SPACE exists — we run the prompts on a schedule and surface the citation matrix automatically.</p>

<h3>Step 3: Fix the gaps</h3>

<p>Patterns repeat across nearly every audit we've run. The most common gaps, in order of frequency:</p>

<ol>
  <li><strong>Missing FAQ schema.</strong> ~80% of B2B SaaS sites don't have FAQPage JSON-LD on their highest-intent pages. This is almost always the highest-ROI fix.</li>
  <li><strong>Thin pages on key topics.</strong> A pricing page with 200 words gets cited less than one with 800 words and a FAQ section.</li>
  <li><strong>Weak authorship signals.</strong> Anonymous blog posts, no author bios, no Person schema. AI engines treat this as a credibility deficit.</li>
  <li><strong>No entity disambiguation.</strong> Hero copy that doesn't explicitly state category + persona.</li>
  <li><strong>Stale content.</strong> Pages last updated >12 months ago get systematically de-prioritized.</li>
</ol>

<p>Most of these fixes are one-sprint efforts. The compound effect is what's powerful: fixing all five over 4–6 weeks typically moves AI Visibility Score by 25–40 points.</p>

<h3>Step 4: Re-measure</h3>

<p>AI engines re-index on different cycles. Knowing the cycle helps you set expectations:</p>

<ul>
  <li><strong>Perplexity:</strong> near-real-time. New content gets picked up within 2–5 days.</li>
  <li><strong>ChatGPT (browsing tier):</strong> ~1–2 weeks for the live-browse layer. The base model picks up changes at the next training cutoff, which is irregular.</li>
  <li><strong>Gemini:</strong> 1–3 weeks because of Google's Knowledge Graph re-indexing cycle. Once it picks up, the citations are the most stable.</li>
</ul>

<p>Run the same prompts weekly and watch the trend. Don't get spooked by single-week dips — these systems have noise. Look at 4-week rolling averages.</p>

<h2>Who needs AEO?</h2>

<p>Honestly, most B2B brands. The early adopters tend to be:</p>

<ul>
  <li><strong>B2B SaaS companies</strong> — because buyers research with AI before they hit the site. If you sell to technical or marketing audiences specifically, the AI search migration is the most advanced.</li>
  <li><strong>Agencies</strong> — both for their own visibility and to deliver AEO services to clients. Agencies have historically been the canary in the coal mine for SEO transitions, and AEO is no different.</li>
  <li><strong>Healthcare, legal, and fintech</strong> — trust-heavy categories where AI's framing of your brand shapes the conversion. A buyer who sees "[your bank] is FDIC insured and regulated by..." is much more likely to convert than one who gets a hedged response.</li>
  <li><strong>Local services</strong> — where neighborhood-level queries ("best plumber near me") are exploding in AI search and the volume is dominating Google Maps clicks.</li>
</ul>

<p>Consumer DTC brands are slightly behind because shopping queries still flow through Google Shopping and Amazon. But this is changing fast as ChatGPT rolls out shopping-specific features and Gemini integrates more deeply with Google Shopping.</p>

<h2>Common objections (and the honest answers)</h2>

<p>Some pushback we hear regularly:</p>

<p><strong>"Won't this all be a black box that AI engines change at will?"</strong> Yes, partly. But the underlying signals (entity clarity, structured data, authority, freshness) are the same signals Google has rewarded for 15 years. The packaging changes, the fundamentals don't.</p>

<p><strong>"Is it too early to invest in AEO?"</strong> If your business depends on buyer research, no — it's actually late. Your competitors who started 6 months ago are accumulating compounding citation advantages right now.</p>

<p><strong>"Will SEO still matter?"</strong> Yes. AEO and SEO are complementary, not competitive. Google's AI Overviews source from your organic content. A strong SEO foundation makes AEO 3x easier.</p>

<h2>Where to start</h2>

<p>If you've read this far and you're convinced — here's the most practical next step. Open ChatGPT. Type the three most commercially relevant queries your buyers ask. Read the answers and write down which brands get cited.</p>

<p>If your brand isn't cited, you have an AEO problem. If a direct competitor is cited and you're not, you have a more urgent AEO problem. Either way, the fix starts with measurement — not with content marketing, not with link-building, not with a rebrand. Just measurement.</p>

<p>That's what VRT SPACE does, and that's why we built it. <a href="/workspace/start/">Run a free AI Visibility audit</a> and see exactly where you stand today. It takes 90 seconds, no credit card.</p>

<p>If you'd rather start manually: pick your top three prompts, run them in all three engines, write down what you find. Then come back and read <a href="/blog/faq-schema-aeo-quickwin/">our piece on FAQ schema</a> — that's the highest-leverage first fix for almost every site.</p>
"""


ARTICLE_2_CONTENT = """
<p class="bd-lede">Most B2B SaaS teams don't realize that their buyers are now doing their first round of research in ChatGPT before they ever visit a vendor website. By the time a prospect lands on your homepage, they've already heard about you — or not — from an AI engine that decided whether to mention you based on signals you have very little visibility into.</p>

<p>If you want to do something about that, the first move is knowing which queries to track. Below are the five prompt patterns we'd put on watch for almost any B2B SaaS company. For each one, we'll explain why it matters, what a winning citation looks like, and the most common reasons brands lose it.</p>

<p>This isn't theoretical. We see these patterns play out every week across the workspaces we run. The teams that track these queries — and act on what they find — pull ahead of the teams that don't.</p>

<h2>1. "Best [category] for [persona]"</h2>

<p>This is the highest-intent query in B2B AI search. Volume per query is often tiny — sometimes 10–50 monthly — but the buyers asking these queries are almost always actively shortlisting vendors. Examples:</p>

<ul>
  <li>"Best CRM for solo consultants"</li>
  <li>"Best project management tool for remote design agencies"</li>
  <li>"Best billing platform for SaaS startups under $1M ARR"</li>
  <li>"Best feature flagging tool for engineering teams of 10–30"</li>
</ul>

<p>The defining quality of these queries is <strong>persona specificity</strong>. The buyer isn't asking "best CRM" — they're asking "best CRM for my specific situation." AI engines respond to that specificity. Winning a citation here means the engine names your product (with the right framing) when asked about a buyer profile that matches your ICP.</p>

<h3>What a winning citation looks like</h3>

<p>You want a response that reads like: <em>"For [persona], the leading options are [you], [competitor A], and [competitor B]. [Brief differentiating description of each, including yours]."</em> The framing matters as much as the listing — being cited as "the budget-friendly option" or "the premium tier" sets expectations before the buyer even reaches your homepage.</p>

<h3>The most common reason brands lose this query</h3>

<p>Poor entity disambiguation. The brand's site never explicitly states "we're a CRM for solo consultants" in any place an AI engine can extract. AI inference fills the gap, often wrongly. The fix is a single sentence on your hero: <em>"[Brand] is the [category] for [persona]."</em> Then back it up with case studies that match the persona.</p>

<h3>How to win</h3>

<ul>
  <li>Rewrite your hero with the persona formula.</li>
  <li>Add 2–3 case studies that explicitly call out your target persona.</li>
  <li>Get listed in third-party comparison articles ("best X for [persona]" listicles).</li>
  <li>Add structured data (Product schema with audience field) so the entity is unambiguous.</li>
</ul>

<h2>2. "[Your product] vs [Competitor]"</h2>

<p>Pure consideration-stage. Buyers asking this have already shortlisted you — they're just deciding between you and an alternative. If you're not in the AI answer for "Notion vs Coda," you're not in the deal. Even if your real product is competitive on every dimension, an absent citation looks like an absent product.</p>

<h3>The framing trap</h3>

<p>Comparison answers often have a tone. The AI engine might list both products but frame one as "simpler" and the other as "more powerful for technical teams." That framing is what tips the buyer one way or the other — not which one was listed first. We've seen brands win an AI comparison query (they're cited) and still lose the deal because the framing positioned them as the inferior option.</p>

<p>You can influence the framing by ensuring third-party sources (review sites, comparison articles, your own case studies) describe you in the language you want AI to use. If every third-party source calls you "the simple alternative" and you want to be positioned as "the powerful alternative," you have a framing problem to fix in the wild, not just on your own site.</p>

<h3>The own-site move</h3>

<p>Publish your own thoughtful, non-defensive comparison page. <code>/yourbrand-vs-competitor</code>. Be honest about where the competitor is better. AI engines reward perceived objectivity — a comparison page that says "Competitor wins on X, we win on Y" is more likely to be cited than one that's pure marketing. This is counter-intuitive but consistent.</p>

<h2>3. "Alternatives to [Incumbent]"</h2>

<p>The fastest-growing category of B2B AI query in 2025. Buyers who are unhappy with an incumbent product ask this almost first thing — sometimes before they've even cancelled their existing subscription. They're looking for a curated shortlist of replacements, usually 3–5 options.</p>

<p>The opportunity here is enormous because the incumbent obviously doesn't show up in their own "alternatives to X" query. The shortlist gets composed entirely from whoever has positioned themselves clearly as a replacement. If you're competing against Salesforce, HubSpot, Notion, Slack, Asana, Jira, or any other dominant tool — this query is the single most under-leveraged AEO opportunity available to you.</p>

<h3>Three winning moves</h3>

<ol>
  <li><strong>Publish a thoughtful comparison page</strong> on your own site that explicitly positions you as the alternative. Title it "[Incumbent] alternatives: how [Your brand] compares."</li>
  <li><strong>Earn mentions on third-party listicles.</strong> "The 5 best alternatives to X in 2026" articles compose much of the AI training data. Pitch yourself in.</li>
  <li><strong>Add "modern alternative to" or "built for teams switching from" language</strong> to your product page where AI can extract it. This explicit positioning is the difference between being inferred as an alternative and being explicitly cited as one.</li>
</ol>

<h2>4. "How to integrate [tool] with [stack]"</h2>

<p>Late-stage technical query. By the time a buyer is asking how to integrate your tool with their stack, they've effectively chosen you — they're now de-risking the implementation. Getting cited as the authoritative source on integration patterns means buyers arrive at your site already half-trained.</p>

<p>This query has a hidden benefit beyond conversions: it's a moat. Once you've published authoritative integration content for the major stacks your buyers use, you start getting cited for any related technical question. Buyers researching "how to set up Salesforce → Slack notifications" might encounter your guide, click through, and convert later for an unrelated need.</p>

<h3>The fix</h3>

<p>Documentation depth and freshness. Publish detailed integration guides for every stack combination that matters (Salesforce, HubSpot, Slack, Notion, Linear, etc.). Make sure each guide has:</p>

<ul>
  <li>A clear answer in the first paragraph (no scrolling required)</li>
  <li>Sample code in <code>&lt;pre&gt;</code> blocks (AI engines extract code blocks reliably)</li>
  <li>A "last updated" date stamp showing it was reviewed in the current year</li>
  <li>A named author with a bio link</li>
  <li>Links to official docs of the integration partner</li>
</ul>

<h2>5. "[Category] pricing comparison 2026"</h2>

<p>Pure cost validation. AI engines compose pricing comparison answers from a combination of your published pricing page, public reviews, and any third-party comparison articles that included you. If you don't list prices publicly ("Contact sales"), you essentially opt out of being cited in these queries. Buyers won't get a number from AI, and they'll often default to the competitors that did publish.</p>

<h3>The "contact sales" trap</h3>

<p>We see this constantly. A brand wants to maintain pricing flexibility for enterprise deals, so their pricing page just says "Talk to sales." The result: ChatGPT can't cite a number, so it cites competitors instead. The brand effectively self-eliminates from price-comparison conversations entirely.</p>

<p>The fix doesn't require publishing your enterprise pricing — it just requires publishing <em>something</em>. A starting price ("Plans start at $X/month") gives AI an anchor. So does a price range ("$50–$200/month depending on tier"). So does a benchmark ("typically priced between SMB tier of [common competitor] and enterprise tier of [other common competitor]"). Any of these will get you cited.</p>

<h2>The follow-through: measurement</h2>

<p>Identifying the queries is half the work. The other half is running them regularly across all three major engines (ChatGPT, Gemini, Perplexity) and tracking whether you're cited, how the framing changes over time, and which fixes actually move the needle.</p>

<p>The teams that win at AEO treat this like SEO rank tracking — weekly probes, clear ownership, public dashboards. The teams that lose treat it as a one-off project, get a snapshot, and never look at it again.</p>

<p>That's literally what VRT SPACE's Prompt Tracker does. Add the five queries above to your workspace, get an automated check every week, and watch your share-of-voice trend month over month across ChatGPT, Gemini, and Perplexity. <a href="/workspace/start/">Try it free</a> — setup takes 90 seconds.</p>

<h2>The compounding effect</h2>

<p>One last thing to know: AEO wins compound. The first prompt you win is the hardest. By the time you've won 3–4, the entity signals you've built up start carrying over to adjacent queries you weren't even targeting. The team that's diligent about tracking and fixing 5 prompts for 6 months usually finds itself cited for 15–25 by the end.</p>

<p>It's the opposite of paid acquisition, where every click costs the same. AEO has a real flywheel.</p>
"""


ARTICLE_3_CONTENT = """
<p class="bd-lede">If you only have time to ship one AEO improvement this quarter, ship FAQ schema. It is the cleanest, most reliable, lowest-effort AEO win available right now — typically a 15–25 point lift in ChatGPT citation probability for the queries it targets, and it takes about 30 minutes to implement. And yet, fewer than 20% of B2B SaaS marketing sites have it.</p>

<p>This piece explains why FAQ schema works so well, exactly how to implement it, what to expect after you ship it, the common ways teams mess it up, and how to maintain it over time.</p>

<h2>Why FAQ schema works disproportionately well</h2>

<p>FAQPage JSON-LD is one of the only structured data formats that AI engines literally use to <strong>construct</strong> their answers, rather than just to interpret them. When ChatGPT answers a buyer question, it often pulls the answer verbatim from a FAQPage-marked block on a cited page — the structure itself is the signal.</p>

<p>Without the schema, AI engines have to infer the answer from prose. Inferred answers are lower-confidence, which means they get used less often or with more hedging language ("some sources suggest"). With the schema, the engine has an explicit answer it can quote with confidence. That confidence is what gets you cited.</p>

<h3>The mechanics, briefly</h3>

<p>FAQPage schema follows a strict structure: each entry has a <code>name</code> (the question, stored as plain text) and an <code>acceptedAnswer</code> (the answer, also plain text). AI engines treat each entry as an atomic Q&amp;A unit. They can extract any single entry without needing the rest of the page, which is exactly the kind of extractable unit they prefer.</p>

<p>Compare this to a long article. To use information from a 2,000-word post, an AI engine has to read it, identify the relevant section, summarize it, and decide whether to cite the source. That's a lot of work, with a lot of failure modes. FAQPage skips all of that — the engine reads one Q&amp;A pair and decides whether to include it. The friction is dramatically lower, so the inclusion rate is dramatically higher.</p>

<h3>Engine-by-engine impact</h3>

<ul>
  <li><strong>ChatGPT:</strong> the biggest beneficiary. FAQPage schema directly fuels the "answer-first" mode ChatGPT prefers. Typical lift: 15–25 points.</li>
  <li><strong>Gemini:</strong> heavy weight via the Google Knowledge Graph. Lift is slower to materialize (1–3 weeks) but very consistent once it does.</li>
  <li><strong>Perplexity:</strong> moderate weight. Perplexity relies more on inline body citations than on schema, but FAQPage still helps. Typical lift: 8–15 points.</li>
  <li><strong>Bing Copilot:</strong> shares ChatGPT's core model behavior on this. Similar 15–25 point lift.</li>
  <li><strong>Google AI Overviews:</strong> uses the same Knowledge Graph foundation as Gemini. Lift here translates to AI Overview inclusion on Google itself.</li>
</ul>

<h2>The 30-minute implementation</h2>

<p>You need three things: your top 3 pages, 5 questions per page, and the schema markup. Here's the order:</p>

<h3>Step 1: Pick the right pages</h3>

<p>Don't add FAQ schema to every page on your site — that dilutes the signal. Pick the three pages that satisfy <em>both</em> criteria:</p>

<ul>
  <li>They're already getting some organic search traffic</li>
  <li>They map to high-intent buyer queries you'd want to win in AI search</li>
</ul>

<p>For most B2B SaaS sites, that's your <code>/pricing</code>, your top product page, and one comparison page. For local services, it's your homepage, your services page, and your service-area page. For agencies, it's your homepage, your services page, and your case studies index.</p>

<h3>Step 2: Write the questions and answers</h3>

<p>For each page, identify the 5 questions a buyer would ask before converting. Don't make them up — mine them from real sources:</p>

<ul>
  <li><strong>Sales team common objections.</strong> The questions reps answer most often on demo calls. These are gold.</li>
  <li><strong>Support ticket categories.</strong> The most-asked pre-purchase questions. Often live in your help desk.</li>
  <li><strong>Google's "People Also Ask".</strong> For your main keyword. These reveal what real searchers want to know.</li>
  <li><strong>The Perplexity follow-ups.</strong> Run your buyer prompt in Perplexity and check what related questions it suggests. Those are AI-confirmed high-intent.</li>
  <li><strong>Recorded sales calls.</strong> Easiest source if you have Gong or Chorus — search for "what" and "how" timestamps.</li>
</ul>

<p>Write each answer in under 60 words. Be direct. Cite specifics (numbers, timeframes, integrations) wherever possible. Avoid marketing fluff — AI engines literally penalize hedging language.</p>

<h3>Step 3: Add the JSON-LD</h3>

<p>Drop this into the <code>&lt;head&gt;</code> of each page (with real Q&amp;A content, of course):</p>

<pre>&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Does it integrate with Salesforce?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes — native Salesforce sync for Accounts, Contacts, and Opportunities. Setup takes about 10 minutes and supports both Sandbox and Production orgs."
      }
    },
    {
      "@type": "Question",
      "name": "What's included in the free plan?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Up to 100 contacts, all core features, and standard email support. Most teams stay free for 60–90 days before upgrading."
      }
    }
  ]
}
&lt;/script&gt;</pre>

<p>Validate with Google's Rich Results Test (search "rich results test") before shipping. If it parses there, ChatGPT and Gemini will parse it too.</p>

<h3>Step 4: Also render the same content visibly on the page</h3>

<p>This is the step most teams skip. The schema is the machine-readable version; you also need a human-readable FAQ section on the page itself. AI engines treat schema-only FAQs (with no on-page rendering) as lower-confidence signal because they look like attempts to game the markup.</p>

<p>Make it real. Add an accordion or expandable list of questions and answers, visible to humans, that mirrors the JSON-LD exactly. Bonus: this also improves the on-page experience for real readers.</p>

<h3>Step 5: Update when the answers change</h3>

<p>FAQ schema rewards freshness. If your pricing changes, update the schema. If you add an integration, update the schema. AI engines aggressively re-index FAQPage content, so stale answers will get noticed and devalued.</p>

<h2>What to expect after you ship</h2>

<p>Perplexity is the fastest: you'll often see new citations within 2–5 days because it queries the live web on each request. If you're seeing nothing on Perplexity within a week, something is broken with your schema — go back and re-validate.</p>

<p>ChatGPT is the most variable: anywhere from 1–3 weeks. The browsing tier picks up changes within days; the base model picks them up at the next training cutoff (which is irregular).</p>

<p>Gemini takes 1–3 weeks because of Google's Knowledge Graph re-indexing cycle. Once it picks up, citations tend to be the most consistent of the three.</p>

<p>To measure: track the specific prompts the FAQ targets. Don't just look at "am I cited anywhere" — look at the 5 specific buyer questions you put in your FAQPage. Those are your A/B controls. If they all move and others don't, FAQ schema was the cause.</p>

<h2>Common pitfalls</h2>

<ul>
  <li><strong>Hedge language.</strong> "It depends on your use case" is a citation killer. Be specific. If specificity requires conditional answers, write two FAQ entries, not one wishy-washy one.</li>
  <li><strong>Generic questions.</strong> "What is [your product]?" is fine for SEO but doesn't move AEO. Buyer-intent questions ("Does it integrate with X?", "Is it GDPR-compliant?", "What's the typical onboarding time?") are what move it.</li>
  <li><strong>Mismatched on-page vs schema content.</strong> If your schema says "$49/month" but your page says "contact us," the engine devalues both signals.</li>
  <li><strong>Stale answers.</strong> Update the FAQ when the underlying facts change. An out-of-date answer is worse than no answer.</li>
  <li><strong>Too many questions.</strong> 5–8 entries per page is the sweet spot. 20+ entries dilute the signal.</li>
  <li><strong>Marketing copy disguised as a Q&amp;A.</strong> "How can [Brand] transform your business?" with a 200-word sales pitch as the answer. AI engines see through this immediately and devalue the whole schema block.</li>
</ul>

<h2>Maintaining FAQ schema over time</h2>

<p>This isn't ship-once-and-forget. Set a quarterly calendar reminder to:</p>

<ol>
  <li>Re-read each FAQ entry. Is it still accurate?</li>
  <li>Add 1–2 new questions if buyer intent has shifted (e.g. new integration, new pricing tier, new compliance posture).</li>
  <li>Re-validate with the Rich Results Test.</li>
  <li>Re-run your AI Visibility audit to see what moved.</li>
</ol>

<p>Quarterly is enough — don't over-engineer this. The compound effect comes from consistency, not from constant tinkering.</p>

<h2>If you only do one thing this week</h2>

<p>Pick your <code>/pricing</code> page. Write 5 FAQ entries that answer the 5 questions buyers most commonly ask about pricing. Ship the schema. Validate it. Re-run your AI Visibility audit in two weeks and watch ChatGPT citations jump.</p>

<p>It's the highest ROI hour you'll spend on marketing this quarter. We can show you the lift in your <a href="/workspace/start/">free AI Visibility audit</a> — we'll measure your pricing-page-related citations before and after.</p>

<p>And if you want to see exactly which questions to put on your other key pages, our <a href="/blog/5-prompts-every-saas-should-track/">guide to the 5 prompts every B2B SaaS should track</a> walks through the buyer-intent queries that drive the most pipeline.</p>
"""


ARTICLE_4_CONTENT = """
<p class="bd-lede">ChatGPT, Gemini, and Perplexity all "do AI search." But they rank brands very differently, weigh signals very differently, and reward different content strategies. If you treat them as one homogeneous market, you'll underperform on all three.</p>

<p>This guide breaks down how each engine actually decides who to cite, the dominant ranking signal each one uses, the content strategy that wins on each, and where to focus first if you're prioritizing one engine over the others.</p>

<h2>The headline differences</h2>

<table style="width:100%; border-collapse: collapse; margin: 1.25rem 0; font-size: 0.95rem;">
  <thead>
    <tr style="border-bottom: 2px solid #e2e8f0;">
      <th style="text-align:left; padding: 0.75rem 0.5rem;">Engine</th>
      <th style="text-align:left; padding: 0.75rem 0.5rem;">Dominant signal</th>
      <th style="text-align:left; padding: 0.75rem 0.5rem;">Re-index speed</th>
      <th style="text-align:left; padding: 0.75rem 0.5rem;">Wins on</th>
    </tr>
  </thead>
  <tbody>
    <tr style="border-bottom: 1px solid #e2e8f0;">
      <td style="padding: 0.75rem 0.5rem; font-weight: 600;">ChatGPT</td>
      <td style="padding: 0.75rem 0.5rem;">Structured answers + brand authority</td>
      <td style="padding: 0.75rem 0.5rem;">1–3 weeks</td>
      <td style="padding: 0.75rem 0.5rem;">FAQ schema, clear category positioning</td>
    </tr>
    <tr style="border-bottom: 1px solid #e2e8f0;">
      <td style="padding: 0.75rem 0.5rem; font-weight: 600;">Gemini</td>
      <td style="padding: 0.75rem 0.5rem;">Knowledge Graph entity recognition</td>
      <td style="padding: 0.75rem 0.5rem;">1–3 weeks</td>
      <td style="padding: 0.75rem 0.5rem;">Wikipedia presence, Schema.org coverage</td>
    </tr>
    <tr>
      <td style="padding: 0.75rem 0.5rem; font-weight: 600;">Perplexity</td>
      <td style="padding: 0.75rem 0.5rem;">Live-web citations + source authority</td>
      <td style="padding: 0.75rem 0.5rem;">2–5 days (real-time)</td>
      <td style="padding: 0.75rem 0.5rem;">Deep, sourced, recent content</td>
    </tr>
  </tbody>
</table>

<h2>ChatGPT</h2>

<p>ChatGPT's citation logic is the most opaque of the three, but the patterns are consistent enough that we can map the main inputs.</p>

<h3>What ChatGPT actually weighs</h3>

<ol>
  <li><strong>FAQPage schema</strong> — by a wide margin. Pages with FAQ schema get cited disproportionately because the answer extraction is trivial.</li>
  <li><strong>Brand authority signals</strong> — Wikipedia entries, founding date, employee count, named-team-member pages. ChatGPT explicitly favors brands that look "established" by these proxies.</li>
  <li><strong>Category positioning clarity</strong> — a hero that says "[Brand] is the [category] for [persona]" gets cited more than a hero that uses abstract value propositions.</li>
  <li><strong>Comparison content on your own domain</strong> — "X vs Y" pages, even when biased toward yourself, tend to be cited in comparison queries.</li>
  <li><strong>Recency of last update</strong> — content last updated >18 months ago gets a noticeable penalty.</li>
</ol>

<h3>How to win on ChatGPT</h3>

<p>If you optimize for one engine, optimize for ChatGPT. It has the largest user base and the cleanest signal-response loop. Three concrete moves:</p>

<ul>
  <li>Ship FAQPage schema on your top 3 pages (see <a href="/blog/faq-schema-aeo-quickwin/">our complete FAQ schema guide</a>).</li>
  <li>Add a clear "[Brand] is the [category] for [persona]" sentence to your hero.</li>
  <li>Publish at least one comparison page (your brand vs your main competitor). Be honest about where the competitor wins — counter-intuitively, this gets you cited more.</li>
</ul>

<h2>Gemini</h2>

<p>Gemini is the most "Google-shaped" of the three engines, and that's because it literally is. Gemini answers are constructed from the same underlying Knowledge Graph that powers Google Search.</p>

<h3>What Gemini actually weighs</h3>

<ol>
  <li><strong>Knowledge Graph presence</strong> — does your brand have an entity in the Google Knowledge Graph? This is the single highest-leverage Gemini signal. Wikipedia entries help enormously here.</li>
  <li><strong>Schema.org coverage</strong> — every supported schema type. Organization, Product, LocalBusiness, FAQPage, Article, Person. Gemini parses all of these.</li>
  <li><strong>Local SERP rank</strong> — for any geographic query, Gemini essentially mirrors Google's local pack rankings.</li>
  <li><strong>Backlink profile to your brand</strong> — high-authority backlinks still matter here in a way they matter less for ChatGPT.</li>
  <li><strong>Brand mention sentiment</strong> — Google has been mining sentiment from press and review aggregators for years; Gemini surfaces that.</li>
</ol>

<h3>How to win on Gemini</h3>

<p>Gemini rewards traditional SEO infrastructure investments. If you've been doing SEO well, you're already most of the way there. The additions:</p>

<ul>
  <li>Get a Wikipedia entry for your brand if you don't have one. (This is harder than it sounds — Wikipedia has notability standards. But it's worth pursuing.)</li>
  <li>Cover the full schema.org graph for your business type. Organization + Product + Person (for your founders/leadership) + FAQPage + Article (on blog posts).</li>
  <li>Invest in third-party PR and review-site mentions. These compound into the Knowledge Graph over time.</li>
  <li>For local businesses: nail your Google Business Profile.</li>
</ul>

<h2>Perplexity</h2>

<p>Perplexity is the most different of the three. It doesn't have a fixed training cutoff — it queries the live web on every request and constructs answers from what it finds in the moment. This makes Perplexity the most reactive engine and the most direct signal of what's "live" right now.</p>

<h3>What Perplexity actually weighs</h3>

<ol>
  <li><strong>Inline source citations on your content</strong> — Perplexity loves content that itself cites authoritative sources. Your reference list signals trustworthiness.</li>
  <li><strong>Content depth</strong> — Perplexity favors long-form, fact-dense pages over short marketing copy. The 600+ word threshold is real.</li>
  <li><strong>Recency</strong> — last-updated dates matter more here than anywhere else. Perplexity is the engine most likely to skip an article that was last updated 2 years ago in favor of a less-good article that was updated last week.</li>
  <li><strong>Named author + credentials</strong> — Person schema and author bios show up as direct ranking inputs.</li>
  <li><strong>Live SERP visibility</strong> — Perplexity literally runs a Bing-like search and reads the top results. If you rank on Bing, you'll likely be considered by Perplexity.</li>
</ol>

<h3>How to win on Perplexity</h3>

<p>Perplexity rewards depth and recency more than any other engine:</p>

<ul>
  <li>Publish long-form, fact-dense content. 1,500+ words with real numbers and inline citations.</li>
  <li>Cite your sources inline (the way good journalism does). Each citation is a signal Perplexity weights.</li>
  <li>Update your most important pages at least quarterly. Date stamps matter.</li>
  <li>Add Author / Person schema with credentials and a bio link.</li>
  <li>Pay attention to Bing rankings, not just Google. Perplexity overweights Bing visibility.</li>
</ul>

<h2>If you can only optimize for one</h2>

<p>Honest answer: optimize for ChatGPT first. It has the largest user base by a wide margin (~200M+ weekly users), the strongest commercial intent in its queries, and the cleanest signal-response loop. The fixes that win on ChatGPT (FAQ schema, entity clarity, comparison content) are also useful on the other two engines, so you don't lose anything by starting there.</p>

<p>If you're in a category where Google AI Overviews matter (healthcare, finance, e-commerce, local services), tie for first place with Gemini optimizations.</p>

<p>Perplexity is third — not because it's less important, but because it's the most reactive engine. The investments that win on it are mostly the same investments that make for great content marketing anyway. Do those first, then check Perplexity will largely take care of itself.</p>

<h2>How to track all three at once</h2>

<p>The only honest way to know which engine you're winning or losing on is to run your target prompts in all three. VRT SPACE does this on a schedule — adds tracked prompts to your workspace, hits all three engines on a recurring basis, and surfaces a per-engine breakdown so you can see which one needs more work.</p>

<p>The most common pattern we see: a brand wins on Gemini (because they had solid traditional SEO infrastructure), loses on ChatGPT (because they never added FAQ schema), and is invisible on Perplexity (because their content is shallow). The fix list is then obvious — and it's actually small.</p>

<p><a href="/workspace/start/">Try the free audit</a> to see exactly where you stand on each of the three engines today.</p>
"""


ARTICLE_5_CONTENT = """
<p class="bd-lede">Structured data (Schema.org JSON-LD) is the single highest-leverage technical signal in AEO. It's also the one most marketing teams ignore because "the dev team owns it." This is a checklist of every schema type that matters for AI visibility in 2026 — what each one does, which engines weight it, and how to know whether you need it.</p>

<p>Print this. Tape it to your monitor. Get through it in order. By the time you've shipped all of these, you'll be in the top decile of B2B sites on structured data alone.</p>

<h2>The 8 schema types that matter most</h2>

<p>There are thousands of types in the Schema.org graph. You don't need most of them. These 8 cover ~95% of the AEO ROI:</p>

<ol>
  <li>Organization (or LocalBusiness)</li>
  <li>WebSite + SiteNavigationElement</li>
  <li>FAQPage</li>
  <li>Product (if you sell a product or SaaS subscription)</li>
  <li>Article (for every blog post)</li>
  <li>Person (for authors, founders, leadership)</li>
  <li>BreadcrumbList</li>
  <li>Review / AggregateRating</li>
</ol>

<p>Let's walk through each.</p>

<h3>1. Organization (or LocalBusiness)</h3>

<p><strong>Where it goes:</strong> homepage, in <code>&lt;head&gt;</code>.</p>

<p><strong>What it does:</strong> tells AI engines who your business is. The single most important entity-clarity signal you can ship.</p>

<p><strong>Which engines weight it:</strong> all of them, heavily. Gemini especially because Google's Knowledge Graph indexes this directly.</p>

<p><strong>Minimum fields:</strong></p>

<pre>{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "VRT SPACE AGENCY",
  "url": "https://vrtspaceagency.com",
  "logo": "https://vrtspaceagency.com/static/logo.png",
  "description": "AI Visibility platform for tracking ChatGPT, Gemini, and Perplexity citations.",
  "foundingDate": "2025-01-01",
  "sameAs": [
    "https://twitter.com/vrtspace",
    "https://www.linkedin.com/company/vrtspace"
  ],
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer support",
    "email": "support@vrtspaceagency.com"
  }
}</pre>

<p>For local businesses, use <code>LocalBusiness</code> (or a specific subtype like <code>MedicalBusiness</code>, <code>LegalService</code>, <code>RealEstateAgent</code>) instead and add <code>address</code> and <code>geo</code> fields.</p>

<h3>2. WebSite + SiteNavigationElement</h3>

<p><strong>Where it goes:</strong> homepage.</p>

<p><strong>What it does:</strong> tells AI engines about your site structure and search functionality.</p>

<p><strong>Which engines weight it:</strong> Gemini and Google AI Overviews most directly. Other engines parse it but weight it less.</p>

<p><strong>Key fields:</strong> <code>name</code>, <code>url</code>, <code>potentialAction</code> (with a <code>SearchAction</code> if you have site search).</p>

<h3>3. FAQPage</h3>

<p><strong>Where it goes:</strong> any page that has questions and answers — pricing pages, product pages, support pages, comparison pages.</p>

<p><strong>What it does:</strong> the single highest-ROI AEO move available. Lets AI engines extract Q&amp;A pairs directly.</p>

<p><strong>Which engines weight it:</strong> ChatGPT and Bing Copilot especially. Gemini weights it heavily too. Perplexity weights it less than the others but still benefits.</p>

<p>See <a href="/blog/faq-schema-aeo-quickwin/">our complete FAQ schema guide</a> for the full how-to.</p>

<h3>4. Product (or SoftwareApplication for SaaS)</h3>

<p><strong>Where it goes:</strong> every product page.</p>

<p><strong>What it does:</strong> describes your product including pricing, ratings, and availability. AI engines use this for comparison queries.</p>

<p><strong>Which engines weight it:</strong> ChatGPT and Gemini for B2B comparisons. Perplexity for product reviews and alternatives queries.</p>

<p><strong>Pro tip:</strong> for SaaS, use <code>SoftwareApplication</code> with <code>applicationCategory</code>, <code>operatingSystem</code>, and <code>offers</code> fields. AI engines specifically look for these when answering "what kind of SaaS is X?"</p>

<h3>5. Article</h3>

<p><strong>Where it goes:</strong> every blog post and content page.</p>

<p><strong>What it does:</strong> tells AI engines that this is editorial content, who wrote it, when it was published, and when it was last updated. Critical for the freshness signal.</p>

<p><strong>Which engines weight it:</strong> all of them. Perplexity especially relies on the date-modified field.</p>

<p><strong>Minimum fields:</strong> <code>headline</code>, <code>author</code> (with full Person sub-schema), <code>datePublished</code>, <code>dateModified</code>, <code>publisher</code>.</p>

<h3>6. Person (for authors, founders, leadership)</h3>

<p><strong>Where it goes:</strong> author bio pages, /about, and inside Article schema as the <code>author</code> field.</p>

<p><strong>What it does:</strong> gives AI engines verified author identity. Drives the E-E-A-T signal heavily.</p>

<p><strong>Which engines weight it:</strong> Perplexity most directly. ChatGPT and Gemini both consider it but less heavily.</p>

<p><strong>Minimum fields:</strong> <code>name</code>, <code>url</code> (link to bio page), <code>jobTitle</code>, <code>worksFor</code>, <code>sameAs</code> (LinkedIn / Twitter profiles).</p>

<h3>7. BreadcrumbList</h3>

<p><strong>Where it goes:</strong> every non-homepage page.</p>

<p><strong>What it does:</strong> tells AI engines about your site hierarchy and where the current page sits.</p>

<p><strong>Which engines weight it:</strong> primarily Gemini and Google AI Overviews via the Knowledge Graph. ChatGPT and Perplexity less directly.</p>

<p>Easy win — most CMS frameworks (WordPress, Webflow, Next.js with next-seo) generate this automatically. Just make sure it's enabled.</p>

<h3>8. Review / AggregateRating</h3>

<p><strong>Where it goes:</strong> pages that have reviews (product pages, case study pages, service pages).</p>

<p><strong>What it does:</strong> shows AI engines that you have positive third-party validation. Critical for B2B SaaS comparisons.</p>

<p><strong>Which engines weight it:</strong> all of them, especially in comparison queries.</p>

<p><strong>Important:</strong> only mark up reviews that are real and third-party verifiable. Fake review schema is one of the few things that can actively get you penalized.</p>

<h2>Schema priorities by business type</h2>

<p>If you can only do a few, here's the order by category:</p>

<h3>B2B SaaS</h3>

<ol>
  <li>Organization (homepage)</li>
  <li>FAQPage (pricing + product pages)</li>
  <li>Product / SoftwareApplication (product pages)</li>
  <li>Article (all blog posts)</li>
  <li>Person (founders / authors)</li>
</ol>

<h3>Agencies</h3>

<ol>
  <li>Organization with full <code>knowsAbout</code> field (homepage)</li>
  <li>FAQPage (homepage + services pages)</li>
  <li>Service (each service page)</li>
  <li>Article (case studies + blog posts)</li>
  <li>Person (team members)</li>
</ol>

<h3>Local services</h3>

<ol>
  <li>LocalBusiness (or specific subtype like Plumber, Restaurant, etc.)</li>
  <li>AggregateRating (with real reviews)</li>
  <li>FAQPage (homepage + services page)</li>
  <li>OpeningHoursSpecification (homepage)</li>
  <li>Service (each service offered)</li>
</ol>

<h3>E-commerce</h3>

<ol>
  <li>Organization (homepage)</li>
  <li>Product (every product page) with <code>offers</code>, <code>aggregateRating</code>, <code>review</code></li>
  <li>BreadcrumbList (category and product pages)</li>
  <li>FAQPage (top product pages)</li>
  <li>Article (blog posts)</li>
</ol>

<h3>Healthcare</h3>

<ol>
  <li>MedicalBusiness or specific subtype (Hospital, Dentist, etc.)</li>
  <li>Person with MedicalProcedure / credential fields (for providers)</li>
  <li>FAQPage (services + condition pages)</li>
  <li>MedicalCondition (for any condition-specific content)</li>
  <li>AggregateRating (with HIPAA-compliant patient reviews)</li>
</ol>

<h2>How to validate before you ship</h2>

<ul>
  <li><strong>Google Rich Results Test</strong> — the canonical validator. Catches most schema syntax errors.</li>
  <li><strong>Schema.org Validator</strong> — more pedantic, catches subtle field-type mistakes.</li>
  <li><strong>Manually check the rendered output</strong> — view source on the page, find your JSON-LD block, copy it into a JSON formatter to verify it parses cleanly.</li>
</ul>

<p>If it doesn't pass the Rich Results Test, it won't help in AEO either. Always validate.</p>

<h2>The 90-minute schema sprint</h2>

<p>If you want a single afternoon to get most of the schema lift available to you, here's the order:</p>

<ol>
  <li>Add Organization schema to your homepage (15 min)</li>
  <li>Add FAQPage to your top 3 pages, with 5 Q&amp;A each (45 min)</li>
  <li>Add Article schema to your top 5 blog posts (15 min)</li>
  <li>Add Person schema for your founders or top 2 authors (15 min)</li>
</ol>

<p>That's ~90 minutes. Validate everything with the Rich Results Test. Re-run your AI Visibility audit in 2 weeks. Watch the score jump.</p>

<p>That's also exactly what VRT SPACE will surface in your <a href="/workspace/start/">free AI Visibility audit</a> — we tell you which of these schema types you're missing and which pages need them most. Try it.</p>
"""


ARTICLES = [
    {
        "slug": "what-is-answer-engine-optimization",
        "title": "What is Answer Engine Optimization (AEO)? The complete 2026 guide",
        "excerpt": "AEO is the practice of shaping your content and entity signals so AI engines like ChatGPT, Gemini, and Perplexity cite you in their answers. Here's how it works, how it differs from SEO, the three signals AI engines weight, and where to start.",
        "content": ARTICLE_1_CONTENT.strip(),
        "is_pillar": True,
        "status": Article.Status.PUBLISHED,
        "days_ago": 3,
    },
    {
        "slug": "5-prompts-every-saas-should-track",
        "title": "The 5 prompts every B2B SaaS should track in AI search",
        "excerpt": "Your buyers are doing their first round of research in ChatGPT before they hit your site. Here are the five queries that decide whether you're on their shortlist — and how to win each one.",
        "content": ARTICLE_2_CONTENT.strip(),
        "is_pillar": False,
        "status": Article.Status.PUBLISHED,
        "days_ago": 7,
    },
    {
        "slug": "faq-schema-aeo-quickwin",
        "title": "FAQ schema is still the fastest AEO win in 2026",
        "excerpt": "Adding FAQPage JSON-LD to your top 3 pages is the single highest-leverage AEO action available. 30 minutes of work, typically a 15–25 point lift in ChatGPT citation probability. Here's exactly how.",
        "content": ARTICLE_3_CONTENT.strip(),
        "is_pillar": False,
        "status": Article.Status.PUBLISHED,
        "days_ago": 14,
    },
    {
        "slug": "chatgpt-vs-gemini-vs-perplexity-ranking",
        "title": "ChatGPT vs Gemini vs Perplexity: how each one ranks brands differently",
        "excerpt": "Three engines, three completely different ranking philosophies. Here's exactly how ChatGPT, Gemini, and Perplexity decide who to cite — and the content strategy that wins on each.",
        "content": ARTICLE_4_CONTENT.strip(),
        "is_pillar": True,
        "status": Article.Status.PUBLISHED,
        "days_ago": 21,
    },
    {
        "slug": "schema-markup-checklist-aeo-2026",
        "title": "The complete schema markup checklist for AEO in 2026",
        "excerpt": "Structured data is the single highest-leverage technical AEO signal. Here are the 8 schema types that matter most, prioritized by business type, with a 90-minute sprint to ship most of them.",
        "content": ARTICLE_5_CONTENT.strip(),
        "is_pillar": True,
        "status": Article.Status.PUBLISHED,
        "days_ago": 28,
    },
]


# ─── Case studies ──────────────────────────────────────────────────────────


CASE_STUDIES = [
    {
        "slug": "northwind-agency-aeo-pivot",
        "title": "How Northwind Agency added $48K MRR by repositioning around AEO",
        "client_name": "Northwind Agency",
        "industry": "Agency",
        "challenge": (
            "Northwind ran a successful SEO agency for B2B SaaS clients but watched their pitch land flatter every quarter — "
            "prospects were starting to ask 'but what about AI search?' and Northwind didn't have a clean answer. Three retainers "
            "churned in Q3 alone, citing 'we need someone who handles AI visibility' as the reason."
        ),
        "solution": (
            "Northwind adopted VRT SPACE as the workspace for every client engagement. They started every audit with the screenshot "
            "showing that the client was invisible in ChatGPT for 8 of 10 target queries, while a named competitor was cited in 7 of them. "
            "That single image — paired with VRT's AI Visibility Score — became the centerpiece of every pitch. The team also "
            "tracked weekly share-of-voice progress and shared dashboard access with the client's CMO."
        ),
        "results": (
            "Within 90 days: 6 new retainers signed at an average of $8K/month MRR (totaling $48K). Churn dropped to zero in Q4. "
            "The team also reduced their reporting overhead from ~6 hours/week of manual spreadsheet work to ~30 minutes of reviewing "
            "VRT-generated dashboards. The founder cites the 'AI visibility before/after' screenshot as the single biggest sales tool "
            "they've ever used."
        ),
        "key_metric": "+$48K MRR in 90 days",
        "featured": True,
    },
    {
        "slug": "lumen-health-citations-jump",
        "title": "Lumen Health went from 0 to 79 AI Visibility Score in 6 weeks",
        "client_name": "Lumen Health",
        "industry": "Healthcare SaaS",
        "challenge": (
            "Lumen Health, a patient engagement platform for clinics, knew their content was solid but couldn't figure out why ChatGPT "
            "kept recommending Klara and Phreesia over them. They had no visibility into which queries they were winning, losing, or "
            "absent from — and their sales team was getting beat to consultations because prospects had already heard about competitors "
            "from AI."
        ),
        "solution": (
            "Lumen Health onboarded to VRT SPACE and added 5 high-intent prompts to their tracker: 'best patient engagement software for clinics', "
            "'HIPAA compliant patient reminder app', 'Lumen Health vs Klara', 'how to reduce patient no-shows with AI', and 'patient "
            "communication platform pricing'. The team also tracked Klara, Solv, Luma Health, and Phreesia as competitors. "
            "Within the first audit, VRT surfaced 3 specific fixes: missing FAQPage schema on their /security page, thin content on "
            "/pricing, and weak author bylines on their blog. They shipped all three fixes in two sprints."
        ),
        "results": (
            "After 6 weeks: AI Visibility Score went from 51 to 79. ChatGPT citations doubled (from 1 to 2 of 3 engines reliably "
            "citing them for the tracked prompts). Inbound consultation requests sourced from AI-referred traffic jumped 27%. "
            "Most importantly, in the 'Lumen Health vs Klara' query, Lumen Health now appears cited 100% of the time (up from "
            "0% at baseline)."
        ),
        "key_metric": "AI Visibility 51 → 79 in 6 weeks",
        "featured": True,
    },
    {
        "slug": "solo-studio-design-citations",
        "title": "How Solo Studio became the design partner ChatGPT recommends for early-stage SaaS",
        "client_name": "Solo Studio",
        "industry": "Creative agency",
        "challenge": (
            "Solo Studio, a 2-person Webflow + brand strategy shop, was getting drowned out by larger studios (Ueno, Ramotion, Studio Hooray) "
            "when SaaS founders asked AI 'who should I hire to design my SaaS marketing site?'. They had no marketing budget and "
            "couldn't outspend the competitors on backlinks."
        ),
        "solution": (
            "Solo Studio used VRT SPACE to track 3 specific queries and identify exactly which on-site signals were missing. "
            "VRT surfaced two issues: no FAQ schema on their /services page, and no E-E-A-T signals around their team (no author bios, "
            "no case study schema). The fix was a single afternoon's work — they added a FAQPage JSON-LD with 6 questions, plus "
            "a /about page with Person schema and real photos."
        ),
        "results": (
            "Within 4 weeks: appearing in 'best Webflow design studios for startups' (ChatGPT) at position 2-3 (previously not cited). "
            "Direct inbound from AI-referred founder traffic accounts for ~40% of their pipeline today. Solo Studio raised rates 30% "
            "since their work started being explicitly recommended by AI."
        ),
        "key_metric": "40% of pipeline from AI",
        "featured": False,
    },
]


# Word counting helper for reading time
def _word_count(html: str) -> int:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split()) if text else 0


class Command(BaseCommand):
    help = "Seed ship-ready blog articles + case studies for the public surface."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete seeded entries first.")

    def handle(self, *args, **options):
        if options["reset"]:
            Article.objects.filter(slug__in=[a["slug"] for a in ARTICLES]).delete()
            CaseStudy.objects.filter(slug__in=[c["slug"] for c in CASE_STUDIES]).delete()
            self.stdout.write("Reset complete.")

        now = timezone.now()
        for data in ARTICLES:
            payload = dict(data)
            days_ago = payload.pop("days_ago", 0)
            published_at = now - timedelta(days=days_ago)
            article, created = Article.objects.update_or_create(
                slug=payload["slug"],
                defaults={**payload, "published_at": published_at},
            )
            wc = _word_count(article.content)
            self.stdout.write(
                self.style.SUCCESS(f"OK {'created' if created else 'updated'}: {article.title}  ({wc} words)")
            )

        for data in CASE_STUDIES:
            cs, created = CaseStudy.objects.update_or_create(
                slug=data["slug"],
                defaults=data,
            )
            self.stdout.write(
                self.style.SUCCESS(f"OK {'created' if created else 'updated'} case study: {cs.title}")
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {Article.objects.filter(status=Article.Status.PUBLISHED).count()} published articles, "
            f"{CaseStudy.objects.count()} case studies."
        ))
