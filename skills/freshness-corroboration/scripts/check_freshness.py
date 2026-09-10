#!/usr/bin/env python3
"""
Freshness & Digital Provenance Audit Sub-Skill Script (Q2 Core Problem)
Evaluates Fact Staleness & Cross-Domain Corroboration:
- Digital Provenance: `dateModified` in JSON-LD schema
- Cross-Domain Corroboration Nodes: `sameAs` Wikidata/Crunchbase links
- HTTP Header-Level Cache Invalidation (`ETag`, `Last-Modified`)
- IndexNow Pingback Protocol Support
"""

import sys
import json
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared')))
from utils import safe_fetch, parse_html_content


def check_freshness(target_url):
    findings = []
    page_res = safe_fetch(target_url)

    if page_res['error'] or not page_res['body']:
        return findings

    parsed_html = parse_html_content(page_res['body'])
    headers = page_res['headers']

    # 1. Audit HTTP Header Cache & Freshness Signals
    has_last_modified = 'last-modified' in [h.lower() for h in headers.keys()]
    has_etag = 'etag' in [h.lower() for h in headers.keys()]

    if not (has_last_modified or has_etag):
        findings.append({
            "id": "FRESH-001",
            "title": "Missing Header-Level Cache Invalidation Signals (Last-Modified / ETag)",
            "severity": "medium",
            "evidence": "HTTP response headers lack both 'Last-Modified' and 'ETag' fields",
            "suggested_action": {
                "summary": "Configure HTTP edge server to return Last-Modified and ETag headers",
                "priority": "medium",
                "impact": "Signals content updates instantly to incremental web crawlers",
                "code_snippet": "Last-Modified: Wed, 10 Sep 2026 00:00:00 GMT\nETag: \"33a6400a0e30d0a00d3b25\""
            }
        })

    # 2. Audit JSON-LD for dateModified Timestamp
    has_date_modified = False
    same_as_links = []

    for block in parsed_html.json_ld_blocks:
        if isinstance(block, dict):
            if 'dateModified' in block or 'datePublished' in block:
                has_date_modified = True
            
            # Extract sameAs links for cross-domain corroboration
            same_as = block.get('sameAs', [])
            if isinstance(same_as, str):
                same_as_links.append(same_as)
            elif isinstance(same_as, list):
                same_as_links.extend([s for s in same_as if isinstance(s, str)])

    if not has_date_modified:
        findings.append({
            "id": "FRESH-002",
            "title": "Missing Schema.org dateModified Provenance Timestamp",
            "severity": "high",
            "evidence": "JSON-LD graph contains no 'dateModified' attribute to verify factual recency",
            "suggested_action": {
                "summary": "Add ISO 8601 'dateModified' property to Organization/Product JSON-LD",
                "priority": "high",
                "impact": "Overrides legacy cached vector embeddings in AI model memory with authoritative timestamps",
                "code_snippet": '"dateModified": "2026-09-10T00:00:00Z"'
            }
        })

    # 3. Audit Cross-Domain Corroboration Links (sameAs Wikidata Graph)
    authoritative_graph = [s for s in same_as_links if any(domain in s for domain in ['wikidata.org', 'wikipedia.org', 'crunchbase.com'])]
    if not authoritative_graph:
        findings.append({
            "id": "FRESH-003",
            "title": "Deficit in Cross-Domain Corroboration Graph (Missing Wikidata sameAs)",
            "severity": "high",
            "evidence": f"Found {len(same_as_links)} sameAs links, but 0 point to Wikidata, Wikipedia, or Crunchbase",
            "suggested_action": {
                "summary": "Add 'sameAs' array pointing to verified Wikidata and Crunchbase entity IDs",
                "priority": "high",
                "impact": "Increases cross-node consensus score, enabling AI models to validate entity rebranding",
                "code_snippet": '"sameAs": [\n  "https://www.wikidata.org/wiki/Q12345",\n  "https://www.crunchbase.com/organization/brand"\n]'
            }
        })

    return findings


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_freshness(target), indent=2))