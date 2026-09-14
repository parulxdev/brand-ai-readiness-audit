---
name: engagement-audit
description: Evaluates on-site engagement readiness for a given URL — the retention half of the AI-readiness problem. Detects structural citation blockers (no heading id anchors, no <h1>, fact-bearing headings without ids) and content-retention blockers: no quotable 40-90 word answer paragraph combining a named entity and quantified fact, above-the-fold fact density deficits in the first ~2000 characters, missing next-action affordances (forms/CTAs/search boxes), absence of AI-referrer context handling (no document.referrer inspection for chatgpt.com/perplexity.ai/claude.ai referrals), section openers that don't begin with a direct answer, and low citation density per 1000 words. Uses optional spaCy NER for precise entity vs. stop-word discrimination, with regex fallback. Use when diagnosing why visitors arriving from an AI citation bounce, why an AI summarizer cites a competitor instead, or why deep-link citations to your content fail.
license: MIT
---
## When to use
Use when auditing on-site retention and structural readiness for RAG extraction. Also use to verify citation-readiness and answer-first section structure.

## Inputs
- `target_url` (string, required): Full URI or bare domain.

## Procedure
1. Run `scripts/check_engagement.py`.
2. Inspect heading anchors, `<h1>` presence, paragraph structure, section-openers, above-fold density.
3. Return an array of findings.

## Output
List of finding dicts conforming to the marketplace schema.

## References
- `references/engagement_checks.md`

## Allowed tools
- `python_interpreter`