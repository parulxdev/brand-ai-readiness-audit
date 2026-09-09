#!/usr/bin/env python3
"""
Off-Site AI Discoverability Sub-skill Script.
Audits robots.txt rules, /llms.txt availability, SSR vs Client-side JavaScript rendering,
and Schema.org list structures (ItemList/Brand).
"""

import os
import sys
import json
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from shared.utils import safe_fetch, parse_html_content


def check_discovery(target_url):
    findings = []
    parsed_url = urllib.parse.urlparse(target_url)
    base_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"

    # --- 1. ROBOTS.TXT AUDIT ---
    robots_url = urllib.parse.urljoin(base_origin, "/robots.txt")
    robots_res = safe_fetch(robots_url)
    
    if robots_res['status'] == 200 and robots_res['body']:
        robots_txt = robots_res['body'].lower()
        ai_bots = ['gptbot', 'chatgpt-user', 'perplexitybot', 'claude-web', 'claude-searchbot', 'anthropic-ai', 'cohere-ai']
        blocked_bots = []
        for bot in ai_bots:
            if f"user-agent: {bot}" in robots_txt:
                # Check next lines for disallow
                lines = robots_txt.splitlines()
                for idx, line in enumerate(lines):
                    if f"user-agent: {bot}" in line:
                        for sub_line in lines[idx+1:idx+4]:
                            if sub_line.startswith("disallow: /") and not sub_line.startswith("disallow: /_"):
                                blocked_bots.append(bot)
                                break

        if blocked_bots:
            findings.append({
                "id": "DISC-001",
                "title": "AI Assistant Crawlers Explicitly Blocked in robots.txt",
                "severity": "critical",
                "evidence": f"robots.txt disallows access to major AI web crawlers: {', '.join(blocked_bots)}.",
                "suggested_action": {
                    "summary": "Remove restrictive Disallow directives for key AI user-agents in robots.txt.",
                    "priority": "critical",
                    "impact": "Unblocks AI models from reading, indexing, and fetching real-time facts from your site.",
                    "code_snippet": "User-agent: GPTBot\nAllow: /\n\nUser-agent: PerplexityBot\nAllow: /"
                }
            })
    else:
        findings.append({
            "id": "DISC-002",
            "title": "Missing or Unreachable robots.txt File",
            "severity": "medium",
            "evidence": f"HTTP request to {robots_url} returned status code {robots_res['status'] or 'Error'}.",
            "suggested_action": {
                "summary": "Deploy a valid robots.txt file at the domain root with explicit rules for AI assistants.",
                "priority": "medium",
                "impact": "Establishes explicit authorization guidelines for AI web crawlers.",
                "code_snippet": "User-agent: *\nAllow: /\nSitemap: " + base_origin + "/sitemap.xml"
            }
        })

    # --- 2. /llms.txt MACHINE-READABLE ENDPOINT CHECK ---
    llms_url = urllib.parse.urljoin(base_origin, "/llms.txt")
    llms_res = safe_fetch(llms_url)
    if llms_res['status'] != 200 or not llms_res['body'].strip():
        findings.append({
            "id": "DISC-003",
            "title": "Missing Machine-Readable /llms.txt Specification Standard",
            "severity": "high",
            "evidence": f"HTTP request to {llms_url} yielded status code {llms_res['status'] or 'Unreachable'}.",
            "suggested_action": {
                "summary": "Implement /llms.txt and /llms-full.txt machine-readable documentation endpoints.",
                "priority": "high",
                "impact": "Provides non-parametric RAG pipelines with a direct, concise markdown index of core brand facts.",
                "code_snippet": f"# Brand Overview\n> Concise summary for LLM context.\n\n## Core Products\n- [{parsed_url.netloc}]({target_url}): Primary brand landing page."
            }
        })

    # --- 3. SSR / CLIENT-SIDE RENDERING GAP AUDIT ---
    page_res = safe_fetch(target_url)
    if page_res['body']:
        parser = parse_html_content(page_res['body'])
        static_body_length = len(page_res['body'])
        
        # Detect Client-side heavy JS framework placeholders
        script_count = len(parser.scripts)
        has_app_root = '<div id="root">' in page_res['body'] or '<div id="app">' in page_res['body']
        
        if (has_app_root and static_body_length < 5000) or (script_count > 15 and static_body_length < 8000):
            findings.append({
                "id": "DISC-004",
                "title": "Client-Side Rendering (CSR) Context Loss for AI Bots",
                "severity": "critical",
                "evidence": f"Page relies heavily on client-side JS hydration (Found {script_count} scripts and client root shell; static HTML size: {static_body_length} bytes).",
                "suggested_action": {
                    "summary": "Implement Server-Side Rendering (SSR) or Dynamic Rendering for non-browser AI crawlers.",
                    "priority": "critical",
                    "impact": "Ensures AI bots fetch fully rendered HTML markup containing core facts without running JS engines.",
                    "code_snippet": "// Configure Edge middleware to render pre-hydrated HTML for User-Agents: GPTBot|PerplexityBot|ClaudeBot"
                }
            })

        # --- 4. SCHEMA.ORG ENTITY DATA CHECK ---
        has_brand_schema = False
        has_item_list = False

        for block in parser.json_ld_blocks:
            if isinstance(block, dict):
                stype = str(block.get('@type', '')).lower()
                if 'brand' in stype or 'organization' in stype:
                    has_brand_schema = True
                if 'itemlist' in stype or 'offercatalog' in stype:
                    has_item_list = True

        if not has_brand_schema:
            findings.append({
                "id": "DISC-005",
                "title": "Missing Schema.org/Brand or Schema.org/Organization Metadata",
                "severity": "high",
                "evidence": "Zero structured Schema.org JSON-LD Organization/Brand entity blocks were found in page HTML.",
                "suggested_action": {
                    "summary": "Embed Schema.org/Organization JSON-LD with canonical entity properties.",
                    "priority": "high",
                    "impact": "Establishes unambiguous entity identity in AI knowledge graphs.",
                    "code_snippet": '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "Brand",\n  "url": "' + base_origin + '"\n}\n</script>'
                }
            })

    return findings


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    results = check_discovery(target)
    print(json.dumps(results, indent=2))