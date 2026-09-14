# Discovery Checks — Mechanism & Justification

## Baseline access

- **DISC-001** — `/llms.txt` presence. The emerging LLM-index convention. Its absence is a low-cost signal that the site has not opted into clean machine-readable context for RAG systems.
- **DISC-001b** — `/llms.txt` content-type. A 200 response served as `text/html` is a soft 404 — RAG parsers may treat the payload as markup rather than plain text.
- **DISC-010** — `/llms-full.txt` companion. Many LLM pipelines prefer the full index when the short one exists.

## Crawler access

- **DISC-002** — AI crawler blocking. Detects root-level `Disallow: /` (or `/*`) for GPTBot, ClaudeBot, PerplexityBot, anthropic-ai, cohere-ai. Root-block only; path-scoped disallows are ignored to avoid false positives.
- **DISC-007** — Sitemap-vs-robots contradiction. Stateful check: reads sitemap URLs and cross-references against robots rules. Conflicting signals cause RAG crawlers to skip pages the site intended to expose.

## Structured data

- **DISC-003** — Brand / Organization / ItemList / Product JSON-LD. Entities give AI systems something to resolve. Without JSON-LD, brand name and product facts are inferred from prose, which is lossy.
- **DISC-011** — WebSite + SearchAction. Provides AI systems a canonical citation entry point.
- **DISC-012** — `meta robots noindex`. Hard blocker. Overrides all other discovery signals.

## Content extraction

- **DISC-004** — JavaScript-render gap. Compares raw HTML visible text against post-hydration visible text (Node/jsdom). A ratio > 1.6 with a raw gain > 500 chars means primary facts are client-side hydrated.
- **DISC-005** — Numbers locked in image alt text. Detects numeric facts that appear only in `<img alt>`/`src`, never in visible text — common on e-commerce and pricing pages. Only flags facts not duplicated in visible text.

## RAG chunking and semantics

- **DISC-013** — Semantic chunking affordances. RAG pipelines chunk on 200-500 token boundaries. `<section>`/`<article>`/`<main>` give the chunker semantic hints; unstructured `<div>` soup forces token-count chunking and fragments facts.
- **DISC-016** — `speakable` schema. Google's declared signal for voice/answer surfaces. Its absence means voice assistants and AI summaries have no page-author hint about what to quote.

## Safety

- **DISC-014** — Hidden text / prompt injection surface. Detects CSS-hidden text (`display:none`, `position:absolute;left:-9999px`, `opacity:0`, `aria-hidden="true"` with visible content) and known injection phrases ("ignore previous instructions", "as an AI language model"). Two-fold value: catches accidental hidden content that pollutes RAG, and flags deliberate injection attempts.

## Conversational queries

- **DISC-015** — Conversational query schemas. FAQPage, QAPage, HowTo, Question. Users ask AI assistants full questions; these schemas map questions to answers and are directly consumed by conversational retrieval.

## Canonical URL

- **DISC-020** — `<link rel="canonical">` missing. Without it, AI assistants
  may cite a parameterized or duplicated URL variant; ranking and citation
  signals are diluted across URL variants.

## Open Graph metadata

- **DISC-021t** — Missing `og:title`.
- **DISC-021d** — Missing `og:description`.
- **DISC-021i** — Missing `og:image`.
  AI summarizers and LLM preview surfaces consume OG metadata as the shortest
  representation of the page. Absence forces arbitrary text extraction, often
  producing off-topic summaries.

## Structured-data integrity

- **DISC-022** — Locale path without `hreflang` declarations. Fires only when
  the URL contains a locale segment (e.g. `/en-IN/`) and no `hreflang` link
  tags are present. AI assistants rely on hreflang to surface the correct
  regional variant.
- **DISC-023** — JSON-LD `@graph` contains unresolved `@id` references. A
  structurally valid graph where a nested `@id` does not resolve to a node
  in the same array. AI entity resolvers may fail to link related nodes.

## AI-bot responsiveness

- **DISC-018** — AI bot receives a different HTTP status than the browser-like
  fetch. Fires when probing with GPTBot / ClaudeBot / PerplexityBot UA returns
  a status that differs from the baseline. Skipped when the bot is
  robots-disallowed at root, and skipped when the probe itself fails
  (status 0).
- **DISC-019** — AI bot receives truncated or swapped content. Fires when
  the probe succeeds but the body length differs by > 40% from baseline.