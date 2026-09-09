---
name: audit-orchestrator
description: Entrypoint skill for the Brand AI-Readiness Audit Marketplace. Orchestrates sub-skills to audit any domain for off-site AI discoverability, fact corroboration/provenance, and on-site context retention. Emits a unified, strict JSON audit report.
license: MIT
---

# Audit Orchestrator Skill

## Overview
This entrypoint skill receives an audit request for a target URL or domain, invokes the sub-skill detection scripts in isolated subprocesses, applies prioritization matrix logic, and emits the final consolidated JSON audit report adhering to the strict project schema.

## Inputs
- `url` (string, required): Target URL or root domain to audit (e.g., `https://example.com`).

## Procedure

1. **Input Normalization:**
   Ensure the input URL contains a valid HTTP/HTTPS scheme and extract the root domain.

2. **Vertical Intelligence Check:**
   Execute `skills/vertical-intelligence/scripts/detect_vertical.py` to classify the target domain into one of the supported verticals: `e-commerce`, `airline`, `saas`, `hospitality`, `news`, or `general`.

3. **Sub-Skill Audits Execution:**
   Run each sub-skill script in a sandboxed, isolated subprocess with a strict 30-second timeout:
   - **Discovery Audit:** `skills/discovery-audit/scripts/check_discovery.py`
   - **Freshness & Provenance Audit:** `skills/freshness-corroboration/scripts/check_freshness.py`
   - **Engagement & Spatial Audit:** `skills/engagement-audit/scripts/check_engagement.py`

4. **Synthesis & Prioritization:**
   Execute `skills/audit-orchestrator/scripts/synthesize_report.py` to:
   - Aggregate findings from all sub-skills.
   - Deduplicate findings by title and evidence signatures.
   - Assign severity classifications (`critical`, `high`, `medium`, `low`).
   - Append non-defect proactive recommendations based on industry vertical.

5. **Output Delivery:**
   Emit the strict JSON response payload directly to standard output.

## Output
A strict JSON object following the format defined in the root specification, containing `site`, `audited_at`, `vertical`, `summary`, `findings`, and `proactive_recommendations`.