# Freshness & Corroboration Checks

## HTTP-level freshness

- **FRESH-004** — Missing `Last-Modified` / `ETag`. Header-level signals let
  incremental crawlers cheaply detect updates; without them, re-fetch or skip.

## Entity resolution

- **FRESH-001** — Entity Disambiguation Deficit. Organization/Brand JSON-LD
  without `disambiguatingDescription` and without an authoritative `sameAs`.
- **FRESH-003** — Cross-Domain Corroboration Deficit. Zero `sameAs` links to
  Wikidata/Wikipedia/Crunchbase.

## Recency

- **FRESH-002** — Missing `dateModified` in JSON-LD.

## Cross-source agreement

- **FRESH-006** — Single-Source Fragility. Emphasized/quoted/attributed numeric
  claims without outbound authoritative links.
- **FRESH-007** — No Wikipedia match.
- **FRESH-008** — Wikipedia entity exists but not linked via `sameAs`.

## Decay velocity (Idea 2)

- **FRESH-012** — High Freshness Decay Velocity.

| Fact class | Half-life |
|---|---|
| Pricing, availability | 30 days |
| Regulatory, promotions | 90 days |
| Specs, integrations | 180 days |
| Company history | 365 days |

Velocity = `(days_since_newest / half_life)`. Values ≥ 3.0 raise FRESH-012.

## Date-source policy

- **FRESH-002** uses only JSON-LD presence for the finding; visible dates near
  a freshness keyword sharpen the evidence message but never suppress the
  finding.
- **FRESH-012** takes `max()` across all trustworthy sources (JSON-LD,
  HTTP `Last-Modified`, visible keyword-adjacent dates). Future dates dropped.
  The newest non-future date drives velocity.

## NER backend

FRESH-006 uses spaCy's `en_core_web_sm` when available, else a regex
stop-word + capital-letter fallback. Diagnostics array records which ran.