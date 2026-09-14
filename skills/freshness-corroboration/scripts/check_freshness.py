#!/usr/bin/env python3
"""Freshness & Corroboration — merged: FRESH-004 headers, FRESH-012 decay."""

import datetime
import json
import os
import re
import sys
import urllib.parse
from email.utils import parsedate_to_datetime

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)
for _p in (SCRIPT_DIR, SHARED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib.utils import create_finding, safe_fetch, parse_html_content
from lib.ner import has_named_entity, has_quantity


AUTHORITATIVE = ("wikidata.org", "wikipedia.org", "crunchbase.com")
AUTHORITATIVE_EXT = (
    # Generic TLDs
    "gov", "edu", "gov.uk", "gov.in", "gov.au", "gov.ca",
    "ac.uk", "ac.in", "edu.au",
    # Encyclopaedic / knowledge graph
    "wikipedia.org", "wikidata.org", "britannica.com",
    # Wire services
    "reuters.com", "apnews.com", "afp.com", "pti.in", "aniin.com",
    # Major outlets
    "bbc.com", "nytimes.com", "theguardian.com", "economist.com",
    "wsj.com", "ft.com", "bloomberg.com", "forbes.com",
    # Academic / scientific
    "nature.com", "sciencedirect.com", "springer.com", "wiley.com",
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "doi.org",
    # Health / regulatory
    "who.int", "cdc.gov", "nih.gov", "ema.europa.eu", "fda.gov",
    "dgca.gov.in", "iata.org", "icao.int",
    # Financial
    "sec.gov", "sebi.gov.in", "rbi.org.in",
    # Crunchbase / business
    "crunchbase.com", "pitchbook.com",
)
_MECHANISM_BY_ID = {
    "FRESH-001": "content",
    "FRESH-002": "template",
    "FRESH-003": "content",
    "FRESH-004": "config",
    "FRESH-004a": "config",
    "FRESH-006": "content",
    "FRESH-007": "external",
    "FRESH-008": "content",
    "FRESH-009": "external",
    "FRESH-010": "external",
    "FRESH-011": "external",
    "FRESH-012": "content",
    
}
FACT_HALF_LIVES = {
    "pricing": 30, "regulatory": 90, "availability": 30,
    "specs": 180, "company": 365,
}

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_HUMAN_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_FRESHNESS_KEYWORD_RE = re.compile(
    r"\b(?:last\s+updated|updated\s+on|last\s+modified|modified\s+on|"
    r"as\s+of|published\s+on|revised\s+on|reviewed\s+on)\b",
    re.IGNORECASE,
)

_FRESHNESS_ATTRIBUTION_RE = re.compile(
    r"(?:"
        r"\b(?:according\s+to|reports?|reported\s+by|studies\s+show|"
        r"research\s+shows|data\s+from|survey\s+by)\b"
        r"|"
        r"\bsource[s]?\s*:"
    r")",
    re.IGNORECASE,
)


# ── helpers ──
def _netloc_authoritative(url, domains):
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(netloc == d or netloc.endswith("." + d) for d in domains)


def _iter_nodes(root):
    stack = [root]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            for v in current.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(current, list):
            stack.extend(current)


def _collect_same_as(blocks):
    acc = set()
    for block in blocks:
        for node in _iter_nodes(block):
            if not isinstance(node, dict):
                continue
            sa = node.get("sameAs")
            if isinstance(sa, str):
                acc.add(sa)
            elif isinstance(sa, list):
                for item in sa:
                    if isinstance(item, str):
                        acc.add(item)
                    elif isinstance(item, dict):
                        u = item.get("@id") or item.get("url")
                        if isinstance(u, str):
                            acc.add(u)
            elif isinstance(sa, dict):
                u = sa.get("@id") or sa.get("url")
                if isinstance(u, str):
                    acc.add(u)
    return acc


def _find_brand_name(blocks):
    for block in blocks:
        for node in _iter_nodes(block):
            if not isinstance(node, dict):
                continue
            t = node.get("@type", "")
            ts = (" ".join(str(x) for x in t).lower()
                  if isinstance(t, list) else str(t).lower())
            if ("organization" in ts or "brand" in ts) and node.get("name"):
                return str(node["name"]).strip()
    return ""


def _parse_dates(text, today):
    out = []
    for m in _ISO_DATE_RE.finditer(text or ""):
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            out.append((d, d > today))
        except ValueError:
            pass
    for m in _HUMAN_DATE_RE.finditer(text or ""):
        try:
            mo = _MONTH_MAP.get(m.group(1).lower())
            if mo:
                d = datetime.date(int(m.group(3)), mo, int(m.group(2)))
                out.append((d, d > today))
        except ValueError:
            pass
    return out


def _parse_dates_near_freshness_keywords(text, today, window=80):
    """Asymmetric window: `window // 2` before, `window` after."""
    out = []
    if not text:
        return out
    for kw in _FRESHNESS_KEYWORD_RE.finditer(text):
        lo = max(0, kw.start() - window // 2)
        hi = min(len(text), kw.end() + window)
        out.extend(_parse_dates(text[lo:hi], today))
    return out


def _parse_http_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.date()
    except (TypeError, ValueError):
        return None


def _classify_fact(page_text, url_path):
    low_path = (url_path or "").lower()
    low_text = (page_text or "").lower()[:4000]
    if any(k in low_path for k in ("pricing", "plans", "rates", "fees")) \
       or re.search(r"\b(?:per\s+month|monthly|annual\s+price|starting\s+at)\b", low_text):
        return "pricing"
    if any(k in low_path for k in ("compliance", "regulatory", "terms", "privacy", "policy")):
        return "regulatory"
    if any(k in low_path for k in ("available", "in-stock", "stock", "availability")):
        return "availability"
    if any(k in low_path for k in ("specs", "specifications", "features", "integrations")):
        return "specs"
    if any(k in low_path for k in ("about", "history", "company", "team")):
        return "company"
    return "company"


def _extract_jsonld_dates(parser):
    found = []
    props = {"dateModified", "datePublished", "uploadDate", "dateCreated"}
    for block in parser.json_ld_blocks:
        for node in _iter_nodes(block):
            if isinstance(node, dict):
                for k in props:
                    v = node.get(k)
                    if isinstance(v, str):
                        found.append(v)
    return found


def _freshness_velocity(page_text, url_path, jsonld_dates=None,
                        http_last_modified=None, today=None):
    today = today or datetime.date.today()
    fact_class = _classify_fact(page_text, url_path)
    half_life = FACT_HALF_LIVES.get(fact_class, 365)

    candidates = []
    for raw in (jsonld_dates or []):
        candidates.extend(_parse_dates(raw, today))
    d_http = _parse_http_date(http_last_modified)
    if d_http:
        candidates.append((d_http, d_http > today))
    candidates.extend(_parse_dates_near_freshness_keywords(page_text, today))

    # Dedupe.
    seen = set()
    unique = []
    for d, fut in candidates:
        if d not in seen:
            seen.add(d)
            unique.append((d, fut))

    past = [d for d, fut in unique if not fut]
    if not past:
        return None
    newest = max(past)
    days_since = (today - newest).days
    velocity = days_since / max(half_life, 1)
    return velocity, fact_class, days_since, half_life, newest


def _extract_numeric_claims(parser, html):
    """
    Single-source fragility candidates.

    Primary: parser-collected emphasized (b/strong/q, nested-aware) + quoted text.
    Secondary: paragraph sentences carrying an attribution phrase.
    No 2-quantity escape hatch.
    """
    claims = list(parser.emphasized_texts)
    claims.extend(re.findall(r'[“"]([^”"]{15,300}?)[”"]', html))

    for para in parser.paragraphs:
        for sent in re.split(r"(?<=[.!?])\s+", para["text"]):
            sent = sent.strip()
            if not (15 <= len(sent) <= 300):
                continue
            if _FRESHNESS_ATTRIBUTION_RE.search(sent):
                claims.append(sent)

    return [c for c in claims if has_quantity(c) and has_named_entity(c)]


# ── main check ──
def check_freshness(target_url):
    findings = []
    res = safe_fetch(target_url)
    if res["status"] != 200 or not res["body"]:
        return findings

    html = res["body"]
    parser = parse_html_content(html)

    # FRESH-004 — HTTP cache-invalidation headers
    headers = res.get("headers", {})
    cc = headers.get("cache-control", "").lower()
    if "no-store" in cc:
        findings.append(create_finding(
            finding_id="FRESH-004a",
            title="Cache-Control: no-store on Public Page",
            severity="medium",
            evidence=f'Cache-Control header: "{cc}"',
            summary=(
                "Remove 'no-store' from public marketing / editorial pages. "
                "It instructs every intermediary (including AI crawlers) not "
                "to retain the response."
            ),
            impact="AI crawlers skip caching, reducing effective visibility.",
            code_snippet="Cache-Control: public, max-age=300, must-revalidate",
        ))

    if "last-modified" not in headers and "etag" not in headers:
        findings.append(create_finding(
            finding_id="FRESH-004",
            title="Missing HTTP Cache-Invalidation Headers (Last-Modified / ETag)",
            severity="medium",
            evidence="Response headers contain neither 'Last-Modified' nor 'ETag'.",
            summary=(
                "Emit Last-Modified and ETag on HTML responses so incremental "
                "crawlers detect updates cheaply."
            ),
            impact=(
                "Without header-level freshness signals, AI crawlers re-fetch "
                "full pages or skip updates."
            ),
            code_snippet='Last-Modified: Wed, 10 Sep 2026 00:00:00 GMT\nETag: "33a6400a"',
        ))
    

    # Walk JSON-LD (iterative).
    has_org_brand = False
    has_disambiguation = False
    has_date_modified = False
    for block in parser.json_ld_blocks:
        for node in _iter_nodes(block):
            if not isinstance(node, dict):
                continue
            t = node.get("@type", "")
            ts = (" ".join(str(x) for x in t).lower()
                  if isinstance(t, list) else str(t).lower())
            if "organization" in ts or "brand" in ts:
                has_org_brand = True
                if node.get("disambiguatingDescription"):
                    has_disambiguation = True
            if node.get("dateModified"):
                has_date_modified = True

    same_as = _collect_same_as(parser.json_ld_blocks)
    if any(_netloc_authoritative(l, AUTHORITATIVE) for l in same_as):
        has_disambiguation = True

    # FRESH-001
    if has_org_brand and not has_disambiguation:
        findings.append(create_finding(
            finding_id="FRESH-001",
            title="Entity Disambiguation Deficit",
            severity="high",
            evidence="Organization/Brand JSON-LD present but no disambiguatingDescription and no Wikidata/Wikipedia sameAs.",
            summary="Add disambiguatingDescription and sameAs links to Wikidata/Wikipedia in Organization JSON-LD.",
            impact="AI systems may confuse the brand with identically-named entities.",
            code_snippet='"sameAs": ["https://www.wikidata.org/wiki/Q12345"],\n"disambiguatingDescription": "Cloud storage provider, distinct from Company X."',
        ))

    # FRESH-002
    if not has_date_modified:
        visible = " ".join("".join(parser.visible_text).split())
        vis_dates = _parse_dates_near_freshness_keywords(visible, datetime.date.today())
        ev = "JSON-LD contains no dateModified attribute."
        past = [d for d, fut in vis_dates if not fut]
        if past:
            recent = max(past)
            ev += f" A visible freshness-context date ({recent.isoformat()}) exists and can be mirrored."
        findings.append(create_finding(
            finding_id="FRESH-002",
            title="Missing Schema.org dateModified Provenance Timestamp",
            severity="high",
            evidence=ev,
            summary="Emit ISO-8601 dateModified in JSON-LD (and Last-Modified HTTP header) whenever facts change.",
            impact="AI systems cannot verify recency; stale facts may be preferred over fresh ones.",
            code_snippet='"dateModified": "2026-09-13T00:00:00Z"',
        ))

    # FRESH-003
    corroborating = [l for l in same_as if _netloc_authoritative(l, AUTHORITATIVE)]
    if not corroborating:
        findings.append(create_finding(
            finding_id="FRESH-003",
            title="Cross-Domain Corroboration Deficit",
            severity="high",
            evidence=f"{len(same_as)} sameAs link(s); 0 to Wikidata, Wikipedia, or Crunchbase.",
            summary="Add sameAs entries linking to authoritative entity registries (Wikidata preferred).",
            impact="Single-source facts are more likely to be discarded or misattributed.",
            code_snippet='"sameAs": ["https://www.wikidata.org/wiki/Q12345"]',
        ))

    # FRESH-006
    own = urllib.parse.urlparse(target_url).netloc.lower()
    numeric_claims = _extract_numeric_claims(parser, html)
    auth_outbound = 0
    for anchor in parser.anchors:
        href = anchor.get("href", "")
        if not href.startswith("http"):
            continue
        netloc = urllib.parse.urlparse(href).netloc.lower()
        if netloc == own:
            continue
        if any(netloc == d or netloc.endswith("." + d) for d in AUTHORITATIVE_EXT):
            auth_outbound += 1

    if len(numeric_claims) >= 3 and auth_outbound == 0:
        example = numeric_claims[0].strip()[:80]
        findings.append(create_finding(
            finding_id="FRESH-006",
            title="Single-Source Fragility Signal",
            severity="medium",
            evidence=f"{len(numeric_claims)} emphasized/quoted/attributed numeric claims; "
                     f"0 outbound authoritative links. Example: \"{example}\"",
            summary="Cite external authoritative sources for key numeric claims.",
            impact="Uncorroborated claims are more likely to be dropped or down-ranked by RAG systems.",
            code_snippet='<p>The 2026 market grew <strong>14.2%</strong> according to <a href="https://www.reuters.com/...">Reuters</a>.</p>',
        ))

    # FRESH-007 / FRESH-008 — Wikipedia corroboration
    try:
        from corroborate import corroborate_brand
    except ImportError as e:
        corroborate_brand = None
        sys.stderr.write(f"corroborate unavailable: {e}\n")

    if corroborate_brand is not None:
        brand = _find_brand_name(parser.json_ld_blocks)
        if not brand:
            for h in parser.headings:
                if h["tag"] == "h1" and h["text"]:
                    brand = h["text"].strip()
                    break
        if not brand:
            t = parser.meta_tags.get("og:site_name") or parser.meta_tags.get("og:title")
            if t:
                brand = t.split("|")[0].split("-")[0].strip()[:60]

        if brand:
            wiki = corroborate_brand(brand)
            if wiki.get("error"):
                sys.stderr.write(f"corroboration failed for '{brand}': {wiki['error']}\n")
            elif not wiki["found"]:
                findings.append(create_finding(
                    finding_id="FRESH-007",
                    title="External Corroboration Deficit (No Wikipedia Match)",
                    severity="medium",
                    evidence=f"Wikipedia search for '{brand}' returned no close match.",
                    summary="Establish a Wikipedia/Wikidata entity, or add sameAs to an authoritative source.",
                    impact="Single-source brands are treated as lower-confidence by AI systems.",
                    code_snippet='"sameAs": ["https://www.wikidata.org/wiki/Q..."]',
                ))
            else:
                frag = f"wikipedia.org/wiki/{wiki['best_match'].replace(' ', '_')}".lower()
                if not any(frag in (l or "").lower() for l in same_as):
                    findings.append(create_finding(
                        finding_id="FRESH-008",
                        title="Wikipedia Entity Exists But Not Linked via sameAs",
                        severity="low",
                        evidence=f"Wikipedia page '{wiki['best_match']}' found, but no sameAs references it.",
                        summary="Add sameAs pointing to the matching Wikipedia/Wikidata URL.",
                        impact="Explicit sameAs strengthens entity-graph confidence.",
                        code_snippet=f'"sameAs": ["https://en.wikipedia.org/wiki/{wiki["best_match"].replace(" ", "_")}"]',
                    ))

    # FRESH-012 — freshness decay
        jsonld_dates = _extract_jsonld_dates(parser)
    http_lm = res["headers"].get("last-modified")

    # Sitemap <lastmod> — one of the most reliable freshness signals for
    # AI crawlers. Read it from the robots-declared sitemap.
    from lib.utils import get_robots, safe_fetch as _sf
    robots = get_robots()
    sitemap_candidates = list(robots.sitemaps) or [
        f"{urllib.parse.urlparse(target_url).scheme}://"
        f"{urllib.parse.urlparse(target_url).netloc}/sitemap.xml"
    ]
    sitemap_lastmods = []
    for sm in sitemap_candidates[:1]:
        r = _sf(sm, timeout=4, skip_robots=True)
        if r.get("status") == 200 and r.get("body"):
            for m in re.finditer(
                r"<lastmod>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
                r["body"],
            ):
                sitemap_lastmods.append(m.group(1))

    visible = " ".join("".join(parser.visible_text).split())
    url_path = urllib.parse.urlparse(target_url).path
    vel = _freshness_velocity(visible, url_path,
                              jsonld_dates=jsonld_dates + sitemap_lastmods,
                              http_last_modified=http_lm)
    if vel:
        velocity, fact_class, days_since, half_life, date_found = vel
        if velocity >= 3.0:
            findings.append(create_finding(
                finding_id="FRESH-012",
                title="High Freshness Decay Velocity",
                severity="high" if velocity >= 6.0 else "medium",
                evidence=(f"Page classified as '{fact_class}'. Newest fact date "
                          f"{date_found.isoformat()} → {days_since} days old. "
                          f"Half-life {half_life}d → decay_velocity={velocity:.2f}."),
                summary=(f"Refresh {fact_class} facts and re-emit dateModified. "
                         f"Target cadence: at least every {half_life // 2} days."),
                impact="Stale facts are down-weighted by recency-sensitive retrieval.",
                code_snippet='"dateModified": "<current ISO-8601 timestamp>"',
            ))

    for f in findings:
        f["mechanism"] = _MECHANISM_BY_ID.get(f.get("id"), "content")
    return findings


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_freshness(target), indent=2))