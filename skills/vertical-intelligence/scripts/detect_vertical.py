#!/usr/bin/env python3
"""
Vertical Intelligence Sub-skill Script.
Auto-detects site vertical (e-commerce, airline, saas, hospitality, news, general)
using HTML structural signals, Schema.org types, meta tags, and URL patterns.
"""

import os
import sys
import json

# Ensure shared utils can be imported relative to skills directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from shared.utils import safe_fetch, parse_html_content


def detect_vertical(target_url):
    fetch_res = safe_fetch(target_url)
    if fetch_res['error'] or not fetch_res['body']:
        return {
            "vertical": "general",
            "confidence": 0.3,
            "evidence": f"Failed to fetch content or empty response ({fetch_res['error']}). Defaulted to general."
        }

    html = fetch_res['body']
    parser = parse_html_content(html)
    url_lower = target_url.lower()

    scores = {
        "e-commerce": 0,
        "airline": 0,
        "saas": 0,
        "hospitality": 0,
        "news": 0
    }

    # 1. Schema.org Entity Inspection
    for block in parser.json_ld_blocks:
        if isinstance(block, dict):
            schema_type = str(block.get('@type', '')).lower()
            if 'product' in schema_type or 'offer' in schema_type or 'store' in schema_type:
                scores['e-commerce'] += 5
            elif 'flight' in schema_type or 'airline' in schema_type:
                scores['airline'] += 5
            elif 'softwareapplication' in schema_type or 'techarticle' in schema_type:
                scores['saas'] += 5
            elif 'hotel' in schema_type or 'lodgingbusiness' in schema_type or 'resort' in schema_type:
                scores['hospitality'] += 5
            elif 'newsarticle' in schema_type or 'reportage' in schema_type:
                scores['news'] += 5

    # 2. Structural & Text Keyword Signals
    html_lower = html.lower()
    
    # E-commerce indicators
    if any(k in html_lower for k in ['add to cart', 'add to bag', 'checkout', 'shopping-cart', 'price', 'sku']):
        scores['e-commerce'] += 3
    
    # Airline indicators
    if any(k in html_lower for k in ['flight', 'book flight', 'boarding pass', 'round trip', 'one way', 'airline']):
        scores['airline'] += 3

    # SaaS indicators
    if any(k in html_lower for k in ['pricing plans', 'free trial', 'api docs', 'sign up free', 'documentation', 'enterprise plan']):
        scores['saas'] += 3

    # Hospitality indicators
    if any(k in html_lower for k in ['check-in', 'check-out', 'book room', 'amenities', 'guests', 'suite']):
        scores['hospitality'] += 3

    # News indicators
    if any(k in html_lower for k in ['editorial', 'breaking news', 'published on', 'journalist', 'press release', 'opinion']):
        scores['news'] += 3

    # 3. URL heuristics
    if any(k in url_lower for k in ['shop', 'store', 'cart']):
        scores['e-commerce'] += 2
    elif any(k in url_lower for k in ['fly', 'air', 'airline', 'flights']):
        scores['airline'] += 2
    elif any(k in url_lower for k in ['app', 'io', 'saas', 'docs']):
        scores['saas'] += 2
    elif any(k in url_lower for k in ['hotel', 'resort', 'stay', 'booking']):
        scores['hospitality'] += 2

    best_vertical = max(scores, key=scores.get)
    highest_score = scores[best_vertical]

    if highest_score < 3:
        return {
            "vertical": "general",
            "confidence": 0.5,
            "evidence": "Low keyword/schema signal variance across standard verticals."
        }

    return {
        "vertical": best_vertical,
        "confidence": min(1.0, round(highest_score / 10.0, 2)),
        "evidence": f"Detected strong structural and schema indicators for vertical: '{best_vertical}' (signal weight score: {highest_score})."
    }


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    res = detect_vertical(target)
    print(json.dumps(res, indent=2))