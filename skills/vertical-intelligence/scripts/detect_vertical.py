#!/usr/bin/env python3
"""
Vertical Intelligence Skill Script
Detects whether a target domain is E-Commerce, Airline, SaaS, Hospitality, News, or General.
Inspects Schema.org JSON-LD types, key HTML signals, and meta tags.
"""


import sys
import json
import os

# Add parent shared folder to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../shared')))
from utils import safe_fetch, parse_html_content


def detect_vertical(target_url):
    fetch_res = safe_fetch(target_url)
    if fetch_res['error'] or not fetch_res['body']:
        return {
            "vertical": "general",
            "confidence": "low",
            "reason": f"Fetch failed: {fetch_res['error'] or 'Empty body'}"
        }

    parsed = parse_html_content(fetch_res['body'])
    body_text_lower = fetch_res['body'].lower()

    # 1. Inspect Schema.org JSON-LD Blocks for Explicit Types
    schema_types = set()
    for block in parsed.json_ld_blocks:
        if isinstance(block, dict):
            stype = block.get('@type')
            if isinstance(stype, str):
                schema_types.add(stype.lower())
            elif isinstance(stype, list):
                for st in stype:
                    if isinstance(st, str):
                        schema_types.add(st.lower())

    # Vertical Signatures Mapping
    if any(st in schema_types for st in ['flight', 'airline', 'flightreservation']):
        return {"vertical": "airline", "confidence": "high", "reason": "Explicit Flight/Airline Schema.org type detected"}

    if any(st in schema_types for st in ['product', 'offer', 'itemlist', 'shoppingcart', 'store']):
        return {"vertical": "e-commerce", "confidence": "high", "reason": "Explicit Product/Offer/ItemList Schema.org type detected"}

    if any(st in schema_types for st in ['hotel', 'lodgingbusiness', 'hotelroom', 'reservation']):
        return {"vertical": "hospitality", "confidence": "high", "reason": "Explicit Hotel/Lodging Schema.org type detected"}

    if any(st in schema_types for st in ['newsarticle', 'reportagearticle']):
        return {"vertical": "news", "confidence": "high", "reason": "Explicit NewsArticle Schema.org type detected"}

    if any(st in schema_types for st in ['softwareapplication', 'saas', 'techarticle']):
        return {"vertical": "saas", "confidence": "high", "reason": "Explicit SoftwareApplication Schema.org type detected"}

    # 2. Heuristic Keyword & Semantic DOM Fallbacks
    if any(term in body_text_lower for term in ['flight', 'boarding pass', 'origin airport', 'destination airport', 'book flight']):
        return {"vertical": "airline", "confidence": "medium", "reason": "Airline semantic keywords detected in DOM"}

    if any(term in body_text_lower for term in ['add to cart', 'buy now', 'checkout', 'free shipping', 'sku']):
        return {"vertical": "e-commerce", "confidence": "medium", "reason": "E-Commerce transactional triggers detected"}

    if any(term in body_text_lower for term in ['book a room', 'check-in date', 'check-out date', 'guests', 'amenities']):
        return {"vertical": "hospitality", "confidence": "medium", "reason": "Hospitality booking controls detected"}

    if any(term in body_text_lower for term in ['free trial', 'pricing plans', 'api documentation', 'enterprise tier', 'saas']):
        return {"vertical": "saas", "confidence": "medium", "reason": "SaaS trial/pricing keywords detected"}

    if any(term in body_text_lower for term in ['editorial', 'breaking news', 'journalism', 'press release', 'published on']):
        return {"vertical": "news", "confidence": "medium", "reason": "Publishing/News terms detected"}

    return {"vertical": "general", "confidence": "low", "reason": "No strong vertical-specific schemas or keywords identified"}


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    result = detect_vertical(target)
    print(json.dumps(result, indent=2))