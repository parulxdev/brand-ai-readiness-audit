#!/usr/bin/env python3
"""
Shared standard-library utilities.

v3.1 changes:
  * Capture STACK (not singular) — paragraphs/headings containing links survive.
  * `<li>` and `<dd>` captured as paragraph-equivalents.
  * above_fold_text excludes nav/footer chrome.
  * height:0 alone no longer hides content (requires overflow:hidden).
  * SSL verification is never bypassed.
  * Robots-aware redirect handler installed on every fetch.
  * One canonical path matcher (`path_matches`).
  * Frozen cache keys via SHA-256.
  * Tri-state robots_presence.
"""

from html.parser import HTMLParser
import contextvars
import hashlib
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FETCH_CACHE = {}
_DEADLINE_VAR = contextvars.ContextVar("audit_deadline", default=None)
_SKIP_ROBOTS_VAR = contextvars.ContextVar("skip_robots", default=False)

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
RESERVED_ACTION_KEYS = {"summary", "priority", "impact", "code_snippet"}

AUDITOR_UA = "AI-Readiness-Auditor/1.0"
AUDITOR_UA_TOKEN = "ai-readiness-auditor"

SKIP_TEXT_TAGS = {"script", "style", "template", "noscript",
                  "svg", "iframe", "textarea", "select", "option"}
SECTION_TAGS = {"section", "article", "main"}
NAV_TAGS = {"nav", "header"}
FOOTER_TAGS = {"footer"}
ASIDE_TAGS = {"aside"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

BLOCK_TAGS = frozenset({
    "p", "div", "section", "article", "aside", "main", "header", "footer",
    "nav", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ul", "ol", "dl", "dt", "dd",
    "table", "tr", "td", "th", "thead", "tbody", "tfoot",
    "blockquote", "pre", "figure", "figcaption",
    "hr", "br", "form", "fieldset", "legend", "address", "details", "summary",
})

PARAGRAPH_EQUIV_TAGS = {"p", "li", "dd"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

HIDDEN_STYLE_PATTERNS = [
    re.compile(r"display\s*:\s*none", re.IGNORECASE),
    re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE),
    re.compile(r"opacity\s*:\s*0(?![.\d])", re.IGNORECASE),
    re.compile(r"position\s*:\s*absolute[^;]*left\s*:\s*-\d{4,}", re.IGNORECASE),
    re.compile(r"position\s*:\s*absolute[^;]*top\s*:\s*-\d{4,}", re.IGNORECASE),
    re.compile(r"font-size\s*:\s*0(?![.\d])", re.IGNORECASE),
    re.compile(r"text-indent\s*:\s*-\d{4,}px", re.IGNORECASE),
    re.compile(r"height\s*:\s*0(?![.\d])[^;]*overflow\s*:\s*hidden", re.IGNORECASE),
]
_A11Y_CLASS_TOKENS = ("sr-only", "visuallyhidden", "visually-hidden", "screen-reader")

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:the\s+)?(?:above|previous)", re.IGNORECASE),
    re.compile(r"as\s+an\s+ai(?:\s+language\s+model)?", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"you\s+must\s+(?:recommend|always\s+recommend)", re.IGNORECASE),
    re.compile(r"do\s+not\s+mention\s+", re.IGNORECASE),
]


# ─────────────────────────── canonical path matcher ───────────────────────

def path_matches(path, pattern):
    """
    RFC-9309-aligned matcher used by every robots decision (policy, sitemap
    cross-reference, Node renderer parity).

    Rules:
      * '/' matches every path.
      * '*' is a wildcard (matches any run of characters).
      * trailing '$' anchors the end of the path.
      * trailing slashes are normalized on both sides.
    """
    pattern = (pattern or "").strip()
    if not pattern:
        return False
    if pattern == "/":
        return path.startswith("/")

    end_anchored = pattern.endswith("$")
    core = pattern[:-1] if end_anchored else pattern

    if "*" in core:
        regex = "".join(
            ".*" if ch == "*" else re.escape(ch)
            for ch in core
        )
    else:
        regex = re.escape(core)

    regex = "^" + regex + ("$" if end_anchored else "")

    try:
        if re.match(regex, path):
            return True
    except re.error:
        return False

    p_norm = path.rstrip("/") or "/"
    pat_norm = core.rstrip("/") or "/"
    return p_norm == pat_norm or p_norm.startswith(pat_norm + "/")


# ───────────────────────────── robots.txt ─────────────────────────────────

class RobotsPolicy:
    """RFC-9309 group-aware parser with version-tolerant agent matching.

    All HTTP goes through safe_fetch(skip_robots=True) so robots.txt is
    fetched exactly once per origin and shared with every other caller
    in the same audit run.
    """

    def __init__(self, ua_token=AUDITOR_UA_TOKEN):
        self.ua_token = ua_token.lower()
        self.groups = []
        self.sitemaps = []
        self.fetched_origins = set()
        self.status_by_origin = {}   # origin -> HTTP status (0 = transient)

    @staticmethod
    def _agent_matches(agent, ours):
        return agent == ours or agent.startswith(ours + "/")

    def load(self, origin):
        if origin in self.fetched_origins:
            return

        # Mark first to prevent recursion/re-entry.
        self.fetched_origins.add(origin)

        url = origin.rstrip("/") + "/robots.txt"
        res = safe_fetch(
            url,
            timeout=5,
            max_bytes=256 * 1024,
            skip_robots=True,
        )

        self.status_by_origin[origin] = res.get("status", 0)

        body = res.get("body") or ""
        if res.get("status") != 200 or not body:
            return

        current = None

        for raw in body.splitlines():
            line = raw.split("#", 1)[0].rstrip()

            if not line.strip():
                current = None
                continue

            if ":" not in line:
                continue

            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()

            if key == "user-agent":
                if current is None or current["rules"]:
                    current = {"agents": [], "rules": []}
                    self.groups.append(current)

                if val:
                    current["agents"].append(val.lower())

            elif key in ("allow", "disallow"):
                if current is None:
                    current = {"agents": ["*"], "rules": []}
                    self.groups.append(current)

                current["rules"].append((key, val))

            elif key == "sitemap" and val:
                self.sitemaps.append(val)

    def _matching_groups(self):
        specific, wildcard = [], []

        for g in self.groups:
            spec = wild = False

            for a in g["agents"]:
                if a == "*":
                    wild = True
                elif self._agent_matches(a, self.ua_token):
                    spec = True

            if spec:
                specific.append(g)
            elif wild:
                wildcard.append(g)

        return specific if specific else wildcard

    def is_allowed(self, url):
        parsed = urllib.parse.urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self.fetched_origins:
            return True

        path = parsed.path or "/"

        if parsed.query:
            path += "?" + parsed.query

        best_rule, best_len = None, -1

        for g in self._matching_groups():
            for kind, pattern in g["rules"]:
                if not pattern:
                    continue

                if not path_matches(path, pattern):
                    continue

                plen = len(pattern)

                if plen > best_len or (
                    plen == best_len and kind == "allow"
                ):
                    best_len, best_rule = plen, kind

        return best_rule is None or best_rule == "allow"


_ROBOTS = RobotsPolicy()


def get_robots():
    return _ROBOTS


def set_deadline(ts):
    _DEADLINE_VAR.set(ts)


def get_deadline():
    return _DEADLINE_VAR.get()


def clear_cache():
    FETCH_CACHE.clear()
    _PARSE_CACHE.clear()
    _DEADLINE_VAR.set(None)

    global _ROBOTS
    _ROBOTS = RobotsPolicy()


# ───────────────────── robots-aware redirect handler ──────────────────────

class _RobotsAwareRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-checks robots.txt on every redirect hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _SKIP_ROBOTS_VAR.get():
            return super().redirect_request(
                req, fp, code, msg, headers, newurl
            )

        parsed = urllib.parse.urlparse(newurl)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        _ROBOTS.load(origin)

        if not _ROBOTS.is_allowed(newurl):
            raise urllib.error.HTTPError(
                newurl,
                code,
                "redirect blocked by robots.txt",
                headers,
                fp,
            )

        return super().redirect_request(
            req, fp, code, msg, headers, newurl
        )


def _build_opener():
    return urllib.request.build_opener(_RobotsAwareRedirectHandler())


# ───────────────────────────── HTML parser ────────────────────────────────

class StandardHTMLParser(HTMLParser):
    """
    Structured HTML parser with a capture STACK.

    A `<p>` containing `<a>` no longer loses the paragraph: the anchor is
    captured on top of the paragraph's capture frame, then the paragraph
    frame resumes. Same for headings containing links, anchors containing
    headings, and nested strongs.
    """

    def __init__(self, above_fold_char_limit=2000):
        super().__init__()

        self.json_ld_blocks = []
        self.json_ld_malformed = 0

        self.headings = []
        self.paragraphs = []
        self.anchors = []
        self.forms = []

        self.meta_tags = {}
        self.scripts = []

        self.visible_text = []
        self.above_fold_text = []

        self.section_openings = []
        self.emphasized_texts = []
        self.hidden_text_candidates = []
        self.potential_injection_hits = []

        self.element_counts = {
            "total": 0,
            "sectioning": 0,
            "div": 0,
            "p": 0,
            "heading": 0,
        }

        self._af_limit = above_fold_char_limit
        self._af_len = 0

        self._stack = []
        self._capture_stack = []

        self._last_section_heading = None
        self._last_section_heading_tag = None
        self._awaiting_section_opener = False
        self._section_head_words = []

        self._emphasis_depth = 0
        self._emphasis_buffer = []

        self._script_depth = 0

    def _push_capture(self, tag, kind, attrs=None, href=""):
        self._capture_stack.append({
            "tag": tag,
            "kind": kind,
            "buffer": [],
            "attrs": attrs or {},
            "href": href or "",
        })

    def _top_capture(self):
        return self._capture_stack[-1] if self._capture_stack else None

    def _pop_capture(self, tag):
        for i in range(len(self._capture_stack) - 1, -1, -1):
            if self._capture_stack[i]["tag"] == tag:
                return self._capture_stack.pop(i)
        return None

    def _push(self, tag, attrs):
        style = attrs.get("style", "")
        aria_hidden = attrs.get("aria-hidden", "").lower() == "true"
        classes = (attrs.get("class", "") or "").lower()
        cls_tokens = set(classes.split())

        a11y_class = any(
            tok in cls_tokens
            for tok in _A11Y_CLASS_TOKENS
        )

        self._stack.append({
            "tag": tag,
            "hidden": self._is_hidden_style(style),
            "a11y_hidden": aria_hidden or a11y_class,
            "nav": tag in NAV_TAGS,
            "footer": tag in FOOTER_TAGS,
            "aside": tag in ASIDE_TAGS,
        })

    def _pop_until(self, tag):
        while self._stack:
            top = self._stack.pop()

            if top["tag"] == tag:
                return

    def _context(self):
        nav = footer = aside = hidden = a11y_hidden = in_skip = False

        for f in self._stack:
            if f["nav"]:
                nav = True
            if f["footer"]:
                footer = True
            if f["aside"]:
                aside = True
            if f["hidden"]:
                hidden = True
            if f["a11y_hidden"]:
                a11y_hidden = True
            if f["tag"] in SKIP_TEXT_TAGS:
                in_skip = True

        return {
            "in_nav": nav,
            "in_footer": footer,
            "in_aside": aside,
            "hidden": hidden,
            "a11y_hidden": a11y_hidden,
            "in_skip": in_skip,
        }

    def _is_hidden_style(self, style_value):
        if not style_value:
            return False

        return any(
            p.search(style_value)
            for p in HIDDEN_STYLE_PATTERNS
        )

    def _emit_separator(self):
        for buf, is_af in (
            (self.visible_text, False),
            (self.above_fold_text, True),
        ):
            if not buf or not buf[-1] or buf[-1].endswith(
                (" ", "\t", "\n")
            ):
                continue

            if is_af and self._af_len >= self._af_limit:
                continue

            buf.append(" ")

            if is_af:
                self._af_len += 1

    def _append_visible(self, data, ctx):
        self.visible_text.append(data)

        if not (ctx["in_nav"] or ctx["in_footer"]):
            if self._af_len < self._af_limit:
                remaining = self._af_limit - self._af_len
                chunk = (
                    data
                    if len(data) <= remaining
                    else data[:remaining]
                )
                self.above_fold_text.append(chunk)
                self._af_len += len(chunk)

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        attr = {k.lower(): v for k, v in attrs if k}

        if t in BLOCK_TAGS:
            self._emit_separator()

        self.element_counts["total"] += 1

        if t in SECTION_TAGS:
            self.element_counts["sectioning"] += 1
        elif t == "div":
            self.element_counts["div"] += 1
        elif t in PARAGRAPH_EQUIV_TAGS:
            self.element_counts["p"] += 1
        elif t in HEADING_TAGS:
            self.element_counts["heading"] += 1

        if t in VOID_TAGS:
            if t == "meta":
                key = attr.get("property") or attr.get("name")

                if key and "content" in attr:
                    self.meta_tags[key.lower()] = attr["content"]

            elif t == "input" and self.forms:
                self.forms[-1]["inputs"].append({
                    "type": attr.get("type", "text"),
                    "name": attr.get("name", ""),
                    "placeholder": attr.get("placeholder", ""),
                })

            return

        self._push(t, attr)

        if t in ("b", "strong", "q"):
            if self._emphasis_depth == 0:
                self._emphasis_buffer = []

            self._emphasis_depth += 1

        if t in HEADING_TAGS:
            self._push_capture(
                t,
                "heading",
                attrs={"tag": t, "attrs": attr},
            )

            if t in ("h2", "h3"):
                if (
                    self._awaiting_section_opener
                    and self._section_head_words
                ):
                    self._record_section_opening()

                self._last_section_heading = None
                self._last_section_heading_tag = None
                self._awaiting_section_opener = False
                self._section_head_words = []

        elif t in PARAGRAPH_EQUIV_TAGS:
            self._push_capture(t, "paragraph")

        elif t == "a":
            self._push_capture(
                t,
                "anchor",
                href=attr.get("href", ""),
            )

        elif t == "form":
            self.forms.append({
                "action": attr.get("action", ""),
                "inputs": [],
                **{
                    k: v
                    for k, v in self._context().items()
                    if k in ("in_nav", "in_footer")
                },
            })

        elif t == "script":
            self._script_depth += 1
            self.scripts.append(attr)

            stype = (
                attr.get("type", "")
                .lower()
                .split(";")[0]
                .strip()
            )

            if stype == "application/ld+json":
                self._push_capture(t, "json_ld")

    def handle_data(self, data):
        ctx = self._context()

        in_skip = ctx["in_skip"]
        visually_hidden = ctx["hidden"]
        a11y_hidden = ctx["a11y_hidden"]

        in_json = any(
            f["kind"] == "json_ld"
            for f in self._capture_stack
        )

        if not in_skip and not in_json:
            if not visually_hidden:
                self._append_visible(data, ctx)

                if (
                    self._awaiting_section_opener
                    and self._last_section_heading is not None
                    and data.strip()
                ):
                    self._section_head_words.extend(data.split())
                    self._record_section_opening()

            if (
                visually_hidden
                and not a11y_hidden
                and len(data.strip()) >= 50
            ):
                stripped = data.strip()
                self.hidden_text_candidates.append({
                    "text": stripped[:200]
                })

                for pat in INJECTION_PATTERNS:
                    if pat.search(stripped):
                        self.potential_injection_hits.append(
                            stripped[:200]
                        )
                        break

        if (
            self._emphasis_depth > 0
            and not in_skip
            and not visually_hidden
        ):
            self._emphasis_buffer.append(data)

        for frame in self._capture_stack:
            if in_skip and frame["tag"] not in SKIP_TEXT_TAGS:
                continue

            frame["buffer"].append(data)

    def handle_endtag(self, tag):
        t = tag.lower()

        if (
            t in ("b", "strong", "q")
            and self._emphasis_depth > 0
        ):
            self._emphasis_depth -= 1

            if self._emphasis_depth == 0:
                text = " ".join(
                    "".join(self._emphasis_buffer).split()
                )

                if text:
                    self.emphasized_texts.append(text)

                self._emphasis_buffer = []

        if t in VOID_TAGS:
            return

        if t == "script":
            self._script_depth = max(
                0,
                self._script_depth - 1,
            )

            frame = self._pop_capture("script")

            if frame and frame["kind"] == "json_ld":
                raw = "".join(frame["buffer"]).strip()

                if raw:
                    try:
                        parsed = json.loads(raw)

                        if isinstance(parsed, list):
                            self.json_ld_blocks.extend(parsed)
                        elif isinstance(parsed, dict):
                            self.json_ld_blocks.append(parsed)

                    except Exception:
                        self.json_ld_malformed += 1

            self._pop_until(t)

        elif t in HEADING_TAGS:
            frame = self._pop_capture(t)

            if frame and frame["kind"] == "heading":
                text = " ".join(
                    "".join(frame["buffer"]).split()
                )

                self.headings.append({
                    "tag": t,
                    "attrs": frame["attrs"].get("attrs", {}),
                    "text": text,
                    "section_heading": self._last_section_heading,
                })

                if t in ("h2", "h3"):
                    self._last_section_heading = text
                    self._last_section_heading_tag = t
                    self._awaiting_section_opener = True
                    self._section_head_words = []

            self._pop_until(t)

        elif t in PARAGRAPH_EQUIV_TAGS:
            frame = self._pop_capture(t)

            if frame and frame["kind"] == "paragraph":
                text = " ".join(
                    "".join(frame["buffer"]).split()
                )

                if text:
                    wc = len(text.split())
                    c = self._context()

                    self.paragraphs.append({
                        "text": text,
                        "word_count": wc,
                        "in_nav": c["in_nav"],
                        "in_footer": c["in_footer"],
                        "in_aside": c["in_aside"],
                        "section_heading": self._last_section_heading,
                        "tag": t,
                    })

                    if (
                        self._awaiting_section_opener
                        and self._last_section_heading is not None
                        and not self._section_head_words
                    ):
                        self._section_head_words.extend(text.split())
                        self._record_section_opening()

            self._pop_until(t)

        elif t == "a":
            frame = self._pop_capture("a")

            if frame and frame["kind"] == "anchor":
                text = " ".join(
                    "".join(frame["buffer"]).split()
                )
                c = self._context()

                self.anchors.append({
                    "href": frame["href"],
                    "text": text,
                    "in_nav": c["in_nav"],
                    "in_footer": c["in_footer"],
                })
                    #  _pop_capture pops from _capture_stack (data buffers);
        # _pop_until pops from _stack (context flags). They are DIFFERENT
        # stacks — both pops are required and must not be merged.

            self._pop_until(t)

        else:
                    # NOTE: _pop_capture pops from _capture_stack (data buffers);
        # _pop_until pops from _stack (context flags). They are DIFFERENT
        # stacks — both pops are required and must not be merged.
            self._pop_until(t)

        if t in BLOCK_TAGS:
            self._emit_separator()

    def _record_section_opening(self):
        text = " ".join(self._section_head_words[:30])

        if text and self._last_section_heading is not None:
            self.section_openings.append({
                "heading": self._last_section_heading,
                "heading_tag": (
                    self._last_section_heading_tag or "h2"
                ),
                "first_para": text,
            })

        self._awaiting_section_opener = False
        self._section_head_words = []


_WHITESPACE_RE = re.compile(r"\s+")
_PARSE_CACHE = {}
_PARSE_CACHE_MAX = 8


def parse_html_content(html_str):
    """
    Cache the parsed model. The returned parser is READ-ONLY: callers must
    not mutate its lists. Cache key is a SHA-256 of the full string, so no
    hash-collision risk.
    """
    if not html_str:
        return StandardHTMLParser()

    key = hashlib.sha256(
        html_str.encode("utf-8", errors="replace")
    ).hexdigest()

    cached = _PARSE_CACHE.get(key)

    if cached is not None:
        return cached

    parser = StandardHTMLParser()

    try:
        parser.feed(html_str)
    except Exception as e:
        sys.stderr.write(
            f"Warning: HTML parse error: {e}\n"
        )

    if len(_PARSE_CACHE) >= _PARSE_CACHE_MAX:
        _PARSE_CACHE.clear()

    _PARSE_CACHE[key] = parser
    return parser


def extract_visible_text(html_str):
    if not html_str:
        return ""

    parser = parse_html_content(html_str)
    raw = "".join(parser.visible_text)

    text = _WHITESPACE_RE.sub(" ", raw).strip()

    if text:
        return text

    fallback = re.sub(r"<[^>]+>", " ", html_str)
    return _WHITESPACE_RE.sub(" ", fallback).strip()


# ───────────────────────────── HTTP fetch ────────────────────────────────

_OPENER = _build_opener()


def safe_fetch(
    url,
    timeout=6,
    max_bytes=1024 * 1024,
    use_cache=True,
    deadline=None,
    skip_robots=False,
):
    scheme = urllib.parse.urlparse(url).scheme.lower()

    if scheme not in ("http", "https"):
        return {
            "status": 0,
            "headers": {},
            "body": "",
            "error": f"unsupported scheme '{scheme}'",
            "truncated": False,
        }

    parsed = urllib.parse.urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    if not skip_robots:
        _ROBOTS.load(origin)

        if not _ROBOTS.is_allowed(url):
            return {
                "status": 0,
                "headers": {},
                "body": "",
                "error": (
                    "blocked by robots.txt for "
                    "AI-Readiness-Auditor"
                ),
                "truncated": False,
            }

    # Timeout deliberately excluded from the cache key:
    # callers requesting the same URL/max_bytes share the same bytes.
    cache_key = (url, max_bytes)

    if use_cache and cache_key in FETCH_CACHE:
        return FETCH_CACHE[cache_key]

    eff = (
        deadline
        if deadline is not None
        else get_deadline()
    )

    if eff is not None:
        remaining = eff - time.time()

        if remaining <= 0:
            return {
                "status": 0,
                "headers": {},
                "body": "",
                "error": "global deadline exceeded",
                "truncated": False,
            }

        timeout = min(timeout, remaining)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 "
            f"{AUDITOR_UA}"
        )
}

    token = _SKIP_ROBOTS_VAR.set(skip_robots)

    try:
        req = urllib.request.Request(
            url,
            headers=headers,
        )

        ctx = ssl.create_default_context()

        with _OPENER.open(req, timeout=timeout) as resp:
            # Re-check origin after redirect for the final URL.
            if not skip_robots:
                final_url = resp.geturl()
                final_parsed = urllib.parse.urlparse(final_url)
                final_origin = (
                    f"{final_parsed.scheme}://"
                    f"{final_parsed.netloc}"
                )

                _ROBOTS.load(final_origin)

                if not _ROBOTS.is_allowed(final_url):
                    return {
                        "status": 0,
                        "headers": {},
                        "body": "",
                        "error": "redirect blocked by robots.txt",
                        "truncated": False,
                    }

            status = resp.status
            hdrs = {
                k.lower(): v
                for k, v in resp.headers.items()
            }

            raw = resp.read(max_bytes)
            truncated = len(raw) >= max_bytes

            ct = hdrs.get("content-type", "")
            charset = "utf-8"

            if "charset=" in ct:
                charset = (
                    ct.split("charset=")[-1]
                    .split(";")[0]
                    .strip()
                    .strip('"')
                    .strip("'")
                )

            try:
                body = raw.decode(
                    charset,
                    errors="replace",
                )
            except Exception:
                body = raw.decode(
                    "utf-8",
                    errors="replace",
                )

            res = {
                "status": status,
                "headers": hdrs,
                "body": body,
                "error": None,
                "truncated": truncated,
            }

    except urllib.error.HTTPError as he:
        res = {
            "status": he.code if hasattr(he, "code") else 0,
            "headers": {},
            "body": "",
            "error": str(he),
            "truncated": False,
        }

    except urllib.error.URLError as ue:
        res = {
            "status": 0,
            "headers": {},
            "body": "",
            "error": str(ue),
            "truncated": False,
        }

    except Exception as e:
        res = {
            "status": 0,
            "headers": {},
            "body": "",
            "error": str(e),
            "truncated": False,
        }

    finally:
        _SKIP_ROBOTS_VAR.reset(token)

    if use_cache:
        FETCH_CACHE[cache_key] = res

    return res


# ───────────────────────────── findings ──────────────────────────────────

def create_finding(
    finding_id,
    title,
    severity,
    evidence,
    summary,
    impact,
    priority=None,
    code_snippet="",
    mechanism="content",
    **extra,
):
    sev = str(severity).strip().lower()

    if sev not in VALID_SEVERITIES:
        sys.stderr.write(
            f"Warning: invalid severity '{sev}' for "
            f"{finding_id}; using medium.\n"
        )
        sev = "medium"

    prio = (
        str(priority).strip().lower()
        if priority
        else sev
    )

    if prio not in VALID_SEVERITIES:
        prio = sev

    if mechanism not in {"config", "template", "content", "architectural", "external"}:
        sys.stderr.write(
            f"Warning: invalid mechanism '{mechanism}' for "
            f"{finding_id}; using content.\n"
        )
        mechanism = "content"

    action = {
        "summary": summary,
        "priority": prio,
        "impact": impact,
        "code_snippet": code_snippet,
    }

    for k, v in extra.items():
        if k in RESERVED_ACTION_KEYS:
            sys.stderr.write(
                f"Warning: extra key '{k}' shadows a "
                f"reserved field; ignored.\n"
            )
            continue

        action[k] = v

    return {
        "id": finding_id,
        "title": title,
        "severity": sev,
        "evidence": evidence,
        "mechanism": mechanism,
        "suggested_action": action,
    }


def robots_presence(url):
    """Tri-state: True (200 + body), False (404), None (transient)."""
    res = safe_fetch(url)

    if res["status"] == 200:
        return True if res["body"].strip() else False

    if res["status"] == 404:
        return False

    return None
