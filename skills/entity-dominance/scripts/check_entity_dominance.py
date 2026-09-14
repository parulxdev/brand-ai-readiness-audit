#!/usr/bin/env python3
"""Entity Graph Dominance — deadline-aware."""

import json
import os
import sys
import time
import urllib.parse
import urllib.request


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
for _p in (SCRIPT_DIR, SHARED_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from utils import create_finding, safe_fetch, parse_html_content, get_deadline


# Wikimedia's UA policy requires a contact URL or email; without it,
# SPARQL calls may be rate-limited or silently dropped.
UA = (
    "AI-Readiness-Auditor/1.0 "
    "(+https://github.com/example/brand-ai-readiness-audit; "
    "contact: audit@example.com)"
)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

_MECHANISM_BY_ID = {
    "FRESH-009": "external",
    "FRESH-010": "external",
    "FRESH-011": "external",
}


def _http_json(url, default_timeout=6):
    """Deadline-aware JSON fetch. Returns None on error or near-deadline."""
    deadline = get_deadline()
    timeout = default_timeout
    if deadline is not None:
        remaining = deadline - time.time()
        if remaining <= 2:
            return None
        timeout = min(default_timeout, remaining - 1)

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/sparql-results+json, application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _wikidata_search(term, limit=10):
    params = {
        "action": "wbsearchentities",
        "search": term,
        "language": "en",
        "format": "json",
        "limit": str(limit),
        "type": "item",
    }
    data = _http_json(
        f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
    )
    return (data or {}).get("search", []) or []


def _wikidata_relationship_count(qid):
    query = f"SELECT (COUNT(?p) AS ?n) WHERE {{ wd:{qid} ?p ?o . }}"
    params = {"query": query, "format": "json"}
    data = _http_json(
        f"{WIKIDATA_SPARQL}?{urllib.parse.urlencode(params)}"
    )
    if not data:
        return None
    try:
        return int(data["results"]["bindings"][0]["n"]["value"])
    except Exception:
        return None


def _wikidata_claims(qid, prop):
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "format": "json",
        "props": "claims",
    }
    data = _http_json(
        f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
    )
    if not data:
        return None
    try:
        return data["entities"][qid]["claims"].get(prop, [])
    except Exception:
        return None


def _infer_brand(target_url):
    res = safe_fetch(target_url)
    if res["status"] != 200:
        return ""
    parser = parse_html_content(res["body"])

    def walk(node):
        stack = [node]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                t = current.get("@type", "")
                ts = (
                    " ".join(str(x) for x in t).lower()
                    if isinstance(t, list)
                    else str(t).lower()
                )
                if ("organization" in ts or "brand" in ts) and current.get("name"):
                    return str(current["name"]).strip()
                for v in current.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(current, list):
                stack.extend(current)
        return ""

    for block in parser.json_ld_blocks:
        name = walk(block)
        if name:
            return name

    if parser.meta_tags.get("og:site_name"):
        return parser.meta_tags["og:site_name"].strip()[:80]

    for h in parser.headings:
        if h["tag"] == "h1" and h["text"]:
            return h["text"].strip()[:80]

    return ""


def check_entity_dominance(target_url):
    findings = []
    brand = _infer_brand(target_url)
    if not brand:
        return findings

    candidates = _wikidata_search(brand, limit=10)
    exact = [
        c for c in candidates
        if (c.get("label") or "").strip().lower()
        == brand.strip().lower()
    ]
    ambiguous = len(candidates)

    if ambiguous == 0:
        findings.append(create_finding(
            finding_id="FRESH-009",
            title="No Knowledge-Graph Entity Exists",
            severity="high",
            evidence=f"Wikidata search for '{brand}' returned 0 items.",
            summary=(
                "Establish a Wikidata item, or add sameAs to an existing "
                "authoritative entity."
            ),
            impact=(
                "Without a knowledge-graph node, AI systems have no anchor "
                "to reconcile brand claims."
            ),
            code_snippet='{"sameAs": ["https://www.wikidata.org/wiki/Q..."]}',
        ))
    elif not exact:
        severity = "high" if ambiguous >= 5 else "medium"
        findings.append(create_finding(
            finding_id="FRESH-009",
            title="Low Entity Dominance — No Exact-Label Match",
            severity=severity,
            evidence=(
                f"Brand name '{brand}' returned {ambiguous} Wikidata "
                f"candidate(s); 0 exact-label matches."
            ),
            summary=(
                "Register or extend a Wikidata item with "
                "disambiguatingDescription, then link via sameAs."
            ),
            impact=(
                "AI assistants resolving by entity cannot tell which "
                "candidate is the brand."
            ),
            code_snippet=(
                '"disambiguatingDescription": "Cloud storage provider, '
                'distinct from Signal messenger."'
            ),
        ))
    elif ambiguous >= 5 and len(exact) >= 1:
        findings.append(create_finding(
            finding_id="FRESH-009",
            title="Moderate Entity Dominance — Name Collision Risk",
            severity="medium",
            evidence=(
                f"Brand '{brand}' matched {len(exact)} exact Wikidata "
                f"item(s) among {ambiguous} candidates."
            ),
            summary=(
                "Consolidate the entity: merge duplicate items and add "
                "disambiguatingDescription."
            ),
            impact="Duplicate items split claim consensus across nodes.",
            code_snippet="",
        ))

    top_qid = (
        exact[0].get("id")
        if exact
        else (candidates[0].get("id") if candidates else None)
    )

    if top_qid:
        rel = _wikidata_relationship_count(top_qid)
        if rel is not None and rel < 15:
            findings.append(create_finding(
                finding_id="FRESH-011",
                title="Shallow Entity Relationship Graph",
                severity="medium",
                evidence=(
                    f"Wikidata item {top_qid} has only {rel} typed "
                    f"statements (target >= 15)."
                ),
                summary=(
                    "Enrich the Wikidata item with typed relationships "
                    "(industry, headquarters, founding year, subsidiaries, "
                    "key people)."
                ),
                impact=(
                    "Sparse entity graphs are less likely to be surfaced "
                    "by entity-resolution pipelines."
                ),
                code_snippet="",
            ))

        hq = _wikidata_claims(top_qid, "P159") or []
        country = _wikidata_claims(top_qid, "P17") or []
        if not hq and not country:
            findings.append(create_finding(
                finding_id="FRESH-010",
                title="Entity Claim Inconsistency — No Location Anchor",
                severity="medium",
                evidence=(
                    f"Wikidata item {top_qid} declares no headquarters "
                    f"(P159) or country (P17)."
                ),
                summary="Add headquarters location and country to the Wikidata item.",
                impact=(
                    "Missing location data weakens local and region-scoped "
                    "retrieval."
                ),
                code_snippet="",
            ))

    for f in findings:
        f["mechanism"] = _MECHANISM_BY_ID.get(f.get("id"), "external")
    return findings


if __name__ == "__main__":
    target = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://example.com"
    )
    print(json.dumps(check_entity_dominance(target), indent=2))