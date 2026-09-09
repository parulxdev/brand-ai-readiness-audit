# Brand AI-Readiness Audit Scoring & Evaluation Rubric

## Severity Classification Matrix

| Severity Level | Definition & Business Impact | Escalation Criteria |
| :--- | :--- | :--- |
| **Critical** | Completely blocks AI models from discovering, crawling, or parsing page contents. Causes total invisibility or catastrophic context loss upon arrival. | `robots.txt` disallows key AI crawlers; Client-Side Rendering (CSR) produces empty static HTML shell. |
| **High** | Significantly impairs fact extraction accuracy or context retention. Leads to hallucinated attributes, stale pricing/logos, or immediate referral traffic bounces. | Missing Schema.org Organization/Brand metadata; missing `dateModified` timestamps; stateless AI referrer routing. |
| **Medium** | Degrades parsing efficiency, machine legibility, or URL citation deep-linking. | Missing `/llms.txt` endpoint; missing HTTP cache invalidation headers (`Last-Modified`/`ETag`); missing heading `id` anchors. |
| **Low** | Minor optimization opportunities for brand authority enhancement. | Unoptimized Schema.org/PropertyValue formatting; missing secondary `sameAs` social profile links. |

## Evaluation Guardrails & Rules
- **Recommend-Only:** Audits and reports findings strictly in read-only mode.
- **Deduplication:** Findings are deduplicated across sub-skills by title and root evidence signature.
- **Resource Limits:** Total execution runtime must strictly remain under 5 minutes; memory buffers capped at 1MB per HTTP call.