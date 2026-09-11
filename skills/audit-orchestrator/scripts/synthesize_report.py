#!/usr/bin/env python3
"""
Orchestration and Synthesis Script for Brand AI-Readiness Audit.
Executes sub-skill audit scripts safely via subprocess, enforces 30s timeouts per skill,
deduplicates findings, assigns severity counts, appends vertical-specific proactive recommendations,
and emits the strict JSON output schema.
"""

import os
import sys
import json
import subprocess
import urllib.parse
from datetime import datetime, timezone

# Root directory helper
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))

# Severity order for prioritization (lower number = higher priority)
SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3
}


def run_subskill_script(script_path, target_url, timeout=30):
    """
    Executes a sub-skill Python script in an isolated subprocess with strict timeout protection.
    Returns parsed JSON output or degraded fallback on failure.
    """
    full_path = os.path.join(BASE_DIR, script_path)
    if not os.path.exists(full_path):
        sys.stderr.write(f"Warning: Script not found at {full_path}\n")
        return None

    try:
        proc = subprocess.run(
            [sys.executable, full_path, target_url],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout)
        else:
            sys.stderr.write(f"Subprocess Warning ({script_path}): {proc.stderr}\n")
            return None
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"Timeout Error: Sub-skill {script_path} exceeded {timeout}s runtime limit.\n")
        return None
    except Exception as e:
        sys.stderr.write(f"Execution Error ({script_path}): {str(e)}\n")
        return None


def get_proactive_recommendations(vertical):
    """Generates vertical-specific, non-defect proactive recommendations."""
    generic_recs = [
        "Deploy a root /llms.txt and /llms-full.txt markdown index to provide RAG systems with clean brand context.",
        "Include high-authority sameAs links (e.g., Wikidata, Wikipedia, Crunchbase) inside Schema.org/Organization JSON-LD markup."
    ]

    vertical_recs = {
        "e-commerce": [
            "Implement Schema.org/OfferCatalog and Schema.org/ItemList to structure product category hierarchies for AI product discovery.",
            "Include explicit Schema.org/PropertyValue entries for technical specifications (e.g., heel_drop, dimensions, weight) directly in static HTML."
        ],
        "airline": [
            "Embed Schema.org/Flight and Schema.org/Airline structured metadata to enable real-time itinerary and fare parsing by AI assistants.",
            "Implement dynamic deep URL anchors for direct flight route queries (e.g., /flights/del-bom#schedule)."
        ],
        "saas": [
            "Deploy machine-readable API documentation tags and Schema.org/SoftwareApplication metadata.",
            "Configure edge middleware to detect AI referral traffic and preserve query context upon entry to pricing/docs pages."
        ],
        "hospitality": [
            "Structure room types, amenities, and policies using Schema.org/Hotel and Schema.org/Accommodation JSON-LD.",
            "Ensure check-in policies and room specifications exist in plain text above the fold rather than inside client-side JS accordions."
        ],
        "news": [
            "Implement Schema.org/NewsArticle with explicit datePublished and dateModified ISO timestamps.",
            "Distribute semantically tagged HTML press kits and integrate IndexNow protocol for sub-minute indexing of breaking stories."
        ]
    }

    return generic_recs + vertical_recs.get(vertical, [])


def synthesize_audit(target_url):
    # 1. Normalize target URL
    if not target_url.startswith('http://') and not target_url.startswith('https://'):
        target_url = 'https://' + target_url

    parsed = urllib.parse.urlparse(target_url)
    site_domain = parsed.netloc or parsed.path

    # 2. Detect Vertical
    vertical_data = run_subskill_script("skills/vertical-intelligence/scripts/detect_vertical.py", target_url)
    detected_vertical = vertical_data.get("vertical", "general") if vertical_data else "general"

    # 3. Execute Sub-skill Audits
    discovery_findings = run_subskill_script("skills/discovery-audit/scripts/check_discovery.py", target_url) or []
    freshness_findings = run_subskill_script("skills/freshness-corroboration/scripts/check_freshness.py", target_url) or []
    engagement_findings = run_subskill_script("skills/engagement-audit/scripts/check_engagement.py", target_url) or []

    # 4. Aggregate and Deduplicate Findings
    all_findings = discovery_findings + freshness_findings + engagement_findings
    seen_titles = set()
    deduped_findings = []

    for finding in all_findings:
        title = finding.get("title")
        if title not in seen_titles:
            seen_titles.add(title)
            deduped_findings.append(finding)

    # 4b. Prioritize by severity (Critical -> High -> Medium -> Low)
    deduped_findings = sorted(
        deduped_findings,
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", "medium").lower(), 3)
    )

    # 5. Compute Severity Summary Counts
    severity_counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0
    }

    for finding in deduped_findings:
        sev = finding.get("severity", "medium").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    summary = {
        "total_findings": len(deduped_findings),
        "critical": severity_counts["critical"],
        "high": severity_counts["high"],
        "medium": severity_counts["medium"]
    }

    # 6. Proactive Recommendations
    proactive = get_proactive_recommendations(detected_vertical)

    # 7. Build Output Object
    audit_report = {
        "site": site_domain,
        "audited_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vertical": detected_vertical,
        "summary": summary,
        "findings": deduped_findings,
        "proactive_recommendations": proactive
    }

    return audit_report


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    report = synthesize_audit(target)
    print(json.dumps(report, indent=2))