#!/usr/bin/env python3
"""Orchestrator — merges detection + causal-lift + prioritization."""

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILLS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)


def _load_module(name, rel):
    path = os.path.join(SKILLS_DIR, rel)
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        sys.stderr.write(f"Error loading {rel}: {e}\n")
        return None



def _page_signals_from(parser, target_url):
    """Real signals for the causal-lift refinements.

    Robots and sitemap state come from the already-loaded RobotsPolicy —
    no /robots.txt probe here. Sitemap is fetched at most twice (the
    robots-declared URL, then /sitemap.xml as fallback), through
    safe_fetch so it shares the cache with discovery-audit's DISC-007 check.
    """
    from lib.utils import get_robots, safe_fetch
    from lib.ner import has_quantity
    import urllib.parse as _up

    parsed = _up.urlparse(target_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    robots = get_robots()
    has_robots = (
        robots.status_by_origin.get(origin) == 200
        and bool(robots.groups)
    )

    # Sitemap: prefer URLs declared in robots.txt; fall back to /sitemap.xml.
    sitemap_urls = list(robots.sitemaps) or [f"{origin}/sitemap.xml"]
    has_sitemap = False
    for sm in sitemap_urls[:2]:
        r = safe_fetch(sm, timeout=4, skip_robots=True)
        if r.get("status") == 200 and (r.get("body") or "").strip():
            has_sitemap = True
            break

    ec = getattr(parser, "element_counts", None) or {}
    sectioning = ec.get("sectioning", 0) if isinstance(ec, dict) else 0

    visible = getattr(parser, "visible_text", None) or []
    try:
        text = " ".join("".join(visible).split())
    except (TypeError, AttributeError):
        text = ""

    has_visible_date = bool(re.search(
        r"(?:last\s+updated|updated\s+on|last\s+modified|as\s+of|"
        r"published\s+on|revised\s+on)\s*[:\-]?\s*"
        r"(?:[A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
        text, re.IGNORECASE,
    ))

    paragraphs = getattr(parser, "paragraphs", None) or []
    has_quantified = False
    for p in paragraphs:
        if not isinstance(p, dict):
            continue
        if has_quantity(p.get("text", "")):
            has_quantified = True
            break

    return {
        "has_any_jsonld":       bool(getattr(parser, "json_ld_blocks", None) or []),
        "has_section_tags":     sectioning > 0,
        "has_visible_date":     has_visible_date,
        "has_quantified_facts": has_quantified,
        "has_robots":           has_robots,
        "has_sitemap":          has_sitemap,
    }

def run_audit(target_url, budget_seconds=180, include_errors=True):
    from lib.utils import set_deadline, clear_cache, safe_fetch, get_robots, parse_html_content

    clear_cache()
    set_deadline(time.time() + budget_seconds)

    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url
    parsed = urllib.parse.urlparse(target_url)
    site = parsed.netloc or parsed.path or target_url

    findings, errors, diagnostics = [], [], []
    vertical_payload = {"vertical": "general", "confidence": 0.0, "recommendations": []}
    freshness_velocity = 0.0

    origin = f"{parsed.scheme}://{parsed.netloc}"
    get_robots().load(origin)

    if include_errors:
        try:
            from lib.ner import diagnostic_info
            diagnostics.append({"skill": "lib",
                                "info": f"NER backend: {diagnostic_info()}"})
        except Exception as e:
            diagnostics.append({"skill": "lib",
                                "info": f"NER diagnostic failed: {e}"})

    # Load skills
    mod_disc     = _load_module("check_discovery",         "discovery-audit/scripts/check_discovery.py")
    mod_fresh    = _load_module("check_freshness",         "freshness-corroboration/scripts/check_freshness.py")
    mod_eng      = _load_module("check_engagement",        "engagement-audit/scripts/check_engagement.py")
    mod_vert     = _load_module("detect_vertical",         "vertical-intelligence/scripts/detect_vertical.py")
    mod_entity   = _load_module("check_entity_dominance",  "entity-dominance/scripts/check_entity_dominance.py")
    mod_priority = _load_module("prioritize",              "prioritization-engine/scripts/prioritize.py")

    # 1. Vertical
    if mod_vert and hasattr(mod_vert, "check_vertical"):
        try:
            vp = mod_vert.check_vertical(target_url)
            if isinstance(vp, dict):
                vertical_payload = {
                    "vertical": vp.get("vertical", "general") or "general",
                    "confidence": float(vp.get("confidence", 0.0) or 0.0),
                    "recommendations": vp.get("recommendations", []) or [],
                }
        except Exception as e:
            sys.stderr.write(f"vertical-intelligence failed: {e}\n")
            if include_errors:
                errors.append({"skill": "vertical-intelligence", "error": str(e)})

    # 2. Detection
    def _run(mod, fn_name, label):
        if mod is None:
            if include_errors:
                errors.append({"skill": label, "error": "module failed to load"})
            return
        fn = getattr(mod, fn_name, None)
        if fn is None:
            if include_errors:
                errors.append({"skill": label, "error": f"{fn_name} not found"})
            return
        try:
            result = fn(target_url)
            if isinstance(result, list):
                findings.extend(result)
        except Exception as e:
            sys.stderr.write(f"{label} failed: {e}\n")
            if include_errors:
                errors.append({"skill": label, "error": str(e)})

    _run(mod_disc,   "check_discovery",        "discovery-audit")
    _run(mod_fresh,  "check_freshness",        "freshness-corroboration")
    _run(mod_eng,    "check_engagement",       "engagement-audit")
    _run(mod_entity, "check_entity_dominance", "entity-dominance")

    # 3. Schema + dedup
    REQUIRED = {"id", "title", "severity", "evidence", "mechanism", "suggested_action"}
    REQ_ACT = {"summary", "priority"}
    clean, seen = [], set()
    for f in findings:
        if not isinstance(f, dict) or not REQUIRED.issubset(f.keys()):
            if include_errors:
                errors.append({"skill": "orchestrator",
                               "error": "finding dropped (missing fields)"})
            continue
        a = f.get("suggested_action")
        if not isinstance(a, dict) or not REQ_ACT.issubset(a.keys()):
            if include_errors:
                errors.append({"skill": "orchestrator",
                               "error": f"finding {f.get('id','?')} malformed action"})
            continue

        key = (
            f["id"],
            f["title"],
            hashlib.sha1(
                f.get("evidence", "").encode(
                    "utf-8",
                    errors="replace",
                )
            ).hexdigest()[:12],
        )
        if key in seen:
            continue
        seen.add(key)
        clean.append(f)

    # 4. Collect page signals for the prioritization engine's causal-lift step.
    signals = {}
        
    try:
        main_res = safe_fetch(target_url)
        if main_res["status"] == 200 and main_res.get("body"):
            parser = parse_html_content(main_res["body"])
            signals = _page_signals_from(parser, target_url)
    except Exception as e:
        if include_errors:
            errors.append({"skill": "orchestrator",
                           "error": f"page-signals collection failed: {e}"})

    if include_errors and not any(signals.values()):
        diagnostics.append({"skill": "orchestrator",
                            "info": "page signals are all-False; lift refinements inactive"})

    # 5. Freshness velocity from FRESH-012 evidence
    for f in clean:
        if f.get("id") == "FRESH-012":
            m = re.search(r"decay_velocity=([\d.]+)", f.get("evidence", ""))
            if m:
                try:
                    freshness_velocity = float(m.group(1))
                except ValueError:
                    pass
            break

    # 6. Prioritization
    roadmap = {"wave_1_do_now": [], "wave_2_plan": [], "wave_3_invest": []}
    if mod_priority and hasattr(mod_priority, "prioritize"):
        try:
            mod_priority.prioritize(
                clean,
                signals=signals,
                vertical=vertical_payload["vertical"],
                freshness_velocity=freshness_velocity,
            )
            roadmap = mod_priority.build_roadmap(clean)
        except Exception as e:
            sys.stderr.write(f"prioritization failed: {e}\n")
            if include_errors:
                errors.append({"skill": "prioritization-engine", "error": str(e)})

    # 7. Summary
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in clean:
        sev = str(f.get("severity", "low")).lower()
        if sev in counts:
            counts[sev] += 1

    report = {
        "site": site,
        "audited_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vertical": vertical_payload["vertical"],
        "vertical_confidence": vertical_payload["confidence"],
        "summary": {
            "total_findings": len(clean),
            "critical": counts["critical"],
            "high":     counts["high"],
            "medium":   counts["medium"],
            "low":      counts["low"],
        },
        "findings": clean,
        "roadmap": roadmap,
        "proactive_recommendations": vertical_payload["recommendations"],
    }
    if include_errors:
        report["errors"] = errors
        if diagnostics:
            report["diagnostics"] = diagnostics
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Brand AI-Readiness Orchestrator")
    ap.add_argument("url")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--budget", type=int, default=180)
    ap.add_argument("--no-errors", action="store_true",
                    help="Suppress the errors AND diagnostics arrays.")
    args = ap.parse_args()
    result = run_audit(
        args.url,
        budget_seconds=args.budget,
        include_errors=not args.no_errors,
    )
    s = json.dumps(result, indent=2)
    if args.json_out:
        open(args.json_out, "w", encoding="utf-8").write(s)
    else:
        print(s)


