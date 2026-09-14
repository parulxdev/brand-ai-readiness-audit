# Priority Model

    score = normalize( impact × confidence / effort × urgency )

- **impact** = severity_weight × vertical_weight(family)
- **confidence** = f(evidence length, digit presence, causal-lift certainty)
- **effort** = 1 / causal_lift (high → 0.9, medium → 0.5, low → 0.25)
- **urgency** = 1 + freshness_velocity (only FRESH-012)

## Waves

| Wave | Rule |
|---|---|
| 1 (do-now) | score ≥ 0.7 OR (causal_lift == high AND severity ∈ {critical, high}) |
| 2 (plan)   | 0.4 ≤ score < 0.7 |
| 3 (invest) | score < 0.4 OR causal_lift == "low" |