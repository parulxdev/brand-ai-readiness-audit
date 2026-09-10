---
name: freshness-corroboration
description: Audits web page temporal lineage, HTTP caching headers, modified timestamps, and entity graph corroboration via sameAs links.
license: MIT
---

# Freshness & Lineage Corroboration Audit

## When to Use
Use to verify fact recency, cache invalidation directives, and external entity corroboration.

## Inputs
- `target_url` (string)

## Procedure
1. Inspect HTTP response headers for `Last-Modified` and `ETag`.
2. Parse JSON-LD structured data for `dateModified` timestamps.
3. Check JSON-LD for `sameAs` entity graph references (Wikidata, Wikipedia, social profiles).

## Output
Emits finding objects detailing freshness or lineage defects.