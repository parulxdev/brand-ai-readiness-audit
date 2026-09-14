#!/usr/bin/env python3
"""Wikipedia corroboration. Deadline-aware. Tightened matching."""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from utils import get_deadline

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = ( "AI-Readiness-Auditor/3.0 " "(+https://github.com/example/brand-ai-readiness-audit; " "contact: parulxdev@gmail.com)" )
TIMEOUT = 6

_BRAND_NOISE = re.compile(
    r"\b(inc\.?|llc|ltd\.?|corp\.?|corporation|company|co\.?|gmbh|plc|group|"
    r"limited|holdings|technologies|technology|solutions|services|systems)\b",
    re.IGNORECASE,
)


def _normalize(s):
    s = (s or "").strip().lower()
    # NFKD-normalize so "L'Oréal" → "l'oreal" and "Nestlé" → "nestle".
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _BRAND_NOISE.sub("", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_close_match(brand_norm, title_norm):
    if not brand_norm or not title_norm:
        return False
    if brand_norm == title_norm:
        return True
    bt = brand_norm.split()
    tt = title_norm.split()
    if len(bt) <= len(tt) and tt[:len(bt)] == bt:
        return True
    return False


def _wiki_search(term, limit=5):
    if not term or len(term.strip()) < 2:
        return {"error": "term too short", "results": []}

    deadline = get_deadline()
    timeout = TIMEOUT
    if deadline is not None:
        remaining = deadline - time.time()
        if remaining <= 2:
            return {"error": "deadline too close", "results": []}
        timeout = min(TIMEOUT, remaining - 1)

    params = {
        "action": "query", "list": "search", "srsearch": term.strip(),
        "format": "json", "srlimit": str(limit), "srnamespace": "0",
    }
    url = f"{WIKI_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        return {"error": str(e), "results": []}

    hits = []
    for hit in (data.get("query", {}).get("search") or []):
        hits.append({
            "title": hit.get("title", ""),
            "pageid": hit.get("pageid"),
            "snippet": hit.get("snippet", ""),
        })
    return {"error": None, "results": hits}


def corroborate_brand(brand_name):
    if not brand_name:
        return {"queried": "", "wiki_results": [], "found": False,
                "best_match": None, "error": "no brand name supplied"}

    outcome = _wiki_search(brand_name)
    if isinstance(outcome, dict) and outcome.get("error"):
        return {"queried": brand_name, "wiki_results": [], "found": False,
                "best_match": None, "error": outcome["error"]}

    results = outcome.get("results", []) if isinstance(outcome, dict) else outcome
    brand_norm = _normalize(brand_name)
    for r in results:
        title_norm = _normalize(r.get("title") or "")
        if _is_close_match(brand_norm, title_norm):
            return {"queried": brand_name, "wiki_results": results,
                    "found": True, "best_match": r.get("title"), "error": None}
    return {"queried": brand_name, "wiki_results": results,
            "found": False, "best_match": None, "error": None}
if __name__ == "__main__":
    import json
    brand = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(json.dumps(corroborate_brand(brand), indent=2))