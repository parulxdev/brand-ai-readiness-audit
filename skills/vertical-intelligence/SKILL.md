---
name: vertical-intelligence
description: Inspects target website DOM signals and metadata to classify the industry vertical (e.g., e-commerce, airline, saas, hospitality, news, general).
license: MIT
---

# Vertical Intelligence

## When to Use
Use during the initial phase of a brand audit to identify the target domain's core business vertical for tailors recommendations.

## Inputs
- `target_url` (string): The URL of the website to analyze.

## Procedure
1. Fetch target HTML using `shared/utils.py`.
2. Inspect meta tags, JSON-LD `@type` properties, and keywords.
3. Classify domain into standard vertical (`e-commerce`, `airline`, `saas`, `hospitality`, `news`, or `general`).

## Output Format
```json
{
  "vertical": "e-commerce",
  "confidence": 0.95
}