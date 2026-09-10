#!/usr/bin/env python3
"""
On-Site Engagement & Context Retention Sub-skill Script (*X-Factor 1 & 3*).
Audits referrer-aware edge middleware signals, deep-linking heading anchor IDs,
and 'Digital Feng Shui' above-the-fold static spec visibility vs hidden accordions/images.
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from shared.utils import safe_fetch, parse_html_content


def check_engagement(target_url):
    findings = []
    fetch_res = safe_fetch(target_url)

    if fetch_res['error'] or not fetch_res['body']:
        return findings

    html = fetch_res['body']
    parser = parse_html_content(html)

    # --- 1. REFERRER-AWARE MIDDLEARING / CONCIERGE PROTOCOL CHECK ---
    html_lower = html.lower()
    has_referrer_script = any(
        k in html_lower for k in ['document.referrer', 'http_referer', 'chatgpt.com', 'perplexity.ai', 'ai_assistant', 'utm_source=ai']
    )

    if not has_referrer_script:
        findings.append({
            "id": "ENGAGE-001",
            "title": "Stateless Referral Routing (Missing AI Referrer Context Bridge)",
            "severity": "high",
            "evidence": "No static DOM scripts or Edge header inspect rules detected for AI referrer domains (e.g., chatgpt.com, perplexity.ai).",
            "suggested_action": {
                "summary": "Deploy Edge Middleware / Frontend Context Bridge to inspect Referer headers and render personalized banners.",
                "priority": "high",
                "impact": "Eliminates state loss when users click citations, preserving pre-conditioned intent upon site entry.",
                "code_snippet": "if (document.referrer.includes('chatgpt.com')) {\n  showIntentBanner('Welcome! Here is the Velocity X9 technical summary you asked ChatGPT about.');\n}"
            }
        })

    # --- 2. DEEP-LINKING ANCHOR PRESERVATION AUDIT ---
    headings_with_id = [h for h in parser.headings if h['id']]
    total_headings = len(parser.headings)

    if total_headings > 0 and len(headings_with_id) == 0:
        findings.append({
            "id": "ENGAGE-002",
            "title": "Missing Heading ID Anchors for Deep AI URL Citation Linking",
            "severity": "medium",
            "evidence": f"Found {total_headings} headings (<h1-h6>), but 0 have explicit 'id' attributes for URL hash deep-linking.",
            "suggested_action": {
                "summary": "Assign explicit, human-readable 'id' attributes to all major section headings.",
                "priority": "medium",
                "impact": "Allows AI assistants to construct exact hash citation links (e.g., page.html#specifications) preventing scroll state loss.",
                "code_snippet": '<h2 id="technical-specifications">Velocity X9 Technical Specifications</h2>'
            }
        })

    # --- 3. DIGITAL FENG SHUI: ABOVE-THE-FOLD FACT VISIBILITY ---
    # First 1500 chars of DOM represents immediate above-the-fold HTML
    above_the_fold_html = html[:1500].lower()
    has_static_specs = any(k in above_the_fold_html for k in ['spec', 'price', 'feature', 'material', 'weight', 'dimension'])
    
    has_accordions = len(parser.accordions) > 0
    has_spec_images = any('spec' in img.get('src', '').lower() or 'spec' in img.get('alt', '').lower() for img in parser.images)

    if not has_static_specs and (has_accordions or has_spec_images):
        findings.append({
            "id": "ENGAGE-003",
            "title": "Attribute Extraction Hallucination Hazard (Specs Hidden in Accordions/Images)",
            "severity": "high",
            "evidence": f"Core technical specifications are missing above the fold and trapped inside {len(parser.accordions)} accordion containers or image files.",
            "suggested_action": {
                "summary": "Extract key technical attributes into static, uncollapsed DOM markup using Schema.org/PropertyValue.",
                "priority": "high",
                "impact": "Prevents AI assistants from fabricating missing technical metrics during multi-brand comparisons.",
                "code_snippet": '<div itemprop="additionalProperty" itemscope itemtype="https://schema.org/PropertyValue">\n  <span itemprop="name">heel_drop</span>: <span itemprop="value">10mm</span>\n</div>'
            }
        })

    return findings


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    results = check_engagement(target)
    print(json.dumps(results, indent=2))