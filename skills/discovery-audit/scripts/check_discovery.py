#!/usr/bin/env python3
"""
Discovery Audit Sub-Skill Script (Q1 Core Problem)
Evaluates Off-Site Discoverability:
- Machine-Readable Markdown Endpoints (/llms.txt and /llms-full.txt)
- AI Crawler Rules in robots.txt (GPTBot, ClaudeBot, PerplexityBot)
- Schema.org Entity Tagging (ItemList, Brand JSON-LD)
- Server-Side Rendering (SSR vs empty JS client hydrates)
"""

import sys
import json
import os
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared')))
from utils import safe_fetch, parse_html_content


def check_discovery(target_url):
    findings = []
    parsed_url = urllib.parse.urlparse(target_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # 1. Audit /llms.txt Machine-Readable Endpoint
    llms_url = f"{base_url}/llms.txt"
    llms_res = safe_fetch(llms_url)
    if llms_res['status'] != 200 or not llms_res['body'].strip():
        findings.append({
            "id": "DISC-001",
            "title": "Missing Machine-Readable /llms.txt Endpoint",
            "severity": "high",
            "evidence": f"GET {llms_url} returned HTTP status {llms_res['status'] or 'FAILED'}",
            "suggested_action": {
                "summary": "Deploy an /llms.txt file providing clean Markdown context for LLM agents",
                "priority": "high",
                "impact": "Improves RAG parsing efficiency for AI assistants like Perplexity and ChatGPT",
                "code_snippet": "# Brand Context\n> Summary of primary product line and key technical specifications.\n\n## Key Documents\n- [Product Catalog](/catalog.md)\n- [API Specs](/api.md)"
            }
        })

    # 2. Audit robots.txt for AI Crawler Bans
    robots_url = f"{base_url}/robots.txt"
    robots_res = safe_fetch(robots_url)
    ai_bots = ['gptbot', 'claudebot', 'perplexitybot', 'anthropic-ai', 'cohere-ai']
    blocked_bots = []

    if robots_res['status'] == 200 and robots_res['body']:
        lines = robots_res['body'].splitlines()
        current_agent = ""
        for line in lines:
            line = line.strip().lower()
            if line.startswith("user-agent:"):
                current_agent = line.split(":", 1)[1].strip()
            elif line.startswith("disallow:") and (current_agent in ai_bots or current_agent == "*"):
                rule = line.split(":", 1)[1].strip()
                if rule in ["/", "/*"]:
                    blocked_bots.append(current_agent)

    if blocked_bots:
        findings.append({
            "id": "DISC-002",
            "title": "AI Assistants explicitly blocked in robots.txt",
            "severity": "critical",
            "evidence": f"Found explicit 'Disallow: /' directive for user-agents: {', '.join(set(blocked_bots))}",
            "suggested_action": {
                "summary": "Update robots.txt to permit indexing by official AI search bots",
                "priority": "critical",
                "impact": "Blocks non-parametric real-time retrieval (RAG) by ChatGPT and Claude",
                "code_snippet": "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /"
            }
        })

    # 3. Audit Landing Page DOM for Schema.org and SSR
    page_res = safe_fetch(target_url)
    if page_res['body']:
        parsed_html = parse_html_content(page_res['body'])

        # Check Schema.org entity metadata
        has_brand_schema = False
        for block in parsed_html.json_ld_blocks:
            if isinstance(block, dict):
                stype = str(block.get('@type', '')).lower()
                if stype in ['brand', 'organization', 'itemlist', 'product']:
                    has_brand_schema = True
                    break

        if not has_brand_schema:
            findings.append({
                "id": "DISC-003",
                "title": "Missing Schema.org Entity Metadata (Brand/ItemList JSON-LD)",
                "severity": "high",
                "evidence": "0 JSON-LD blocks containing 'Brand', 'Organization', or 'ItemList' schemas were found",
                "suggested_action": {
                    "summary": "Embed structured Schema.org JSON-LD to assist entity resolution",
                    "priority": "high",
                    "impact": "Helps AI crawlers extract authoritative entity relationships and product collections",
                    "code_snippet": '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Brand",\n  "name": "BrandName",\n  "url": "https://example.com"\n}\n</script>'
                }
            })

        # Check SSR vs Client-Side JS Hydration
        body_len = len(page_res['body'].strip())
        script_count = len(parsed_html.scripts)
        if body_len < 1500 and script_count > 5:
            findings.append({
                "id": "DISC-004",
                "title": "Potential Client-Side JS Hydration Trap (Poor SSR)",
                "severity": "medium",
                "evidence": f"HTML payload is small ({body_len} bytes) but relies on {script_count} external JS bundles",
                "suggested_action": {
                    "summary": "Implement Server-Side Rendering (SSR) or Static Site Generation (SSG) for essential facts",
                    "priority": "medium",
                    "impact": "Ensures AI crawlers without JS rendering engines can extract facts immediately",
                    "code_snippet": "Pre-render HTML content above the fold during build time."
                }
            })

    return findings


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(check_discovery(target), indent=2))