"""
AI Content Optimizer — scores any block of content for AI citation readiness.

The score is broken into 5 weighted dimensions, each with concrete fix advice
the user can act on. No API keys needed — the analysis runs on text features,
HTML structure, and proven heuristics derived from how ChatGPT / Gemini /
Perplexity actually surface answers.

Public function:
    optimize_content(*, content, target_query="", url="") -> dict
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse


# ── Tuning constants ──────────────────────────────────────────────────────

STOP = {
    "a", "an", "the", "in", "of", "for", "and", "or", "to", "at",
    "by", "with", "on", "is", "are", "be", "it", "its", "that",
    "this", "their", "from", "your", "our", "we", "us", "you",
    "as", "was", "were", "but", "if", "than", "then", "so",
}

ANSWER_FIRST_PATTERNS = [
    r"\bis\b",
    r"\bare\b",
    r"\bmeans?\b",
    r"\brefers? to\b",
    r"\bdefined as\b",
]

FACT_DENSITY_PATTERNS = [
    r"\b\d{1,4}(?:,\d{3})*(?:\.\d+)?\s?(?:%|percent|x|×|users?|customers?|kg|km|miles?|hours?|minutes?|seconds?|years?|months?|days?|dollars?|usd|eur|gbp)\b",
    r"\b\$\d[\d,]*(?:\.\d+)?\b",
    r"\b\d{4}\b",  # years
    r"\bvs\.?\b|\bversus\b|\bcompared (?:to|with)\b",
]

CITATION_PATTERNS = [
    r"\bhttps?://",
    r"\b(?:source|according to|study|research|report|survey)[:.\s]",
    r"\bcite[ds]?\b",
]

LISTICLE_PATTERNS = [
    r"^\s*[\-\*•]\s+",
    r"^\s*\d+[\).]\s+",
]


@dataclass
class Dimension:
    key: str
    label: str
    score: int  # 0..100
    weight: float
    findings: list[str]
    fixes: list[str]


# ── Helpers ────────────────────────────────────────────────────────────────


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in cleaned.split() if t and t not in STOP and len(t) >= 3]


def _strip_html(html: str) -> str:
    txt = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<style[^>]*>.*?</style>", "", txt, flags=re.DOTALL | re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def _has_html(content: str) -> bool:
    return bool(re.search(r"<\w+[^>]*>", content))


def _extract_headings(content: str) -> dict:
    if not _has_html(content):
        return {"h1": [], "h2": [], "h3": [], "any": []}
    return {
        "h1": [m.group(1).strip() for m in re.finditer(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)],
        "h2": [m.group(1).strip() for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", content, re.IGNORECASE | re.DOTALL)],
        "h3": [m.group(1).strip() for m in re.finditer(r"<h3[^>]*>(.*?)</h3>", content, re.IGNORECASE | re.DOTALL)],
        "any": re.findall(r"<h[1-6][^>]*>", content, re.IGNORECASE),
    }


def _has_faq_schema(content: str) -> bool:
    if not content:
        return False
    return bool(re.search(r'"@type"\s*:\s*"FAQPage"', content, re.IGNORECASE))


def _has_other_schema(content: str) -> bool:
    return bool(re.search(r'"@type"\s*:', content, re.IGNORECASE))


def _question_phrases(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip().endswith("?")]


# ── Dimension scorers ──────────────────────────────────────────────────────


def _score_answer_first(text: str, target_query: str) -> Dimension:
    findings = []
    fixes = []
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    intro = " ".join(sentences[:3])
    score = 30

    if not sentences:
        return Dimension("answer_first", "Answer-first structure", 0, 0.22, ["Content is empty."], ["Add at least one direct-answer paragraph."])

    if target_query:
        target_tokens = set(_tokens(target_query))
        intro_tokens = set(_tokens(intro))
        overlap = len(target_tokens & intro_tokens) / max(len(target_tokens), 1)
        if overlap >= 0.6:
            score += 35
            findings.append(f"Your opening covers {round(overlap * 100)}% of the target query terms.")
        else:
            findings.append(f"Only {round(overlap * 100)}% of the target query terms appear in your opening.")
            fixes.append(f"Mention the exact phrase '{target_query}' in the very first paragraph — AI engines surface answers from the lede.")
    else:
        score += 10

    # Direct-answer pattern in first 2 sentences
    for pat in ANSWER_FIRST_PATTERNS:
        if re.search(pat, intro, re.IGNORECASE):
            score += 10
            findings.append("Definition-style language detected in the opening — good for AI extraction.")
            break
    else:
        fixes.append("Open with a definition: \"X is …\", \"Y means …\", or \"Z refers to …\".")

    if len(sentences[0].split()) > 35:
        fixes.append("Shorten your first sentence to under 30 words — AI engines prefer crisp lede sentences.")
    else:
        score += 8

    if "?" in intro:
        score += 10
        findings.append("Question framing in the opening signals Q&A intent.")
    elif target_query:
        fixes.append(f"Restate the question — e.g. \"What is {target_query}? It's …\" — so AI can match Q→A.")

    return Dimension("answer_first", "Answer-first structure", min(score, 100), 0.22, findings, fixes)


def _score_structure(content: str, text: str) -> Dimension:
    findings = []
    fixes = []
    score = 25

    headings = _extract_headings(content)
    if not _has_html(content):
        # Markdown-style headings
        h_count = len(re.findall(r"^#{1,3}\s+", text, flags=re.MULTILINE))
        if h_count:
            score += 20
            findings.append(f"{h_count} markdown heading(s) detected.")
        else:
            fixes.append("Add clear H2/H3 headings to break content into scannable sections.")
    else:
        h_total = len(headings["any"])
        if h_total:
            score += min(h_total * 8, 32)
            findings.append(f"{h_total} HTML heading element(s) found.")
        else:
            fixes.append("Wrap section titles in <h2>/<h3> tags — AI engines key off heading hierarchy.")
        if headings["h1"]:
            score += 8
            findings.append(f"H1: \"{headings['h1'][0][:80]}\"")
        else:
            fixes.append("Add exactly one H1 with the target query phrased as a clear topic.")

    # Lists
    list_count = sum(1 for line in text.splitlines() for pat in LISTICLE_PATTERNS if re.match(pat, line))
    list_count += len(re.findall(r"<li[^>]*>", content, re.IGNORECASE))
    if list_count >= 4:
        score += 12
        findings.append(f"{list_count} list item(s) detected — AI loves structured data.")
    elif list_count == 0:
        fixes.append("Add a bullet or numbered list — ChatGPT and Perplexity extract list items directly.")

    # FAQ / Q&A blocks
    questions = _question_phrases(text)
    if len(questions) >= 3:
        score += 12
        findings.append(f"{len(questions)} question-style headings — strong Q&A structure.")
    elif len(questions) >= 1:
        score += 5
    else:
        fixes.append("Add 3–5 Q&A pairs answering related questions. Pair them with FAQPage JSON-LD schema.")

    if _has_faq_schema(content):
        score += 15
        findings.append("FAQPage JSON-LD schema detected — top-tier signal for ChatGPT.")
    else:
        fixes.append("Add FAQPage JSON-LD schema — typically a 15–25 point boost for ChatGPT citations.")

    return Dimension("structure", "Structural clarity", min(score, 100), 0.22, findings, fixes)


def _score_entity_signals(text: str, content: str, url: str, target_query: str) -> Dimension:
    findings = []
    fixes = []
    score = 30

    # Named entity proxy: capitalised multi-word phrases
    proper = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text)
    proper_unique = {p for p in proper if p.lower() not in {"the", "a", "an"}}
    if len(proper_unique) >= 6:
        score += 18
        findings.append(f"{len(proper_unique)} named entities detected.")
    elif len(proper_unique) < 2:
        fixes.append("Name specific people, places, brands, and products — entity-dense content gets cited more often.")

    if _has_other_schema(content):
        score += 18
        findings.append("Structured data (JSON-LD) detected.")
    else:
        fixes.append("Add JSON-LD schema (Organization, Article, Product, or LocalBusiness) so AI can identify the entity.")

    # Author signal
    if re.search(r"\b(?:by|author|written by)\s+[A-Z]", text):
        score += 8
        findings.append("Author byline detected.")
    else:
        fixes.append("Add a visible author byline + bio. Gemini specifically uses author signals for E-E-A-T.")

    # Domain/URL signal
    if url:
        try:
            domain = urlparse(url).netloc or url
            if domain:
                score += 8
                findings.append(f"Source domain: {domain}")
        except Exception:
            pass

    if target_query:
        target_tokens = set(_tokens(target_query))
        text_tokens = set(_tokens(text))
        coverage = len(target_tokens & text_tokens) / max(len(target_tokens), 1)
        if coverage >= 0.8:
            score += 12
        elif coverage >= 0.5:
            score += 6
        else:
            fixes.append(f"Cover all the keywords in '{target_query}' more thoroughly — entity-keyword match is weak.")

    return Dimension("entity", "Entity & authority signals", min(score, 100), 0.20, findings, fixes)


def _score_depth(text: str) -> Dimension:
    findings = []
    fixes = []
    words = text.split()
    wc = len(words)
    score = 20

    if wc >= 1200:
        score += 40
        findings.append(f"{wc} words — excellent depth for Perplexity.")
    elif wc >= 800:
        score += 32
        findings.append(f"{wc} words — strong depth.")
    elif wc >= 500:
        score += 22
        findings.append(f"{wc} words — moderate depth.")
    elif wc >= 300:
        score += 12
        findings.append(f"{wc} words — content is thin.")
        fixes.append("Expand to at least 600 words. Perplexity favours fact-dense, deep content.")
    else:
        findings.append(f"Only {wc} words — too thin for confident AI citation.")
        fixes.append("Expand to 600+ words. Add sections: definition, how-it-works, examples, FAQ.")

    # Vocabulary diversity proxy
    tokens = _tokens(text)
    if tokens:
        diversity = len(set(tokens)) / len(tokens)
        if diversity >= 0.45:
            score += 10
            findings.append(f"Vocabulary diversity: {round(diversity * 100)}% — good topical coverage.")
        elif diversity < 0.25:
            fixes.append("Vocabulary is repetitive — add varied synonyms and related sub-topics.")

    return Dimension("depth", "Content depth", min(score, 100), 0.18, findings, fixes)


def _score_fact_density(text: str, content: str) -> Dimension:
    findings = []
    fixes = []
    score = 25

    fact_hits = 0
    for pat in FACT_DENSITY_PATTERNS:
        fact_hits += len(re.findall(pat, text, re.IGNORECASE))

    citation_hits = 0
    for pat in CITATION_PATTERNS:
        citation_hits += len(re.findall(pat, text, re.IGNORECASE))
    citation_hits += len(re.findall(r"<a [^>]*href=", content, re.IGNORECASE))

    if fact_hits >= 8:
        score += 35
        findings.append(f"{fact_hits} fact markers (numbers, dates, comparisons) — Perplexity loves this.")
    elif fact_hits >= 3:
        score += 18
        findings.append(f"{fact_hits} fact markers detected.")
    else:
        fixes.append("Add specific numbers, dates, dollar amounts, percentages — fact-dense content gets cited more.")

    if citation_hits >= 4:
        score += 25
        findings.append(f"{citation_hits} citation/link signals — authoritative.")
    elif citation_hits >= 1:
        score += 12
    else:
        fixes.append("Cite sources (with linked references). Perplexity specifically scores by linked authority.")

    # Quotes/blockquotes
    if re.search(r"<blockquote", content, re.IGNORECASE) or text.count('"') >= 4:
        score += 8
        findings.append("Direct quotes detected — supports AI extraction.")

    return Dimension("fact_density", "Fact density & citations", min(score, 100), 0.18, findings, fixes)


# ── Engine-specific projections ────────────────────────────────────────────


def _engine_projections(score: int, dimensions: list[Dimension]) -> list[dict]:
    by_key = {d.key: d.score for d in dimensions}
    weights = {
        "ChatGPT": {"answer_first": 0.30, "structure": 0.30, "entity": 0.18, "depth": 0.12, "fact_density": 0.10},
        "Gemini": {"entity": 0.32, "structure": 0.26, "answer_first": 0.18, "depth": 0.12, "fact_density": 0.12},
        "Perplexity": {"fact_density": 0.32, "depth": 0.26, "entity": 0.16, "answer_first": 0.14, "structure": 0.12},
    }
    colors = {"ChatGPT": "#10a37f", "Gemini": "#4285f4", "Perplexity": "#a855f7"}
    threshold = 65
    out = []
    for engine, weight_map in weights.items():
        proj = sum(by_key.get(k, 0) * w for k, w in weight_map.items())
        proj = round(proj)
        out.append({
            "engine": engine,
            "color": colors[engine],
            "score": proj,
            "threshold": threshold,
            "would_cite": proj >= threshold,
            "gap": max(0, threshold - proj),
        })
    return out


# ── Public entry point ─────────────────────────────────────────────────────


def optimize_content(*, content: str, target_query: str = "", url: str = "") -> dict:
    """Returns a full optimization report for a piece of content."""
    if not content or not content.strip():
        return {
            "ok": False,
            "error": "No content provided.",
        }

    text = _strip_html(content) if _has_html(content) else content

    dims = [
        _score_answer_first(text, target_query),
        _score_structure(content, text),
        _score_entity_signals(text, content, url, target_query),
        _score_depth(text),
        _score_fact_density(text, content),
    ]

    composite = round(sum(d.score * d.weight for d in dims))
    composite = max(0, min(composite, 100))

    if composite >= 80:
        grade = "A"
        verdict = "Strong AI citation candidate. Ship and monitor."
    elif composite >= 65:
        grade = "B"
        verdict = "Decent foundation — close the listed gaps and you'll get cited consistently."
    elif composite >= 50:
        grade = "C"
        verdict = "Moderate readiness. Several high-impact fixes available."
    elif composite >= 35:
        grade = "D"
        verdict = "Low readiness. Major structural gaps blocking AI citation."
    else:
        grade = "F"
        verdict = "Unlikely to be cited as-is. Rewrite with answer-first structure and depth."

    # Collect top fixes, prioritised by dimension impact
    prioritised_fixes = []
    for d in sorted(dims, key=lambda dim: (dim.score, -dim.weight)):
        for fix in d.fixes:
            prioritised_fixes.append({"category": d.label, "fix": fix})

    return {
        "ok": True,
        "composite_score": composite,
        "grade": grade,
        "verdict": verdict,
        "word_count": len(text.split()),
        "target_query": target_query,
        "url": url,
        "dimensions": [
            {
                "key": d.key,
                "label": d.label,
                "score": d.score,
                "weight_pct": round(d.weight * 100),
                "findings": d.findings,
                "fixes": d.fixes,
            }
            for d in dims
        ],
        "engine_projections": _engine_projections(composite, dims),
        "top_fixes": prioritised_fixes[:8],
    }
