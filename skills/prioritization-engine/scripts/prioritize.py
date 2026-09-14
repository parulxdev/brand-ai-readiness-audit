#!/usr/bin/env python3
"""
Prioritization Engine v3.1 — mechanism-driven scoring, wave assignment,
and roadmap assembly. Causal-lift is inlined (no separate skill).

Causal-lift model
-----------------
Each finding declares `mechanism` ∈ {config, template, content,
architectural, external}. Mechanism determines base lift + effort.
Page signals (passed by the orchestrator) can *promote* lift for
content/architectural findings when the raw material already exists.

Scoring
-------
    score = normalize( impact × confidence / effort × urgency )
    impact     = severity_weight × vertical_weight(family)
    confidence = evidence-signal(0..1) × lift-certainty(0.5..0.9)
    effort     = inverse of lift (high -> 0.9, medium -> 0.5, low -> 0.25)
    urgency    = 1 + freshness_velocity (only FRESH-012)

Waves
-----
    1: score >= 0.7 OR (lift == high AND severity ∈ {critical, high})
    2: 0.4 <= score < 0.7
    3: score < 0.4
"""

import re

# ── causal-lift ────────────────────────────────────────────────────────────

MECHANISM_LIFT = {
    "config":        "high",
    "template":      "high",
    "content":       "medium",
    "architectural": "low",
    "external":      "low",
}

MECHANISM_EFFORT = {
    "config":        "trivial",
    "template":      "moderate",
    "content":       "moderate",
    "architectural": "significant",
    "external":      "significant",
}

MECHANISM_REASON = {
    "config":        "Single-file / single-header change; applies on next deploy.",
    "template":      "Theme-level edit; applies site-wide on one deploy.",
    "content":       "Authoring or restructuring existing prose; no infra change.",
    "architectural": "Requires SSR/SSG migration or routing restructure.",
    "external":      "Depends on third-party curation; outside single-site control.",
}

# (predicate, promoted_lift, reasoning) — first match wins. Only promotes.
_LIFT_REFINEMENTS = {
    "content": [
        # Only promote content findings when the *specific fix* is a
        # small edit. Having *some* JSON-LD somewhere is not enough —
        # that's true on nearly every modern site and would promote
        # everything to high, collapsing the signal.
        (lambda s: s.get("has_visible_date"),
         "high", "A visible date already exists — mirror it into dateModified."),
    ],
}


def estimate_lift(finding, signals):
    """Mechanism-keyed lift. Writes causal_lift + effort into the finding's
    suggested_action in place. Returns the finding. No finding-ID coupling."""
    mech = finding.get("mechanism", "content")
    if mech not in MECHANISM_LIFT:
        mech = "content"

    lift = MECHANISM_LIFT[mech]
    reason = MECHANISM_REASON[mech]

    for predicate, upgraded, extra in _LIFT_REFINEMENTS.get(mech, ()):
        try:
            if predicate(signals or {}):
                lift = upgraded
                reason = f"{reason} {extra}".strip()
                break
        except Exception:
            continue

    action = finding.setdefault("suggested_action", {})
    action["causal_lift"] = lift
    action["causal_lift_reasoning"] = reason
    action["effort"] = MECHANISM_EFFORT[mech]
    return finding


# ── scoring ────────────────────────────────────────────────────────────────

SEVERITY_IMPACT = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
LIFT_CONFIDENCE = {"high": 0.9, "medium": 0.7, "low": 0.5}
LIFT_EFFORT_MULT = {"high": 0.9, "medium": 0.5, "low": 0.25}
VERTICAL_WEIGHTS = {
    # Family: (DISC, ENG, FRESH) multipliers
    "saas":         {"DISC": 1.1, "ENG": 1.0, "FRESH": 1.0},
    "e-commerce":   {"DISC": 1.0, "ENG": 1.2, "FRESH": 0.9},
    "news":         {"DISC": 1.0, "ENG": 0.9, "FRESH": 1.4},
    "airline":      {"DISC": 1.1, "ENG": 1.0, "FRESH": 1.1},
    "travel":       {"DISC": 1.1, "ENG": 1.0, "FRESH": 1.1},
    "hotel":        {"DISC": 1.0, "ENG": 1.1, "FRESH": 1.0},
    "healthcare":   {"DISC": 1.2, "ENG": 0.9, "FRESH": 1.2},
    "fintech":      {"DISC": 1.2, "ENG": 1.0, "FRESH": 1.1},
    "banking":      {"DISC": 1.2, "ENG": 1.0, "FRESH": 1.1},
    "real-estate":  {"DISC": 1.0, "ENG": 1.1, "FRESH": 1.0},
    "automotive":   {"DISC": 1.0, "ENG": 1.1, "FRESH": 0.9},
    "industrial":   {"DISC": 1.1, "ENG": 0.9, "FRESH": 0.9},
    "education":    {"DISC": 1.1, "ENG": 1.0, "FRESH": 1.0},
    "media":        {"DISC": 1.0, "ENG": 1.0, "FRESH": 1.2},
    "general":      {"DISC": 1.0, "ENG": 1.0, "FRESH": 1.0},
}
_VERTICAL_TO_FAMILY = {
    "e-learning": "education", "edtech": "education",
    "banking": "banking", "wealth-management": "banking",
    "insurance": "fintech", "insurtech": "fintech",
    "proptech": "real-estate", "construction": "real-estate",
    "aerospace": "industrial", "manufacturing": "industrial",
    "defense": "industrial", "logistics": "industrial",
    "supply-chain": "industrial", "energy": "industrial",
    "cleantech": "industrial", "agtech": "industrial",
    "gaming": "media", "e-sports": "media", "sports": "media",
    "entertainment": "media", "publishing": "media",
    "restaurant": "hotel", "hospitality": "hotel",
    "fashion": "e-commerce", "beauty": "e-commerce",
    "consulting": "saas", "legaltech": "saas",
    "hrtech": "saas", "martech": "saas", "govtech": "saas",
    "ai-ml": "saas", "cybersecurity": "saas",
    "deeptech": "industrial", "biotech": "healthcare",
    "medtech": "healthcare", "fitness": "healthcare",
    "telecommunications": "industrial",
    "venture-capital": "fintech", "private-equity": "fintech",
    "non-profit": "general", "architecture": "general",
}

def _weight_family(vertical):
    return _VERTICAL_TO_FAMILY.get(vertical, vertical)

URGENCY_IDS = {"FRESH-012"}


def _family(fid):
    return fid.split("-", 1)[0] if "-" in fid else "DISC"


def _confidence(f):
    """Evidence-signal × lift-certainty. Confidence reflects whether the
    evidence contains concrete, verifiable claims — not how verbose it is."""
    ev = f.get("evidence", "") or ""
    sig = 0.5
    if re.search(r"\bHTTP\s+\d{3}\b|\bstatus\s+\d{3}\b", ev):
        sig += 0.25
    elif any(c.isdigit() for c in ev):
        sig += 0.15
    if re.search(r"\bchars\b|\bwords\b|ratio\s+[\d.]+", ev):
        sig += 0.10
    if re.search(r"\bGET\s+\S+|\bHEAD\s+\S+", ev):
        sig += 0.05
    if not ev.strip():
        sig -= 0.30
    sig = min(1.0, max(0.30, sig))
    lift = f.get("suggested_action", {}).get("causal_lift")
    lift_cert = LIFT_CONFIDENCE.get(lift, 0.6) if lift else 0.6
    return round(sig * lift_cert, 3)


def _effort(f):
    """Return a MULTIPLIER (not a divisor): high-lift = easy fix = boost."""
    lift = f.get("suggested_action", {}).get("causal_lift", "medium")
    return LIFT_EFFORT_MULT.get(lift, 0.5)


def prioritize(findings, signals=None, vertical="general", freshness_velocity=0.0):
    """Estimate lift, score, assign wave. Mutates findings in place."""
    signals = signals or {}
    for f in findings:
        estimate_lift(f, signals)

    family = _weight_family(vertical)
    vw = VERTICAL_WEIGHTS.get(family, VERTICAL_WEIGHTS["general"])
    raw_scores = []
    for f in findings:
        fid = f.get("id", "")
        sev = str(f.get("severity", "medium")).lower()
        impact = SEVERITY_IMPACT.get(sev, 0.5) * vw.get(_family(fid), 1.0)
        conf = _confidence(f)
        effort = _effort(f)
        urgency = 1.0
        if fid in URGENCY_IDS:
            urgency = 1.0 + min(0.5, max(0.0, freshness_velocity))
        raw = (impact * conf * effort) * urgency
        raw_scores.append((f, raw))

    max_raw = max((r for _, r in raw_scores), default=1.0) or 1.0
    for f, raw in raw_scores:
        score = max(0.0, min(1.0, raw / max_raw))
        action = f.setdefault("suggested_action", {})
        action["priority_score"] = round(score, 3)
        lift = action.get("causal_lift")
        sev = str(f.get("severity", "")).lower()
        if score >= 0.7 or (lift == "high" and sev in ("critical", "high")):
            f["wave"] = 1
        elif score >= 0.4:
            f["wave"] = 2
        else:
            f["wave"] = 3
    return findings


# ── roadmap ────────────────────────────────────────────────────────────────

def build_roadmap(findings):
    waves = {1: [], 2: [], 3: []}
    for f in findings:
        w = f.get("wave", 3)
        if w not in (1, 2, 3):
            w = 3
        action = f.get("suggested_action", {}) or {}
        waves[w].append({
            "id":             f.get("id"),
            "title":          f.get("title"),
            "severity":       f.get("severity"),
            "priority_score": action.get("priority_score"),
            "causal_lift":    action.get("causal_lift"),
            "effort":         action.get("effort"),
            "action":         action.get("summary", ""),
        })
    for w in waves.values():
        w.sort(key=lambda e: -(e.get("priority_score") or 0.0))
    return {
        "wave_1_do_now": waves[1],
        "wave_2_plan":   waves[2],
        "wave_3_invest": waves[3],
    }
if __name__ == "__main__":
    import json
    demo = [
        {"id": "DISC-002", "title": "AI Crawler Blocked in robots.txt",
         "severity": "critical", "evidence": "User-agent 'GPTBot' disallowed from root '/'",
         "mechanism": "config",
         "suggested_action": {"summary": "Remove root Disallow", "priority": "critical"}},
        {"id": "ENG-004", "title": "No Quotable Answer Paragraph",
         "severity": "high", "evidence": "Scanned 25 paragraphs; none 40-90 words with entity + quantity",
         "mechanism": "content",
         "suggested_action": {"summary": "Author a 40-90 word paragraph", "priority": "high"}},
        {"id": "FRESH-009", "title": "No Knowledge-Graph Entity",
         "severity": "high", "evidence": "Wikidata search returned 0 items",
         "mechanism": "external",
         "suggested_action": {"summary": "Establish a Wikidata item", "priority": "high"}},
    ]
    prioritize(demo, signals={"has_any_jsonld": True}, vertical="saas")
    print(json.dumps({
        "findings": demo,
        "roadmap": build_roadmap(demo),
    }, indent=2))