---
name: entity-dominance
description: Scores how strongly a brand owns its entity across open knowledge graphs. Measures identity clarity, claim consistency, and relationship density. Emits FRESH-009/010/011. Public Wikidata + Wikipedia APIs only.
license: MIT
---
## Procedure
1. Infer brand name (JSON-LD → og:site_name → h1).
2. Query Wikidata wbsearchentities.
3. Query SPARQL for relationship density.
4. Emit findings.

## References
- `references/entity_dominance.md`

## Allowed tools
- `python_interpreter`