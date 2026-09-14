#!/usr/bin/env python3
"""Node renderer bridge. Deadline-aware, rejects empty shells."""

import json
import os
import re
import shutil
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SKILLS_DIR = os.path.abspath(os.path.join(SKILL_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(SKILLS_DIR, ".."))
SHARED_DIR = os.path.join(ROOT_DIR, "lib")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from utils import get_deadline

RENDER_JS = os.path.join(SCRIPT_DIR, "render.js")
NODE_TIMEOUT = 20
_MIN_VISIBLE = 20


def is_node_available():
    return shutil.which("node") is not None


def render_dom(target_url, timeout=NODE_TIMEOUT):
    deadline = get_deadline()
    if deadline is not None:
        remaining = deadline - time.time()
        if remaining <= 3:
            return {"ok": False, "html": "", "error": "deadline too close for Node render"}
        timeout = min(timeout, max(3, remaining - 3))

    if not is_node_available():
        return {"ok": False, "html": "", "error": "node not available"}
    if not os.path.exists(RENDER_JS):
        return {"ok": False, "html": "", "error": f"renderer missing at {RENDER_JS}"}

    try:
        proc = subprocess.run(
            ["node", RENDER_JS, target_url],
            capture_output=True, text=True, timeout=timeout, cwd=SCRIPT_DIR,
        encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            return {"ok": False, "html": "",
                    "error": (proc.stderr or "render failed").strip()[:400]}
        payload = json.loads(proc.stdout)
        if not isinstance(payload, dict):
            return {"ok": False, "html": "", "error": "malformed renderer output"}
        html = payload.get("html", "") or ""
        err = payload.get("error")
        # Reject empty shells: require at least _MIN_VISIBLE non-tag chars.
        visible = re.sub(r"<[^>]+>|\s+", "", html)
        if len(visible) < _MIN_VISIBLE:
            return {"ok": False, "html": "", "error": err or "renderer returned empty shell"}
        return {"ok": True, "html": html, "error": None}
    except subprocess.TimeoutExpired:
        return {"ok": False, "html": "", "error": "renderer timeout"}
    except Exception as e:
        return {"ok": False, "html": "", "error": str(e)}


def text_length_ratio(raw_text, rendered_text):
    raw_len = len(raw_text)
    rendered_len = len(rendered_text)
    if raw_len == 0:
        return rendered_len, raw_len, float("inf") if rendered_len else 0.0
    return rendered_len, raw_len, rendered_len / raw_len

if __name__ == "__main__":
    import json
    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    result = render_dom(target)
    # Don't dump the entire HTML — summarize.
    out = {
        "ok": result.get("ok"),
        "error": result.get("error"),
        "html_len": len(result.get("html") or ""),
    }
    print(json.dumps(out, indent=2))