---
name: freshness-corroboration
description: Evaluates fact shelf-life and cross-source corroboration for a given URL. Detects entity disambiguation deficits (Organization/Brand JSON-LD present but no disambiguatingDescription and no Wikidata/Wikipedia/Crunchbase sameAs), missing dateModified provenance timestamps, cross-domain corroboration deficits, single-source fragility (bold/strong/quoted numeric claims with no outbound links to authoritative non-own-domain sources), and external knowledge-graph absence (queried against Wikipedia's public API to check if the brand is corroborated outside its own site). Recurses safely into nested JSON-LD @graph structures. Use when diagnosing why an AI assistant confidently states a stale fact, why a brand is confused with an identically-named entity, why a well-sourced claim is treated as marketing copy, or why the site's assertions are not corroborated by external sources. Uses optional spaCy NER for precise entity vs. stop-word discrimination; falls back to regex if the model is unavailable.
license: MIT
---
## When to use
Use when auditing fact recency and cross-source agreement. Also use when diagnosing entity confusion (name collisions) or single-source claims that RAG systems discard.

## Inputs
- `target_url` (string, required): Full URI or bare domain.

## Procedure
1. Run `scripts/check_freshness.py`.
2. Inspect JSON-LD for dateModified, disambiguatingDescription, and sameAs.
3. Extract the brand name and query Wikipedia via `scripts/corroborate.py`.
4. Return an array of findings.

## Output
List of finding dicts conforming to the marketplace schema.

## References
- `references/freshness_checks.md`

## Allowed tools
- `python_interpreter`