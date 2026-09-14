---
name: discovery-audit
description: Evaluates off-site discoverability for a target URL. Checks /llms.txt and /llms-full.txt presence and content-type, robots.txt AI-bot root blocks (GPTBot, ClaudeBot, PerplexityBot, anthropic-ai, cohere-ai), Brand/Organization JSON-LD, WebSite+SearchAction, meta-robots noindex, canonical URL declaration, Open Graph metadata (og:title, og:description, og:image), JS-render gaps (Node + jsdom or heuristic fallback), image-metadata numeric facts (alt/title/aria-label), sitemap-vs-robots contradictions using the robots-declared sitemap URL, semantic chunking affordances, hidden-text/prompt-injection surfaces, conversational-query schemas (FAQPage/QAPage/HowTo/Question/Answer), malformed JSON-LD, @graph unresolved @id references, speakable schema (vertical-gated), and AI-bot UA responsiveness (does GPTBot/ClaudeBot/PerplexityBot receive a different response than a browser-like UA?).
license: MIT
---

## When to use

Invoked by `audit-orchestrator` as the first detection stage. Also runnable standalone for debugging:

    python skills/discovery-audit/scripts/check_discovery.py https://example.com

## Inputs

- `target_url` (string, required) — full URI or bare domain. Bare domains are normalized to `https://`.

## Procedure

1. Fetch `/llms.txt`, `/llms-full.txt`, `/robots.txt`, the target URL, and the robots-declared sitemap (falling back to `/sitemap.xml`).
2. Parse robots.txt and evaluate DISC-002 (AI-bot root blocks) per configured bot, honoring wildcard-group inheritance.
3. On the target HTML, evaluate the DISC-003…DISC-017 structured-data, meta, render, and content checks.
4. Evaluate DISC-018/019 by re-probing the target with each AI bot UA — skipping bots that are robots-disallowed at root, and skipping probes that fail with a transient error (status 0).
5. Evaluate DISC-020…DISC-023 (canonical, Open Graph, @graph integrity).
6. Cross-reference sitemap URLs against robots rules (DISC-007).
7. Attach `mechanism` to every finding via the module-scope `_MECHANISM_BY_ID` map.

## Output

A list of finding dicts, each with `id`, `title`, `severity`, `evidence`, `mechanism`, and `suggested_action` (containing at minimum `summary` and `priority`).

## References

- `references/discovery_checks.md` — per-check mechanism and justification.

## Allowed tools

- Python interpreter (stdlib only).
- Optional: `node` — required only for the accurate JS-render-gap check (DISC-004). Without Node, the code falls back to a heuristic (raw visible text < 150 chars + ≥ 5 scripts + mount element).