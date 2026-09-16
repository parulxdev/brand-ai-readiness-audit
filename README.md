# Brand AI-Readiness Audit

An agentskills.io marketplace that audits any website for two things: can AI assistants find it, and will a visitor from an AI citation stay?

Read-only, robots.txt-respecting, reports in under 5 minutes on CPU.

## The problem

AI assistants don't cite what they can't fetch, parse, or quote:

1. **Can't reach the page** — blocked by robots.txt, a WAF, or a stray noindex.
2. **Can't parse the page** — content hidden behind hydration, facts locked in image alt text, broken JSON-LD.
3. **Weak citation** — no dateModified, no sameAs, no quotable paragraph, so a competitor gets picked instead.

Every check here targets one of these three failure modes and says what to fix, in what order, and why.

## What's in it

Seven skills, one entrypoint, composed via `marketplace.json`:

```text
audit-orchestrator          ← entrypoint
├── discovery-audit         ← can the machine find + parse the page?
├── freshness-corroboration ← is content dated, sourced, corroborated?
├── engagement-audit        ← will an AI-referred visitor stay?
├── entity-dominance        ← does the brand own its knowledge-graph node?
├── vertical-intelligence   ← what kind of site is this?
└── prioritization-engine   ← scores findings, builds a 3-wave roadmap
```

Each skill is independently runnable; the orchestrator composes them, dedupes findings, and emits one report.

## Key design decisions

**1. Causal-lift is mechanism-keyed, not finding-ID-keyed.**
Mapping fix effort by finding ID (`DISC-002 → high`) breaks the moment a new finding is added. Instead, every finding is tagged with a `mechanism`: `config | template | content | architectural | external`. Lift is derived from mechanism, then promoted based on page signals — so new checks get accurate estimates for free.

**2. One fetch per resource, guaranteed.**
`/robots.txt` is fetched once per origin via a contextvars flag that short-circuits recursive checks. Cache keys exclude timeout, so retries at different timeouts hit the same cache entry. A typical audit makes 5–6 requests to the target origin, not 15.

**3. AI-bot UA spoofing.**
Each page is fetched with a browser UA, then re-fetched as GPTBot, ClaudeBot, and PerplexityBot. A different status or a >40% body-length difference flags a WAF or CDN treating AI crawlers differently — the check that catches sites invisible to ChatGPT but fine in every SEO tool.

## Output

A single schema-validated JSON object with findings, severity, mechanism, suggested fixes, and a wave-based roadmap:

```json
{
  "site": "example.com",
  "vertical": "saas",
  "summary": {"total_findings": 11, "critical": 1, "high": 4, "medium": 5, "low": 1},
  "findings": [
    {
      "id": "FRESH-002",
      "title": "Missing dateModified",
      "severity": "high",
      "mechanism": "template",
      "suggested_action": {
        "summary": "Emit ISO-8601 dateModified in JSON-LD when facts change.",
        "causal_lift": "high",
        "effort": "moderate"
      },
      "wave": 1
    }
  ],
  "roadmap": {
    "wave_1_do_now": [],
    "wave_2_plan": [],
    "wave_3_invest": []
  }
}
```

## Runtime envelope

| Constraint | Target | Actual |
|------------|--------|--------|
| Runtime | < 5 min | 30–90s typical |
| Submission size | ≤ 50 MB | well under |
| Dependencies | none required | stdlib-only core |
| Network | read-only | 1 robots.txt + 1 target fetch + cache hits |
| Storage | none | all in-memory |

## What it doesn't do

- Modify the target site — no writes, no auth, no POSTs
- Assume a browser — no Playwright/Selenium; Node renderer is optional
- Use visitor analytics — no GA, no server logs
- Depend on an external service — Wikidata/Wikipedia queried read-only with graceful degradation

## Skills

**discovery-audit** — 23 checks: crawler access (AI-bot robots.txt blocks, sitemap mismatches), structured data (JSON-LD validity, `@graph` refs), meta tags, JS-render gap, hidden text/prompt injection, AI-bot UA responsiveness.

**freshness-corroboration** — missing dateModified/Last-Modified/ETag, entity disambiguation deficits, single-source claims, freshness decay per fact class (pricing 30-day, specs 180, company 365).

**engagement-audit** — missing H1/heading anchors, no quotable 40–90 word answer paragraph, low citation density, no AI-referrer handling.

**entity-dominance** — Wikidata entity match, relationship density, location anchors (P159/P17).

**vertical-intelligence** — 50-vertical taxonomy via keyword scoring, emits vertical + confidence + tailored recommendations.

**prioritization-engine** — scores by impact × confidence / effort × urgency; assigns waves (≥0.7 do now, 0.4–0.7 plan, <0.4 invest). Inlines the causal-lift estimator; no finding-ID coupling.

## Running it locally

```bash
python3 skills/audit-orchestrator/scripts/synthesize_report.py https://example.com
python3 skills/audit-orchestrator/scripts/synthesize_report.py https://example.com --json-out report.json
python3 skills/audit-orchestrator/scripts/synthesize_report.py https://example.com --no-errors

# individual skills
python3 skills/discovery-audit/scripts/check_discovery.py https://example.com
python3 skills/entity-dominance/scripts/check_entity_dominance.py https://stripe.com
```

Stdlib only — no install required. Optional NER boost via `requirements-optional.txt` (spaCy), falls back to regex if absent.

## Repository layout

```text
brand-ai-readiness-audit/
├── marketplace.json
├── README.md
├── CHANGELOG.md
├── requirements.txt
├── requirements-optional.txt
├── lib/
│   ├── utils.py         ← HTTP, robots, HTML parser
│   └── ner.py            ← optional spaCy, regex fallback
└── skills/
    ├── audit-orchestrator/
    ├── discovery-audit/
    ├── freshness-corroboration/
    ├── engagement-audit/
    ├── entity-dominance/
    ├── vertical-intelligence/
    └── prioritization-engine/
```

Each skill folder is spec-compliant: YAML frontmatter, `references/` for checklists, `scripts/` for logic.

## What makes it different

1. Distinguishes "unreachable" from "unquotable" — different problems, different fixes.
2. Scores effort by mechanism, not finding ID — new checks don't break prioritization.
3. Probes with AI-bot user agents — the only reliable way to catch a CDN silently serving different content to GPTBot.
