---
name: prioritization-engine
description: Multi-axis priority scoring, wave assignment, and roadmap assembly. Inlines a mechanism-keyed causal-lift estimator — each finding declares `mechanism` ∈ {config, template, content, architectural, external}; page signals promote lift for content/architectural findings when the raw material already exists. Deterministic; no LLM; no finding-ID coupling. Emits `priority_score`, `causal_lift`, `causal_lift_reasoning`, `effort`, and `wave` on every finding, plus a top-level enriched roadmap.
license: MIT
allowed-tools: [python_interpreter]
---

## When to use

Invoked by `audit-orchestrator` once, after all detection skills have
run and findings have been schema-validated. Never invoked directly by
the evaluation harness.

## Inputs

- `findings` (list[dict], required) — each finding carries `mechanism`,
  `severity`, `evidence`, and `suggested_action`.
- `signals` (dict, optional) — page-level booleans emitted by the
  orchestrator: `has_any_jsonld`, `has_section_tags`,
  `has_visible_date`, `has_quantified_facts`, `has_robots`,
  `has_sitemap`.
- `vertical` (string, optional, default "general") — vertical label from
  `vertical-intelligence`; mapped to a weight family internally.
- `freshness_velocity` (float, optional, default 0.0) — decays FRESH-012
  urgency multiplier.

## Procedure

1. **Causal-lift.** For each finding, look up `mechanism` in the base
   lift/effort tables. Apply mechanism-specific signal promotions (only
   promote, never demote). Write `causal_lift`, `causal_lift_reasoning`,
   and `effort` into `suggested_action`.
2. **Confidence.** Compute a scalar in [0, 1] from the finding's
   evidence — presence of concrete HTTP status / measured counts, not
   evidence verbosity.
3. **Score.** `score = normalize(impact × confidence / effort × urgency)`
   where:
   - `impact = severity_weight × vertical_weight(family)`
   - `effort = inverse of lift`
   - `urgency = 1 + freshness_velocity` (only for `FRESH-012`)
4. **Wave.** Assign `wave` ∈ {1, 2, 3} per the threshold table in
   `references/priority_model.md`.
5. **Roadmap.** Build the enriched roadmap — entries carry `id`, `title`,
   `severity`, `priority_score`, `causal_lift`, `effort`, and `action`
   so the report is actionable without cross-referencing the findings
   array.

## Output

The input `findings` list, enriched in place, plus a roadmap dict of the
shape `{wave_1_do_now: [...], wave_2_plan: [...], wave_3_invest: [...]}`.

## References

- `references/priority_model.md` — thresholds, weight tables, and the
  mechanism taxonomy.

## Allowed tools

- Python interpreter (stdlib only).