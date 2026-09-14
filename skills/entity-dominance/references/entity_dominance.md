# Entity Dominance — Mechanism & Justification

Presence of an entity in a knowledge graph is not the same as **dominance** of
that entity. A brand can have a Wikidata item and still be invisible to
entity-resolution pipelines because the item is ambiguous, sparse, or
unlinked. The three checks below measure that gap.

## Brand inference (precondition)

Before any check runs, the brand name is inferred from the page — in this
order:

1. `@type: Organization` or `@type: Brand` node with a `name` field, found by
   walking the JSON-LD `@graph` (or the flat JSON-LD array) iteratively.
2. `<meta property="og:site_name">` if JSON-LD yields nothing.
3. The first `<h1>` text if OG metadata is also missing.

If none of the three succeed, the skill emits zero findings and exits. This
is deliberate: entity checks require a named entity to query, and guessing
a brand name from ambiguous page text would produce false positives on
most multi-brand or aggregator sites.

## FRESH-009 — Identity clarity

**Question:** does an exact-label Wikidata item exist for this brand?

**Mechanism:** `wbsearchentities` returns up to 10 candidates for the brand
string. Three cases:

- **0 candidates** → no knowledge-graph anchor exists. Severity: **high**.
  AI systems resolving the brand by name have nothing authoritative to
  attach facts to.
- **≥1 candidates, 0 with an exact lowercase-label match** → the brand is
  ambiguous. Severity: **high** if ≥5 candidates, else **medium**. AI
  assistants resolving the brand to an entity cannot tell which candidate
  is the brand — they may cite the wrong one.
- **≥1 exact match, ≥5 candidates total** → name-collision risk. Severity:
  **medium**. The brand has an entity, but it competes with other entities
  for the same surface form.

The signal to fix is not "no Wikidata item" — it's "no *unambiguous*
Wikidata item". The recommendation is always `disambiguatingDescription`
plus a `sameAs` link from the site's Organization JSON-LD, so the AI has
two independent anchors agreeing on identity.

**Mechanism tag:** `external` — depends on Wikidata community curation and
notability, outside single-site control. Lift is low because the fix is
not a code change; the site can only influence it via `sameAs`.

## FRESH-010 — Claim consistency (location anchor)

**Question:** does the Wikidata item declare a headquarters (`P159`) or
country (`P17`)?

**Mechanism:** location anchors are load-bearing for two classes of AI
query:

- **Local-intent queries** ("cloud providers in Berlin") — the AI filters
  candidates by location before ranking.
- **Region-scoped queries** ("Delhi to Mumbai flights") — the AI prefers
  entities that declare a base in the query's region.

An item with neither property cannot be ranked by either filter, even if
it is otherwise complete.

**Mechanism tag:** `external`. Lift is low — the site cannot add Wikidata
claims directly; the fix is to enrich the item (or coordinate with
whoever owns it) and then reflect the same facts in the site's JSON-LD
with `sameAs` to establish consensus.

## FRESH-011 — Relationship density

**Question:** how many typed statements does the Wikidata item carry?

**Mechanism:** wikidata's own indexing and downstream entity-resolution
systems score items partly by graph density. Items with only a handful of
statements are treated as low-confidence — they may be stubs, orphans, or
duplicates. The **threshold of 15 typed statements** is not arbitrary; it
sits above the stub tier (typically 3–8 statements) and below the
well-developed tier (typically 40+), matching the range where AI
pipelines begin to prefer an item over unstructured page text.

**Mechanism tag:** `external`. Lift is low, same reasoning as FRESH-010.

## What the skill does *not* do

- **Does not query Wikipedia.** The Wikipedia-corroboration check (FRESH-007
  and FRESH-008) lives in `freshness-corroboration/scripts/corroborate.py`.
  Keeping the two skills separate avoids double-charging an HTTP call for
  the same underlying entity.
- **Does not edit Wikidata.** The skill is read-only. All three findings
  are recommendations.
- **Does not assume Wikidata is reachable.** `_http_json` is deadline-aware
  and returns `None` on any error. When that happens, the corresponding
  check is skipped and no finding is emitted — the audit does not crash
  on a network failure at `query.wikidata.org`.
- **Does not infer brand from `<title>` or page text.** Only from JSON-LD,
  OG metadata, or `<h1>` — in that order. Broader inference was tested
  and produced false positives on news sites, aggregators, and
  marketplaces where the `<title>` names an article, not a brand.