---
name: vertical-intelligence
description: Classifies the audited site into one of 50 industry verticals using URL-path-weighted keyword scoring with word-boundary matching and margin thresholds. Returns a vertical label, a raw score, and a confidence value for the orchestrator to select vertical-specific proactive recommendations. The taxonomy spans core commercial (e-commerce, saas, airline, hotel, news, healthcare, real-estate, automotive, fintech), professional services (hrtech, martech, govtech, consulting, legaltech, insurtech), industrial (manufacturing, logistics, supply-chain, defense, aerospace, telecommunications, energy, construction), media (entertainment, sports, publishing, e-sports, gaming), lifestyle (travel, hospitality, restaurant, fashion, beauty, fitness), and frontier tech (biotech, deeptech, ai-ml, cybersecurity, cleantech, agtech, proptech, edtech, medtech). Use when the audit requires vertical-specific recommendation tuning or when the evaluator asks "what kind of site is this." Proactive recommendations for each vertical are embedded in this skill's output so the orchestrator remains a pure router.
license: MIT
---
## When to use
Use to apply taxonomy tags and to attach vertical-specific proactive recommendations to the audit report.

## Inputs
- `target_url` (string, required): Full URI or bare domain.

## Procedure
1. Fetch and strip the page to visible text.
2. Score each vertical using word-boundary keyword matches, weighting URL path matches higher.
3. Apply a minimum threshold and margin check.
4. Return `{ vertical, confidence, recommendations }`.

## Output
Dict (consumed by the orchestrator, not treated as findings).

## References
- `references/taxonomy.md`

## Allowed tools
- `python_interpreter`