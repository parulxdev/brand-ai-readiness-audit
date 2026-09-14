---
name: audit-orchestrator
description: ENTRYPOINT skill. Composes discovery-audit, freshness-corroboration, engagement-audit, vertical-intelligence, entity-dominance, and prioritization-engine (which inlines a mechanism-keyed causal-lift estimator) into one JSON report. Detects off-site discoverability gaps and on-site engagement gaps, scores each finding on impact × confidence × effort × urgency, assigns waves, and emits a three-wave roadmap plus proactive recommendations. Use whenever a full audit report for a URL is requested.
license: MIT
allowed-tools: [python_interpreter]
---

## When to use

Invoked by the evaluation harness when a full audit report for a target
website is requested. It is the sole entrypoint declared in
`marketplace.json`.

## Inputs

- `target_url` (string, required) — full URI or bare domain.
- `budget_seconds` (int, optional, default 180) — soft deadline; safe
  fetches abort when exhausted.
- `include_errors` (bool, optional, default True) — include `errors` and
  `diagnostics` arrays in the emitted report.

## Procedure

1. `clear_cache()` and `set_deadline(now + budget_seconds)`.
2. Normalize `target_url`; parse origin; `get_robots().load(origin)`.
3. Classify vertical via `vertical-intelligence`.
4. Run detection skills in sequence, collecting findings:
   `discovery-audit`, `freshness-corroboration`, `engagement-audit`,
   `entity-dominance`.
5. Enforce the finding schema — every finding must have
   `id`, `title`, `severity`, `evidence`, `mechanism`, and a
   `suggested_action` with `summary` and `priority`. Deduplicate by
   `(id, title, sha1(evidence)[:12])`.
6. Collect page signals via `_page_signals_from` (JSON-LD present,
   sectioning tags, quantified facts, visible date, robots.txt presence,
   sitemap presence).
7. Extract `freshness_velocity` from the `FRESH-012` evidence if present.
8. Invoke `prioritization-engine.prioritize(findings, signals=...,
   vertical=..., freshness_velocity=...)`. This assigns each finding
   `mechanism`-keyed `causal_lift`, `effort`, `priority_score`, and
   `wave`, then builds the enriched roadmap.
9. Emit the audit report against the schema in
   `references/output_schema.md`.

## Output

A single JSON object with the required top-level fields `site`,
`audited_at`, `summary`, `findings`, plus the additive fields `vertical`,
`vertical_confidence`, `roadmap`, `proactive_recommendations`, and
(when `include_errors` is True) `errors` and `diagnostics`.

## References

- `references/output_schema.md` — the full report schema and vocabulary.

## Allowed tools

- Python interpreter (stdlib only).
- Standard shell (`curl`, `grep`) for diagnostics if needed.
- Optional: `node` — only used by `discovery-audit` for the JS-render
  gap; degrades gracefully if absent.