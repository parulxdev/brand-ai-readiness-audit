# Brand AI-Readiness Audit

**AI assistants don't cite what they can't fetch, read, or quote.** This marketplace finds out which of those three is happening to your site — and fixes it in priority order.

Read-only. Robots-respecting. Under 5 minutes on CPU. Seven skills, one entrypoint, zero `pip install`.

---

## The Problem

Three failure modes. In order. Each invisible until it costs you traffic.

1. **Crawler can't reach you** — robots.txt, WAF, forgotten noindex.
2. **Crawler reaches you but can't parse you** — hydration-locked content, facts in image alt text, silently-broken JSON-LD.
3. **Assistant finds you but won't quote you** — no `dateModified`, no `sameAs`, no quotable paragraph. Competitor with all three wins.

Every check catches one of these on a specific URL and says *what to change, in what order, why it matters*.

---

## What's In It

```text
audit-orchestrator          ← entrypoint, composes everything below
├── discovery-audit         ← can the machine find + parse the page?
├── freshness-corroboration ← is the content dated, sourced, corroborated?
├── engagement-audit        ← will the AI-referred visitor stay?
├── entity-dominance        ← does the brand own its knowledge-graph node?
├── vertical-intelligence   ← what kind of site, what matters here?
└── prioritization-engine   ← scores findings → 3-wave roadmap