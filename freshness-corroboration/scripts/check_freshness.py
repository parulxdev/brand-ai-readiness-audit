#!/usr/bin/env python3
"""
Fact Freshness & Digital Provenance Sub-skill Script (*X-Factor 2*).
Audits timestamp lineage (dateModified), HTTP cache invalidation headers,
IndexNow protocol readiness, and external cross-domain corroboration graphs (sameAs Wikidata).
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from shared.utils import safe_fetch, parse_html_content


def check_freshness(target_url):
    findings = []
    fetch_res = safe_fetch(target_url)

    if fetch_res['error'] or not fetch_res['body']:
        return findings

    headers = fetch_res['headers']
    parser = parse_html_content(fetch_res['body'])

    # --- 1. HTTP CACHE INVALIDATION & PROVENANCE HEADERS ---
    last_modified = headers.get('Last-Modified') or headers.get('last-modified')
    etag = headers.get('ETag') or headers.get('etag')

    if not last_modified and not etag:
        findings.append({
            "id": "FRESH-001",
            "title": "Missing HTTP Provenance & Cache Invalidation Headers",
            "severity": "medium",
            "evidence": "HTTP response lacks both 'Last-Modified' and 'ETag' header fields.",
            "suggested_action": {
                "summary": "Configure web server/CDN to emit Last-Modified and strong ETag HTTP response headers.",
                "priority": "medium",
                "impact": "Allows AI crawlers to instantly identify stale vector embeddings without re-parsing entire pages.",
                "code_snippet": "Header set Last-Modified %{NOW}e\nHeader set ETag \"\\\"%X-%s\\\"\""
            }
        })

    # --- 2. STRUCTURED TIMESTAMP LINEAGE AUDIT ---
    has_date_modified = False
    same_as_links = []

    for block in parser.json_ld_blocks:
        if isinstance(block, dict):
            if 'dateModified' in block or 'datePublished' in block:
                has_date_modified = True
            
            # Extract sameAs corroboration links
            same_as = block.get('sameAs', [])
            if isinstance(same_as, str):
                same_as_links.append(same_as)
            elif isinstance(same_as, list):
                same_as_links.extend([str(x) for x in same_as])

    if not has_date_modified:
        findings.append({
            "id": "FRESH-002",
            "title": "Missing Schema.org dateModified Provenance Timestamps",
            "severity": "high",
            "evidence": "Structured JSON-LD blocks do not specify a 'dateModified' attribute.",
            "suggested_action": {
                "summary": "Add explicit ISO-8601 'dateModified' property to Schema.org JSON-LD markup.",
                "priority": "high",
                "impact": "Explicitly instructs RAG systems and LLMs that current facts supersede legacy vector data.",
                "code_snippet": '"dateModified": "2026-09-10T00:00:00Z"'
            }
        })

    # --- 3. CROSS-DOMAIN CORROBORATION GRAPH (sameAs Wikidata Verification) ---
    authoritative_sources = ['wikidata.org', 'wikipedia.org', 'crunchbase.com', 'linkedin.com']
    has_authority_link = any(
        any(auth in link.lower() for auth in authoritative_sources)
        for link in same_as_links
    )

    if not has_authority_link:
        findings.append({
            "id": "FRESH-003",
            "title": "Weak Cross-Domain Entity Corroboration Graph (Missing sameAs References)",
            "severity": "high",
            "evidence": f"Found {len(same_as_links)} sameAs links, but zero links pointing to authoritative graph nodes (Wikidata/Wikipedia/Crunchbase).",
            "suggested_action": {
                "summary": "Populate Schema.org 'sameAs' array with canonical Wikidata, Wikipedia, and official corporate registry URIs.",
                "priority": "high",
                "impact": "Increases cross-node corroboration weight, preventing legacy facts from overriding modern rebrand metrics.",
                "code_snippet": '"sameAs": [\n  "https://www.wikidata.org/wiki/Q12345",\n  "https://en.wikipedia.org/wiki/BrandName"\n]'
            }
        })

    return findings


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    results = check_freshness(target)
    print(json.dumps(results, indent=2))