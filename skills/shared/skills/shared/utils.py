"""
Shared utilities for Brand AI-Readiness Audit Marketplace.
Strictly relies on Python 3.6+ Standard Library.
Provides memory-guarded HTTP fetching and structured HTML/JSON-LD parsing.
"""

import json
import ssl
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

# --- MEMORY & TIMEOUT CONSTANTS ---
MAX_PAYLOAD_BYTES = 1024 * 1024  # Strict 1MB Guard
DEFAULT_TIMEOUT = 10              # 10s socket timeout
MAX_REDIRECTS = 5                 # Prevent circular redirect loops


class CustomRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom redirect handler enforcing a strict 5-hop maximum."""
    def __init__(self, max_redirects=MAX_REDIRECTS):
        super().__init__()
        self.max_redirects = max_redirects
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > self.max_redirects:
            raise urllib.error.HTTPError(
                req.full_url, code, f"Exceeded maximum allowed redirects ({self.max_redirects})", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_fetch(url, headers=None, timeout=DEFAULT_TIMEOUT):
    """
    Safely fetches URL content with:
    - Custom SSL context (ignores non-fatal cert errors)
    - 5-hop redirect capping
    - 10s socket connection timeout
    - Strict 1MB payload streaming cap
    - Encoding auto-detection with fallback
    """
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Compatible; BrandAIAuditBot/1.0; +https://agentskills.io)"
        }

    # Defensive SSL Context
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    redirect_handler = CustomRedirectHandler(MAX_REDIRECTS)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_ctx),
        redirect_handler
    )

    req = urllib.request.Request(url, headers=headers)

    try:
        with opener.open(req, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            encoding = 'utf-8'
            if 'charset=' in content_type:
                encoding = content_type.split('charset=')[-1].split(';')[0].strip()

            # Stream max 1MB
            raw_data = response.read(MAX_PAYLOAD_BYTES)
            
            try:
                html_text = raw_data.decode(encoding, errors='replace')
            except Exception:
                html_text = raw_data.decode('utf-8', errors='replace')

            return {
                "status": response.status,
                "url": response.geturl(),
                "headers": dict(response.headers),
                "body": html_text,
                "error": None
            }
    except Exception as e:
        return {
            "status": None,
            "url": url,
            "headers": {},
            "body": "",
            "error": str(e)
        }


class RobustHTMLParser(HTMLParser):
    """
    Standard Library HTMLParser subclass extracting:
    - Meta tags (robots, viewport, canonical, etc.)
    - JSON-LD blocks (<script type="application/ld+json">)
    - Headings and IDs for context retention anchor checks
    - Image tags for missing alt/spec attribution
    - Interactive accordions and client-side dynamic tabs
    """
    def __init__(self):
        super().__init__()
        self.meta_tags = {}
        self.json_ld_blocks = []
        self.headings = []      # Dicts: {'tag': 'h1', 'id': '...', 'text': '...'}
        self.images = []        # Dicts: {'src': '...', 'alt': '...'}
        self.links = []         # Dicts: {'href': '...', 'rel': '...', 'id': '...'}
        self.scripts = []       # Dicts: {'src': '...', 'inline': '...'}
        self.accordions = []    # Dicts: {'tag': '...', 'class': '...', 'id': '...'}
        
        self._in_script = False
        self._in_script_json = False
        self._current_heading = None
        self._script_buffer = []

    def handle_starttag(self, tag, attrs):
        attr_dict = {k.lower(): v for k, v in attrs if k}
        class_name = attr_dict.get('class', '').lower()
        tag_id = attr_dict.get('id', '')

        # Detect accordions / tab containers that might hide specs from bots
        if 'accordion' in class_name or 'tab' in class_name or 'collapse' in class_name:
            self.accordions.append({
                'tag': tag,
                'class': class_name,
                'id': tag_id
            })

        # Extract Meta Tags
        if tag == 'meta':
            name = attr_dict.get('name') or attr_dict.get('property')
            content = attr_dict.get('content')
            if name and content:
                self.meta_tags[name.lower()] = content

        # Track Script Blocks (JSON-LD and inline JS)
        elif tag == 'script':
            self._in_script = True
            script_type = attr_dict.get('type', '').lower()
            src = attr_dict.get('src', '')
            if src:
                self.scripts.append({'src': src, 'inline': ''})
            if script_type == 'application/ld+json':
                self._in_script_json = True
                self._script_buffer = []

        # Headings for Deep-Anchor checks
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self._current_heading = {
                'tag': tag,
                'id': tag_id,
                'text': ''
            }

        # Image extraction for hidden spec detection
        elif tag == 'img':
            self.images.append({
                'src': attr_dict.get('src', ''),
                'alt': attr_dict.get('alt', '')
            })

        # Links for canonical / relationship validation
        elif tag == 'a':
            if 'href' in attr_dict:
                self.links.append({
                    'href': attr_dict.get('href', ''),
                    'rel': attr_dict.get('rel', ''),
                    'id': tag_id
                })

    def handle_data(self, data):
        if self._in_script_json:
            self._script_buffer.append(data)
        elif self._in_script and data.strip():
            self.scripts.append({'src': '', 'inline': data.strip()})
        if self._current_heading is not None:
            self._current_heading['text'] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            if self._in_script_json:
                full_json_str = "".join(self._script_buffer).strip()
                if full_json_str:
                    try:
                        parsed_json = json.loads(full_json_str)
                        self.json_ld_blocks.append(parsed_json)
                    except Exception:
                        self.json_ld_blocks.append({"_parse_error": full_json_str})
                self._in_script_json = False
                self._script_buffer = []
            self._in_script = False

        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'] and self._current_heading:
            self._current_heading['text'] = self._current_heading['text'].strip()
            self.headings.append(self._current_heading)
            self._current_heading = None


def parse_html_content(html_str):
    """Helper utility to parse HTML string safely using RobustHTMLParser."""
    parser = RobustHTMLParser()
    try:
        parser.feed(html_str)
    except Exception as e:
        sys.stderr.write(f"HTML Parsing Warning: {e}\n")
    return parser