# Output Schema

## Required

- Top-level: `site`, `audited_at`, `summary`, `findings`.
- `summary`: `total_findings`, `critical`, `high`, `medium`, `low`.
- Per finding: `id`, `title`, `severity`, `evidence`, `suggested_action`.
- `suggested_action`: `summary`, `priority`.

## Vocabulary

- `severity`, `priority` ∈ {critical, high, medium, low}.
- `causal_lift` ∈ {high, medium, low}.
- `effort` ∈ {trivial, moderate, significant}.
- `wave` ∈ {1, 2, 3}.
- Finding prefixes: `DISC-*`, `FRESH-*`, `ENG-*`.

## Optional additive fields

| Field | Meaning |
|---|---|
| `vertical`, `vertical_confidence` | Vertical classification. |
| `roadmap` | `{wave_1_do_now[], wave_2_plan[], wave_3_invest[]}`. |
| `proactive_recommendations` | Beyond-defect suggestions. |
| `errors` | Runtime errors (suppressed by `--no-errors`). |
| `diagnostics` | Non-error info (suppressed by `--no-errors`). |
| Per-finding `wave` | 1 / 2 / 3. |
| `suggested_action.causal_lift`, `.causal_lift_reasoning`, `.priority_score`, `.effort` | Enrichment. |
| `suggested_action.wave`, `.impact`, `.code_snippet` | Additional suggested-action enrichment. If both finding-level `wave` and `suggested_action.wave` are present, they should match. |

## Example

```json
{
  "site": "example.com",
  "audited_at": "2026-09-13T09:12:00Z",
  "vertical": "saas",
  "vertical_confidence": 0.7,
  "summary": {"total_findings": 11, "critical": 1, "high": 4, "medium": 5, "low": 1},
  "findings": [
    {
      "id": "FRESH-002",
      "title": "Missing dateModified",
      "severity": "high",
      "evidence": "...",
      "suggested_action": {
        "summary": "...",
        "priority": "high",
        "priority_score": 0.82,
        "wave": 1,
        "effort": "trivial",
        "causal_lift": "high",
        "causal_lift_reasoning": "A visible 'last updated' date exists — mirror it into dateModified.",
        "impact": "...",
        "code_snippet": "..."
      },
      "wave": 1
    }
  ],
  "roadmap": {
    "wave_1_do_now": ["FRESH-002"],
    "wave_2_plan":   ["ENG-008"],
    "wave_3_invest": ["FRESH-009"]
  },
  "proactive_recommendations": ["..."],
  "errors": [],
  "diagnostics": []
}