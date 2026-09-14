#!/usr/bin/env python3
"""Engagement Audit — merged with element-stack context."""

import json
import os
import re
import sys
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from utils import create_finding, safe_fetch, parse_html_content
from ner import has_named_entity, has_quantity, extract_entities


GENERIC_OPENERS = re.compile(
    r"^\s*(welcome|we are|we're|our company|our team|at\s+[A-Z][a-z]+,\s+we|"
    r"introducing|discover\s+how|learn\s+more|read\s+on|explore)",
    re.IGNORECASE,
)
_MECHANISM_BY_ID = {
    "ENG-001": "template",
    "ENG-002": "template",
    "ENG-003": "template",
    "ENG-004": "content",
    "ENG-005": "content",
    "ENG-006": "architectural",
    "ENG-007": "template",
    "ENG-008": "content",
    "ENG-009": "content",
}
_CTA_RE = re.compile(
    r"\b(buy now|get started|sign up|try free|start free|try it free|"
    r"contact us|get in touch|book now|book a demo|request a demo|"
    r"schedule a demo|schedule demo|learn more|download|subscribe|"
    r"apply now|get a quote|talk to sales|talk to us|see pricing|"
    r"start trial|start your trial|create account|create an account|"
    r"register|join now|join free|request access|request info)\b",
    re.IGNORECASE,
)


def _is_deep_anchor(href):
    if not href:
        return False
    if href.startswith("#"):
        return False
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return False
    if href.startswith("?"):
        return False
    return True


def check_engagement(target_url):
    findings = []
    res = safe_fetch(target_url)
    if res["status"] != 200 or not res["body"]:
        return findings

    parser = parse_html_content(res["body"])

    # Main-content-only views (exclude nav/footer/aside).
    body_paras = [p for p in parser.paragraphs
                  if not (p["in_nav"] or p["in_footer"] or p["in_aside"])]
    body_anchors = [a for a in parser.anchors
                    if not (a["in_nav"] or a["in_footer"])]
    headings = parser.headings

    # ENG-001 — heading id coverage
    no_ids = [h for h in headings if "id" not in (h.get("attrs") or {})]
    if headings and len(no_ids) == len(headings):
        findings.append(create_finding(
            finding_id="ENG-001",
            title="Complete Absence of Section Identifier Anchors",
            severity="low",
            evidence=f"All {len(headings)} heading elements lack 'id' attributes.",
            summary="Add id attributes to structural headings (h1-h4) so AI systems can deep-link citations.",
            impact="AI models cannot generate citation links to specific sections.",
            code_snippet='<h2 id="specifications">Specifications</h2>',
        ))

    # ENG-002 — h1 presence
    if not any(h["tag"] == "h1" for h in headings):
        findings.append(create_finding(
            finding_id="ENG-002",
            title="Missing Primary Heading (<h1>)",
            severity="medium",
            evidence="Document contains no <h1> element.",
            summary="Add a descriptive <h1> naming the primary entity/topic.",
            impact="AI agents cannot determine the page's primary subject.",
            code_snippet="<h1>Brand Product Name</h1>",
        ))

    # ENG-003 — citation-ready anchors on fact-bearing headings
    fact_headings, id_headings = 0, 0
    for h in headings:
        if h["tag"] in ("h2", "h3", "h4") and re.search(r"\d", h["text"]):
            fact_headings += 1
            if "id" in (h.get("attrs") or {}):
                id_headings += 1
    if fact_headings >= 2 and (id_headings / fact_headings) < 0.30:
        findings.append(create_finding(
            finding_id="ENG-003",
            title="Citation-Ready Anchor Deficit on Fact-Bearing Headings",
            severity="medium",
            evidence=f"{fact_headings - id_headings} of {fact_headings} fact-bearing headings lack an id anchor.",
            summary="Add id attributes to every heading preceding numeric facts.",
            impact="AI cannot construct deep-link citations to specific claim sections.",
            code_snippet='<h2 id="pricing-2026">Pricing 2026</h2>',
        ))

    # ENG-004 — quotable answer paragraph
    best = None
    for p in body_paras[:25]:
        text = p["text"]
        if 40 <= p["word_count"] <= 90 \
           and has_quantity(text) and has_named_entity(text):
            best = text
            break
    if best is None and len(body_paras) >= 3:
        findings.append(create_finding(
            finding_id="ENG-004",
            title="No Quotable Answer Paragraph Detected",
            severity="high",
            evidence=f"Scanned {min(len(body_paras), 25)} body paragraphs; none matched 40-90 words with entity + quantity.",
            summary="Author a 40-90 word paragraph near the top combining the brand entity with key quantified facts.",
            impact="AI summarizers have no clean extractable block to quote.",
            code_snippet="<p>Nike's Air Zoom Pegasus 40 weighs 283 g and retails for $129.99 in 2026.</p>",
        ))

    # ENG-005 — above-fold density
    af_raw = "".join(parser.above_fold_text)
    af_text = re.sub(r"\s+", " ", af_raw).strip()
    af_words = af_text.split()
    af_q = 1 if has_quantity(af_text) else 0
    af_entities = len({e["text"] for e in extract_entities(af_text)})
    if len(af_words) >= 30 and af_q == 0 and af_entities < 3:
        findings.append(create_finding(
            finding_id="ENG-005",
            title="Above-the-Fold Fact Density Deficit",
            severity="medium",
            evidence=f"First ~2000 chars: {len(af_words)} words, {af_q} quantified facts, {af_entities} distinct entities.",
            summary="Place at least one quantified fact and the brand's primary entity in the first ~2000 chars.",
            impact="AI crawlers that score above-the-fold content miss core quantified claims.",
            code_snippet="<p>Acme Pro Plan starts at $29/month for 5 users.</p>",
        ))

    # ENG-006 — AI-referrer handling
    ai_refs = ("chatgpt.com", "chat.openai.com", "perplexity.ai", "claude.ai",
               "copilot.microsoft.com", "gemini.google.com", "you.com")
    lower = res["body"].lower()
    has_ref_code = ("document.referrer" in lower
                or any(r in lower for r in ai_refs))
    deep = sum(1 for a in body_anchors if _is_deep_anchor(a.get("href", "")))
    is_landing = deep < 5 and len(headings) <= 6
    if is_landing and not has_ref_code:
        findings.append(create_finding(
            finding_id="ENG-006",
            title="No AI-Referrer Context Handling Detected",
            severity="medium",
            evidence=f"Landing structure ({deep} deep anchors, {len(headings)} headings) with no document.referrer handling.",
            summary="Detect AI-referred traffic (chatgpt.com, perplexity.ai, claude.ai) at the edge or via JS and preserve query context.",
            impact="Visitors from AI citations land on a generic page with no context continuity.",
            code_snippet="if (document.referrer.includes('chatgpt.com')) { showContextBanner(); }",
        ))

    # ENG-007 — next-action affordance
    has_form = len(parser.forms) > 0
    has_search = any(
        any(inp.get("type") in ("search", "text")
            and ("search" in inp.get("name", "").lower()
                 or "search" in inp.get("placeholder", "").lower()
                 or "query" in inp.get("name", "").lower())
            for inp in form.get("inputs", []))
        for form in parser.forms
    )
    has_cta_a = any(_CTA_RE.search(a.get("text", "")) for a in parser.anchors)
    has_cta_h = any(_CTA_RE.search(h["text"] or "") for h in headings)
    if not (has_form or has_search or has_cta_a or has_cta_h):
        findings.append(create_finding(
            finding_id="ENG-007",
            title="No Next-Action Affordance Detected",
            severity="medium",
            evidence=f"0 forms, 0 search inputs, 0 CTA anchors/headings ({len(parser.anchors)} anchors scanned).",
            summary="Add at least one explicit next-action (form, search box, or CTA).",
            impact="AI-referred visitors have no obvious next step.",
            code_snippet='<a href="/pricing" class="cta">Get started free</a>',
        ))

    # ENG-008 — answer-first section structure
    total, weak, examples = 0, 0, []
    for sec in parser.section_openings:
        opening = (sec.get("first_para") or "").strip()
        if not opening:
            continue
        total += 1
        first30 = " ".join(opening.split()[:30])
        has_q = has_quantity(first30)
        has_e = has_named_entity(first30)
        generic = bool(GENERIC_OPENERS.match(first30))
        if not (has_q and has_e and not generic):
            weak += 1
            if len(examples) < 2:
                tag = sec.get("heading_tag", "h2")
                examples.append(
                    f"<{tag}>{sec.get('heading','')[:40]!r}</{tag}> -> {first30[:70]!r}"
                )
    if total >= 3 and (weak / total) >= 0.6:
        findings.append(create_finding(
            finding_id="ENG-008",
            title="Sections Do Not Open With Direct Answers",
            severity="high",
            evidence=f"{weak}/{total} section openers lack entity+quantity in first 30 words. Examples: {' | '.join(examples) or 'n/a'}.",
            summary="Rewrite each section's first sentence to state the primary answer before framing language.",
            impact="GEO pipelines quote the first sentence; generic openers yield zero extractable facts.",
            code_snippet='<h2>Pricing</h2>\n<p>Acme Pro costs $29/month for 5 users and includes API access.</p>',
        ))

    # ENG-009 — citation density (body only)
    cit = 0
    for p in body_paras:
        if 40 <= p["word_count"] <= 90 \
           and has_quantity(p["text"]) and has_named_entity(p["text"]):
            cit += 1
    total_words = sum(p["word_count"] for p in body_paras)
    if total_words >= 300:
        density = (cit / total_words) * 1000.0
        if density < 2.0:
            findings.append(create_finding(
                finding_id="ENG-009",
                title="Low Citation Density",
                severity="high",
                evidence=f"{cit} citation-grade paragraph(s) across {total_words} body words → {density:.2f} per 1000 (target >= 2.0).",
                summary="Add 1-2 citation-grade paragraphs per major section: 40-90 words with an entity and a quantified fact.",
                impact="Low citation density gives AI summarizers almost nothing quotable.",
                code_snippet="<p>Acme Pro costs $29/month for 5 users, includes 100 GB storage.</p>",
            ))

    for f in findings:
        f["mechanism"] = _MECHANISM_BY_ID.get(f.get("id"), "content")
    return findings


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_engagement(target), indent=2))