#!/usr/bin/env python3
"""Discovery Audit — merged: seen_agents robots, iterative walkers, v2.4 checks."""

import json
import os
import re
import sys
import urllib.parse
from collections import defaultdict


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")

for _p in (SCRIPT_DIR, SHARED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils import (
    create_finding,
    safe_fetch,
    parse_html_content,
    extract_visible_text,
    get_robots,
    path_matches as _path_matches,
)


_MECHANISM_BY_ID = {
    "DISC-001":  "config",
    "DISC-001b": "config",
    "DISC-002":  "config",
    "DISC-003":  "content",
    "DISC-004":  "architectural",
    "DISC-005":  "content",
    "DISC-007":  "config",
    "DISC-010":  "config",
    "DISC-011":  "content",
    "DISC-012":  "template",
    "DISC-013":  "template",
    "DISC-014":  "template",
    "DISC-015":  "content",
    "DISC-016":  "content",
    "DISC-017":  "config",
    "DISC-018":  "config",        # often a CDN/WAF rule
    "DISC-019":  "config",
    "DISC-020":  "template",
    "DISC-021t": "template",
    "DISC-021d": "template",
    "DISC-021i": "template",
    "DISC-023":  "content",
}

AI_BOT_UA_PROBES = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); "
              "compatible; GPTBot/1.0; +https://openai.com/gptbot",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); "
                 "compatible; ClaudeBot/1.0; +claudebot@anthropic.com",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); "
                     "compatible; PerplexityBot/1.0; "
                     "+https://perplexity.ai/perplexitybot",
}

AI_BOTS = ("gptbot", "claudebot", "perplexitybot", "anthropic-ai", "cohere-ai")
CONVERSATIONAL_TYPES = {"faqpage", "qapage", "howto", "question", "answer"}
NEWS_ARTICLE_TYPES = {"newsarticle", "article", "blogposting",
                      "reportagenewsarticle"}


# ── robots helpers ──
def _blocks_root(rules):
    for r in rules:
        if r.strip() in ("/", "/*", "*"):
            return True
    return False


def _parse_robots(body):
    """
    Returns (rules_by_agent, seen_agents, sitemaps).
    `seen_agents` records every User-agent token that appears, even if the
    group has no directives — distinguishes 'explicit empty block → allow'
    from 'no block → inherit from *'.
    """
    rules = defaultdict(lambda: {"disallow": [], "allow": []})
    seen_agents = set()
    sitemaps = []
    current_agents = []
    in_directives = False

    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()

        if key == "user-agent":
            if in_directives:
                current_agents = []
                in_directives = False
            if value:
                agents = [a.strip().lower() for a in value.split(",") if a.strip()]
                current_agents.extend(agents)
                seen_agents.update(agents)
        elif key in ("disallow", "allow") and current_agents:
            in_directives = True
            for agent in current_agents:
                rules[agent][key].append(value)
        elif key == "sitemap" and value:
            sitemaps.append(value)

    return dict(rules), seen_agents, sitemaps


def _ua_blocked_for_bot(bot_name, rules_by_agent, seen_agents):
    """True if robots.txt explicitly disallows this bot at root."""
    if not rules_by_agent and not seen_agents:
        return False
    bot_key = bot_name.lower()
    if bot_key in seen_agents:
        bot_rules = rules_by_agent.get(bot_key, {"disallow": [], "allow": []})
    else:
        bot_rules = rules_by_agent.get("*", {"disallow": [], "allow": []})
    return _blocks_root(bot_rules["disallow"]) and not _blocks_root(bot_rules["allow"])


def _probe_with_ua(url, ua, timeout=6):
    """One-shot GET with a custom UA. Does not consult the response cache.

    Reads up to 1 MB — matches the baseline fetch in check_discovery so that
    DISC-019's body-length comparison is meaningful on large pages.
    """
    import urllib.request
    import urllib.error
    import ssl as _ssl
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        ctx = _ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = r.read(1024 * 1024).decode("utf-8", errors="replace")
            return {"status": r.status, "body_len": len(body)}
    except urllib.error.HTTPError as he:
        return {"status": he.code, "body_len": 0}
    except Exception:
        return {"status": 0, "body_len": 0}


# ── JSON-LD iterative walkers ──
def _iter_json_ld(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, dict):
            for v in current.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(current, list):
            stack.extend(x for x in current if isinstance(x, (dict, list)))


def _has_type_bounded(parser, type_set, max_depth=2):
    """Depth-bounded @type detection. Lists do NOT increment depth."""
    def walk(root):
        stack = [(root, 0)]
        while stack:
            node, depth = stack.pop()
            if depth > max_depth:
                continue
            if isinstance(node, dict):
                stype = node.get("@type", "")
                strs = ([str(t).lower() for t in stype]
                        if isinstance(stype, list)
                        else [str(stype).lower()])
                if any(t in type_set for t in strs):
                    return True
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        stack.append((v, depth + 1))
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        stack.append((item, depth))

    return any(walk(b) for b in parser.json_ld_blocks)


# ── img-metadata helpers (module scope for testing) ──
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_IMG_ATTR_RE = re.compile(
    r'\s(alt|title|aria-label)\s*=\s*["\']([^"\']*)["\']',
    re.IGNORECASE,
)

_NUM_FACT_PATTERNS = [
    re.compile(r"(\d[\d,.]*)\s*(?:₹|\$|€|£|¥|kg|g|cm|mm|m|km|%|"
               r"gb|tb|mb|kb|mbps|gbps|ghz|mhz|"
               r"users?|seats?|devices?|years?|months?|days?|hours?|"
               r"warranty|sq\.?\s*ft|sq\.?\s*m|lakh|crore)", re.IGNORECASE),
    re.compile(r"(?:₹|\$|€|£|¥)\s*(\d[\d,.]*)"),
    re.compile(r"\b(\d[\d,.]*)\s*[x×]\s*(\d[\d,.]*)"),  # dimensions
]


def extract_img_metadata(html):
    out = []
    for tag in _IMG_TAG_RE.finditer(html):
        attrs = {}
        for m in _IMG_ATTR_RE.finditer(tag.group(0)):
            attrs[m.group(1).lower()] = m.group(2)
        if attrs:
            out.append(attrs)
    return out


def number_in_visible(num_str, visible_text):
    """Match a digit-run regardless of thousands separators.

    Both sides are normalized: `num_str` is already comma-stripped by
    `_extract_number_and_unit`; the visible text has commas removed only
    in digit contexts (not in prose) to avoid corrupting word boundaries."""
    if not num_str:
        return True
    # Strip thousands separators only between digits: "1,299.99" -> "1299.99".
    visible_digits = re.sub(r"(?<=\d),(?=\d{3}\b)", "", visible_text)
    return bool(re.search(
        r"(?<!\d)" + re.escape(num_str) + r"(?!\d)",
        visible_digits,
    ))


def _extract_number_and_unit(value):
    for pat in _NUM_FACT_PATTERNS:
        m = pat.search(value)
        if m:
            return m.group(1).replace(",", "").rstrip(".")
    return None


def _is_plain_text(content_type):
    ct = (content_type or "").lower()
    if not ct:
        return False
    if "html" in ct or "xml" in ct or "json" in ct:
        return False
    return ct.startswith("text/")


# ── main check ──
def check_discovery(target_url):
    findings = []
    parsed = urllib.parse.urlparse(target_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # 1. /llms.txt
    llms_url = f"{base}/llms.txt"
    llms_res = safe_fetch(llms_url)
    ct = llms_res.get("headers", {}).get("content-type", "").lower()

    if llms_res["status"] != 200 or not llms_res["body"].strip():
        findings.append(create_finding(
            finding_id="DISC-001",
            title="Missing Machine-Readable /llms.txt Endpoint",
            severity="high",
            evidence=f"GET {llms_url} returned HTTP status {llms_res['status'] or 'FAILED'}",
            summary="Deploy an /llms.txt file providing clean Markdown context for LLM agents.",
            impact="Improves RAG parsing efficiency for AI assistants like Perplexity and ChatGPT.",
            code_snippet="# Brand Context\n> Summary...\n\n## Key Documents\n- [Catalog](/catalog.md)",
        ))
    elif not _is_plain_text(ct):
        findings.append(create_finding(
            finding_id="DISC-001b",
            title="Invalid Content-Type for /llms.txt Endpoint",
            severity="high",
            evidence=f"GET {llms_url} returned HTTP 200 but Content-Type: {ct or 'unspecified'}",
            summary="Serve /llms.txt with Content-Type: text/plain or text/markdown.",
            impact="RAG agents treat the payload as markup rather than plain text.",
            code_snippet="Content-Type: text/plain; charset=utf-8",
        ))

    # 2. /llms-full.txt
    if llms_res["status"] == 200:
        lf = safe_fetch(f"{base}/llms-full.txt")
        if lf["status"] != 200:
            findings.append(create_finding(
                finding_id="DISC-010",
                title="Missing /llms-full.txt Companion Index",
                severity="low",
                evidence=f"GET {base}/llms-full.txt returned HTTP {lf['status'] or 'FAILED'}",
                summary="Publish /llms-full.txt with expanded content for deeper RAG ingestion.",
                impact="Provides AI systems a deeper index for citation-level retrieval.",
                code_snippet="# Full Brand Index\n> Extended content...",
            ))

    # 3. robots.txt (per-bot, correct empty-block semantics)
    # max_bytes matches RobotsPolicy.load's fetch so both callers share a
    # single cache entry — one /robots.txt request per audit run.
    robots_res = safe_fetch(f"{base}/robots.txt", max_bytes=256 * 1024)
    rules_by_agent = {}
    seen_agents = set()
    if robots_res["status"] == 200 and robots_res["body"]:
        rules_by_agent, seen_agents, _ = _parse_robots(robots_res["body"])

        for bot in AI_BOTS:
            if bot in seen_agents:
                bot_rules = rules_by_agent.get(bot, {"disallow": [], "allow": []})
                via_wildcard = False
            else:
                bot_rules = rules_by_agent.get("*", {"disallow": [], "allow": []})
                via_wildcard = True
            if _blocks_root(bot_rules["disallow"]) and not _blocks_root(bot_rules["allow"]):
                label = f"{bot} (via wildcard '*')" if via_wildcard else bot
                findings.append(create_finding(
                    finding_id="DISC-002",
                    title="AI Crawler Blocked in robots.txt",
                    severity="critical",
                    evidence=f"User-agent '{label}' is disallowed from root '/' access.",
                    summary=f"Remove the root Disallow rule for {bot} to allow AI indexing.",
                    impact="Prevents ChatGPT, Claude, and Perplexity from indexing brand facts.",
                    code_snippet="User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /",
                ))

    # 4. Main page
    main_res = safe_fetch(target_url)
    if main_res["status"] == 200:
        html = main_res["body"]
        parser = parse_html_content(html)
        visible = " ".join("".join(parser.visible_text).split())
        word_count = len(visible.split())

        # 4a. Brand/Organization JSON-LD (bounded)
        if not _has_type_bounded(parser, {"brand", "organization"}, max_depth=2):
            # Report what WAS found, not just what's missing.
            found_types = set()
            for block in parser.json_ld_blocks:
                for node in _iter_json_ld(block):
                    if isinstance(node, dict):
                        t = node.get("@type", "")
                        if isinstance(t, list):
                            found_types.update(str(x) for x in t)
                        elif t:
                            found_types.add(str(t))
            found_str = (", ".join(sorted(found_types))[:100]
                         if found_types else "none")
            findings.append(create_finding(
                finding_id="DISC-003",
                title="Missing Schema.org Entity Metadata (Brand/Organization JSON-LD)",
                severity="high",
                evidence=(
                    f"Found JSON-LD types: [{found_str}]. No Brand or "
                    f"Organization node → entity resolution has no anchor."
                ),
                summary="Embed structured Schema.org JSON-LD to assist entity resolution.",
                impact="Helps AI crawlers extract authoritative entity relationships.",
                code_snippet='<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"BrandName","url":"https://example.com"}</script>',
            ))

        # 4b. WebSite + SearchAction (iterative)
        has_search = False
        for block in parser.json_ld_blocks:
            for node in _iter_json_ld(block):
                if not isinstance(node, dict):
                    continue
                t = node.get("@type", "")
                ts = (" ".join(str(x) for x in t).lower()
                      if isinstance(t, list) else str(t).lower())
                if ts == "website":
                    pa = node.get("potentialAction")
                    if isinstance(pa, dict) and "searchaction" in str(pa.get("@type", "")).lower():
                        has_search = True
                        break
            if has_search:
                break
        if not has_search:
            findings.append(create_finding(
                finding_id="DISC-011",
                title="Missing WebSite + SearchAction JSON-LD",
                severity="medium",
                evidence="No JSON-LD block declares @type WebSite with potentialAction SearchAction.",
                summary="Add WebSite + SearchAction JSON-LD so AI systems can cite a canonical search entry point.",
                impact="Enables AI agents to deep-link query-specific URLs rather than the homepage.",
                code_snippet='{"@type":"WebSite","url":"https://example.com","potentialAction":{"@type":"SearchAction","target":"https://example.com/search?q={query}"}}',
            ))

        # 4c. meta robots noindex
        meta_rb = parser.meta_tags.get("robots", "").lower()
        if "noindex" in meta_rb or meta_rb.strip() == "none":
            findings.append(create_finding(
                finding_id="DISC-012",
                title="Meta robots noindex Directive Found",
                severity="critical",
                evidence=f'<meta name="robots" content="{parser.meta_tags.get("robots")}"> blocks indexing.',
                summary="Remove the noindex directive from pages that must remain discoverable.",
                impact="Prevents all search engines and AI assistants from indexing this page.",
                code_snippet='<meta name="robots" content="index, follow">',
            ))

        # 4c2. Canonical URL declaration.
        canonical = None
        for link in re.findall(
            r'<link\b[^>]*\brel\s*=\s*["\']canonical["\'][^>]*>',
            html, re.IGNORECASE,
        ):
            m = re.search(r'\bhref\s*=\s*["\']([^"\']+)["\']', link, re.IGNORECASE)
            if m:
                canonical = m.group(1)
                break
        if not canonical:
            findings.append(create_finding(
                finding_id="DISC-020",
                title="Missing <link rel='canonical'> on Landing Page",
                severity="medium",
                evidence="No canonical URL declaration found in <head>.",
                summary=(
                    "Add <link rel='canonical' href='...'> to every indexable "
                    "page. Without it, AI assistants may cite a parameterized "
                    "or duplicated URL variant."
                ),
                impact=(
                    "Citations and ranking signals are diluted across URL "
                    "variants; AI assistants may link to the wrong page."
                ),
                code_snippet='<link rel="canonical" href="https://example.com/page">',
            ))

        # 4c3. og:title / og:description / og:image presence.
        for prop, severity, label, fid_suffix in (
            ("og:title",       "low",    "Open Graph title",       "t"),
            ("og:description", "medium", "Open Graph description", "d"),
            ("og:image",       "low",    "Open Graph image",       "i"),
        ):
            if not parser.meta_tags.get(prop):
                findings.append(create_finding(
                    finding_id=f"DISC-021{fid_suffix}",
                    title=f"Missing {label} (property='{prop}')",
                    severity=severity,
                    evidence=f'<meta property="{prop}"> not present.',
                    summary=(
                        f"Add {prop} to every indexable page. AI summarizers "
                        f"and social/LLM preview surfaces consume OG metadata "
                        f"as the shortest representation of the page."
                    ),
                    impact=(
                        "Without OG metadata, AI summarizers fall back to "
                        "arbitrary text extraction, often producing off-topic "
                        "summaries of the page."
                    ),
                    code_snippet=f'<meta property="{prop}" content="...">',
                ))

        # 4d. malformed JSON-LD
        if parser.json_ld_malformed > 0:
            findings.append(create_finding(
                finding_id="DISC-017",
                title="Malformed JSON-LD Structured Data",
                severity="medium",
                evidence=f'{parser.json_ld_malformed} <script type="application/ld+json"> block(s) failed to parse.',
                summary="Validate JSON-LD syntax and repair each block.",
                impact="Malformed blocks are silently ignored; the intended schema has zero effect.",
                code_snippet='<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization"}</script>',
            ))

        # 4d2. @graph nodes with unresolved @id references.
        unresolved = 0
        for block in parser.json_ld_blocks:
            if not isinstance(block, dict):
                continue
            graph = block.get("@graph")
            if not isinstance(graph, list):
                continue
            ids = {n.get("@id") for n in graph
                   if isinstance(n, dict) and n.get("@id")}
            for node in graph:
                if not isinstance(node, dict):
                    continue
                for v in node.values():
                    if isinstance(v, dict) and "@id" in v and v["@id"] not in ids:
                        unresolved += 1
        if unresolved > 0:
            findings.append(create_finding(
                finding_id="DISC-023",
                title="JSON-LD @graph Contains Unresolved @id References",
                severity="low",
                evidence=f"{unresolved} @id reference(s) do not resolve to a node in the same graph.",
                summary=(
                    "Either inline the referenced node or ensure the @id "
                    "target is present in the same @graph array."
                ),
                impact=(
                    "AI entity resolvers may fail to link related nodes, "
                    "weakening the entity signal."
                ),
                code_snippet='{"@graph":[{"@id":"#brand","@type":"Brand"}]}',
            ))

        # 4e. JS-render gap
        try:
            from render_diff import render_dom, text_length_ratio
        except ImportError as e:
            sys.stderr.write(f"render_diff unavailable: {e}\n")
            render_dom, text_length_ratio = None, None

        rr = (render_dom(target_url) if render_dom
              else {"ok": False, "error": "renderer unavailable"})

        if rr.get("ok") and text_length_ratio:
            rendered = extract_visible_text(rr["html"])
            r_len, raw_len, ratio = text_length_ratio(visible, rendered)
            gained = r_len - raw_len
            if gained > 500 and ratio > 1.6:
                findings.append(create_finding(
                    finding_id="DISC-004",
                    title="JavaScript-Render Gap (Content Hidden from Non-JS Crawlers)",
                    severity="critical",
                    evidence=f"Raw HTML visible text: {raw_len} chars. Post-hydration: "
                             f"{r_len} chars (+{gained}, ratio {ratio:.2f}).",
                    summary="Server-render (SSR) or statically generate (SSG) primary facts.",
                    impact="AI crawlers that fetch raw HTML cannot see key facts.",
                    code_snippet="<!-- Ensure primary facts appear in server HTML -->",
                ))
        else:
            script_count = len(parser.scripts)
            has_noscript = bool(re.search(r"<noscript\b[^>]*>", html, re.IGNORECASE))
            has_mount = ('<div id="root"' in html.lower()) or ('<div id="app"' in html.lower())
            if len(visible) < 150 and script_count >= 5 and (has_noscript or has_mount):
                findings.append(create_finding(
                    finding_id="DISC-004",
                    title="Possible JavaScript-Only Content Wall",
                    severity="high",
                    evidence=f"Raw visible text {len(visible)} chars; {script_count} scripts; "
                             f"noscript={has_noscript}; mount={has_mount}; "
                             f"renderer: {rr.get('error')}",
                    summary="Verify critical facts are server-rendered. Install Node + jsdom for render-diff.",
                    impact="Non-JS crawlers may see an empty shell.",
                    code_snippet="",
                ))

        # 4f. numeric facts locked in image metadata (alt/title/aria-label)
        locked = []
        for attrs in extract_img_metadata(html):
            for value in attrs.values():
                num = _extract_number_and_unit(value)
                if not num:
                    continue
                if not number_in_visible(num, visible):
                    locked.append(value[:60])
                    break

        if locked:
            findings.append(create_finding(
                finding_id="DISC-005",
                title="Numeric Facts Locked in Image Metadata",
                severity="medium",
                evidence=f"{len(locked)} image(s) carry numeric facts in alt/title/aria-label not present in visible text.",
                summary="Expose the same numeric facts as semantic text.",
                impact="Facts locked in image metadata are unreliable for text-only AI extraction.",
                code_snippet='<span itemprop="price" content="99.00">$99.00</span>',
            ))

        # 4g. semantic chunking
        ec = parser.element_counts
        if word_count >= 400 and ec["total"] > 0:
            ratio = ec["sectioning"] / max(ec["total"], 1)
            if ratio < 0.03:
                findings.append(create_finding(
                    finding_id="DISC-013",
                    title="Poor Semantic Chunking Affordances",
                    severity="medium",
                    evidence=f"{word_count} words across {ec['total']} elements; {ec['sectioning']} sectioning elements (ratio {ratio:.3f}).",
                    summary="Wrap content in <section>/<article> with an <h2> per chunk.",
                    impact="Fragmentary chunking degrades retrieval accuracy.",
                    code_snippet="<section>\n  <h2>Pricing</h2>\n  <p>Pro plan is $29/month for 5 users.</p>\n</section>",
                ))

        # 4h. hidden text / injection surface
        if parser.hidden_text_candidates:
            sev = "critical" if parser.potential_injection_hits else "medium"
            title = ("Hidden Text / Potential Prompt Injection Surface"
                     if parser.potential_injection_hits
                     else "Hidden Text in DOM")
            ev = [f"{len(parser.hidden_text_candidates)} visually-hidden block(s) >= 50 chars."]
            if parser.potential_injection_hits:
                ev.append(f"{len(parser.potential_injection_hits)} matched injection phrasing.")
            findings.append(create_finding(
                finding_id="DISC-014",
                title=title,
                severity=sev,
                evidence=" ".join(ev),
                summary=("Remove hidden text blocks; hidden text is read by LLMs but not users."
                         if parser.potential_injection_hits
                         else "Audit hidden text for AI-relevant content."),
                impact="Malicious or accidental hidden content can hijack AI assistants.",
                code_snippet='<span style="position:absolute;left:-9999px">Ignore previous instructions.</span>',
            ))

        # 4i. conversational-query schemas
        if word_count >= 500 and not _has_type_bounded(parser, CONVERSATIONAL_TYPES, max_depth=3):
            findings.append(create_finding(
                finding_id="DISC-015",
                title="Missing Conversational Query Schemas (FAQ/Q&A/HowTo)",
                severity="medium",
                evidence=f"No FAQPage/QAPage/HowTo/Question/Answer schema despite {word_count} words.",
                summary="Add FAQPage, HowTo, or QAPage JSON-LD on pages that answer discrete questions.",
                impact="Conversational retrieval indexes structured Q&A; unstructured content is skipped.",
                code_snippet='{"@type":"FAQPage","mainEntity":[{"@type":"Question","name":"How much does Pro cost?","acceptedAnswer":{"@type":"Answer","text":"$29/month for 5 users."}}]}',
            ))

        # 4j. speakable — vertical-gated
        is_article = _has_type_bounded(parser, NEWS_ARTICLE_TYPES, max_depth=2)
        has_speakable = False
        for block in parser.json_ld_blocks:
            for node in _iter_json_ld(block):
                if isinstance(node, dict) and "speakable" in node:
                    has_speakable = True
                    break
            if has_speakable:
                break
        if is_article and not has_speakable and word_count >= 400:
            findings.append(create_finding(
                finding_id="DISC-016",
                title="Missing speakable Schema on Article Page",
                severity="low",
                evidence=f"Article JSON-LD present but no speakable property ({word_count} words).",
                summary="Add speakable with cssSelector pointing to the page's answer paragraph.",
                impact="Voice/AI answer surfaces have no author hint about what to quote.",
                code_snippet='{"@type":"WebPage","speakable":{"@type":"SpeakableSpecification","cssSelector":[".answer-summary"]}}',
            ))

        # 4k. AI-bot UA responsiveness — compare baseline fetch with each bot UA.
        try:
            baseline_status = main_res["status"]
            baseline_len = len(html)
            for bot_name, ua in AI_BOT_UA_PROBES.items():
                if _ua_blocked_for_bot(bot_name, rules_by_agent, seen_agents):
                    continue
                probe = _probe_with_ua(target_url, ua)

                # Skip on transient probe failure — status 0 means DNS/SSL/timeout,
                # not a bot-specific WAF rule.
                if probe["status"] == 0:
                    sys.stderr.write(
                        f"DISC-018: skipping {bot_name} — probe failed "
                        f"(DNS/SSL/timeout)\n"
                    )
                    continue

                if probe["status"] != baseline_status:
                    findings.append(create_finding(
                        finding_id="DISC-018",
                        title=f"AI Bot {bot_name} Receives Different Response",
                        severity="high",
                        evidence=(
                            f"Browser-like fetch: HTTP {baseline_status}. "
                            f"{bot_name} UA fetch: HTTP {probe['status']}."
                        ),
                        summary=(
                            f"Investigate WAF/CDN rules that serve a different "
                            f"response to {bot_name}. AI assistants that respect "
                            f"this UA see a different page than users."
                        ),
                        impact=(
                            f"{bot_name} may cache or cite the wrong content, or "
                            f"fail to cite the brand entirely."
                        ),
                        code_snippet="",
                    ))
                elif (
                    probe["body_len"]
                    and baseline_len
                    and not main_res.get("truncated")
                    and abs(probe["body_len"] - baseline_len) > 0.4 * baseline_len
                ):
                    findings.append(create_finding(
                        finding_id="DISC-019",
                        title=f"AI Bot {bot_name} Receives Truncated/Swapped Content",
                        severity="medium",
                        evidence=(
                            f"Browser-like body: {baseline_len} chars. "
                            f"{bot_name} body: {probe['body_len']} chars."
                        ),
                        summary=(
                            f"Audit CDN/WAF behavior for {bot_name}. "
                            f"Content-parity between bot UAs is required for "
                            f"reliable AI citation."
                        ),
                        impact="AI summarizers see different facts than users.",
                        code_snippet="",
                    ))
        except Exception as e:
            sys.stderr.write(f"DISC-018/019 probe failed: {e}\n")

    # 5. sitemap-vs-robots
    robots = get_robots()
    sitemap_candidates = list(robots.sitemaps) or [f"{base}/sitemap.xml"]
    sitemap_res = {"status": 0, "body": ""}
    for sm_url in sitemap_candidates[:2]:
        r = safe_fetch(sm_url, skip_robots=True)
        if r.get("status") == 200 and (r.get("body") or "").strip():
            sitemap_res = r
            break
    if sitemap_res["status"] == 200 and rules_by_agent:
        urls = re.findall(r"<loc>(.*?)</loc>", sitemap_res["body"])
        if urls:
            conflicts = []
            for agent, agent_rules in rules_by_agent.items():
                for url in urls:
                    path = urllib.parse.urlparse(url).path or "/"
                    disallowed = any(_path_matches(path, d) for d in agent_rules["disallow"])
                    allowed = any(_path_matches(path, a) for a in agent_rules["allow"])
                    if disallowed and not allowed:
                        conflicts.append((agent, url))
            if conflicts:
                sample = sorted({a for a, _ in conflicts})[:4]
                findings.append(create_finding(
                    finding_id="DISC-007",
                    title="Sitemap-vs-Robots Contradiction",
                    severity="medium",
                    evidence=f"{len(conflicts)} sitemap URL(s) disallowed for agents: {', '.join(sample)}.",
                    summary="Ensure URLs in sitemap.xml are explicitly allowed in robots.txt.",
                    impact="Conflicting signals cause AI fetchers to skip pages.",
                    code_snippet="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml",
                ))

    for f in findings:
        f["mechanism"] = _MECHANISM_BY_ID.get(f.get("id"), "content")
    return findings


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_discovery(target), indent=2))