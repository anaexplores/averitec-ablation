"""Fetch the fact-checking articles referenced by AVeriTeC claims and store plain-text extractions.

Preexisting pattern reused from anaexplores/lost-caveats fetch_fulltext.py:
HTML parsed with Python html.parser dropping script/style/noscript/svg/head, then html.unescape;
CR and CRLF turned into LF before hashing. The AVeriTeC data itself (data/train.json, data/dev.json,
CC BY-NC 4.0, MichSchli/AVeriTeC) is external new material for the sprint.

For every unique fact_checking_article URL the script stores fulltext/<key>.txt, where <key> is a
stable short hash of the URL, and appends a manifest entry (URL, HTTP status, SHA-256 of the
extracted text, byte count, fetch date). Re-running skips URLs already present in the manifest.

    python pipeline/fetch_articles.py --averitec-file data/dev.json          # tuning-pool articles
    python pipeline/fetch_articles.py --averitec-file data/dev.json data/train.json
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "fulltext_manifest.json")
SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}


class _Extractor:
    """Minimal html.parser subclass: drop SKIP_TAGS subtrees, break on BLOCK_TAGS."""

    def __init__(self):
        import html.parser
        self._p = html.parser.HTMLParser(convert_charrefs=False)
        self._p.handle_starttag = self.handle_starttag
        self._p.handle_endtag = self.handle_endtag
        self._p.handle_data = self.handle_data
        self._p.handle_entityref = self.handle_entityref
        self._p.handle_charref = self.handle_charref
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def handle_entityref(self, name):
        if not self._skip:
            self.parts.append(html.unescape(f"&{name};"))

    def handle_charref(self, name):
        if not self._skip:
            self.parts.append(html.unescape(f"&#{name};"))


def extract_text(raw, content_type):
    """Plain text from HTML or raw bytes; non-HTML payloads are kept as decoded text."""
    text = raw.decode("utf-8", errors="replace")
    if content_type and "html" in content_type.lower():
        ex = _Extractor()
        ex._p.feed(text)
        ex._p.close()
        text = "".join(ex.parts)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


WAYBACK_HEADER_RE = re.compile(
    r"^The Wayback Machine - https?://", re.M)
WAYBACK_NOISE_LINES = {
    "about this capture",
    "timestamps",
    "success",
    "fail",
    "wayback machine hasn't archived that url.",
    "support the wayback machine",
}


def strip_wayback_banner(text):
    """Drop the Wayback Machine UI block that archive.org prepends/appends to captures."""
    lines = text.split("\n")
    keep, out = False, []
    for line in lines:
        stripped = line.strip()
        if not keep:
            # Content starts after the machine banner line ("The Wayback Machine - https://...").
            if WAYBACK_HEADER_RE.match(line):
                keep = True
            continue
        if stripped.lower() in WAYBACK_NOISE_LINES:
            continue
        out.append(line)
    cleaned = "\n".join(out) if keep else text
    # Trailing capture footer, if any survived.
    for marker in ("About this capture", "TIMESTAMPS"):
        idx = cleaned.rfind(marker)
        if idx != -1 and len(cleaned) - idx < 4000 and idx > len(cleaned) * 0.8:
            cleaned = cleaned[:idx]
    return cleaned.strip()


def url_key(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            return {e["url"]: e for e in json.load(f)}
    return {}


def save_manifest(m):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(sorted(m.values(), key=lambda e: e["url"]), f, indent=1)


def article_urls(averitec_files):
    urls = set()
    for path in averitec_files:
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if r.get("fact_checking_article"):
                    urls.add(r["fact_checking_article"])
    return sorted(urls)


def fetch_one(url, out_dir, delay=0.0, last_call=[0.0]):
    """Fetch one URL; returns a manifest entry (successes and failures both logged)."""
    import threading
    lock = getattr(fetch_one, "_lock", None)
    if lock is None:
        lock = fetch_one._lock = threading.Lock()
    if delay:
        with lock:
            now = time.time()
            wait = (last_call[0] + delay) - now
            if wait > 0:
                time.sleep(wait)
            last_call[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "averitec-ablation/0.1 (research; contact via repo)"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            status = resp.status
    except urllib.error.HTTPError as e:
        return {"url": url, "status": e.code, "error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001 - network errors are logged, not raised
        return {"url": url, "status": None, "error": str(e)[:200]}
    text = extract_text(raw, ctype)
    if len(text) < 200:
        return {"url": url, "status": status, "error": f"suspiciously short extraction ({len(text)} chars)"}
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = strip_wayback_banner(text)
    if len(text) < 200:
        return {"url": url, "status": status, "error": f"empty after banner cleanup ({len(text)} chars)"}
    key = url_key(url)
    path = os.path.join(out_dir, f"{key}.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return {
        "url": url,
        "key": key,
        "status": status,
        "content_type": ctype,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "chars": len(text),
        "fetched": "2026-11-15",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--averitec-file", nargs="+", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=1.0, help="min seconds between requests globally")
    ap.add_argument("--limit", type=int, default=0, help="fetch at most N new URLs (0 = all)")
    args = ap.parse_args(argv)

    out_dir = os.path.join(ROOT, "fulltext")
    os.makedirs(out_dir, exist_ok=True)
    manifest = load_manifest()
    todo = [u for u in article_urls(args.averitec_file)
            if u not in manifest or "error" in manifest[u]]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} URLs to fetch ({len(manifest)} already in manifest)")

    ok = fail = 0
    for i, entry in enumerate(ThreadPoolExecutor(args.workers).map(
            lambda u: fetch_one(u, out_dir, args.delay), todo), 1):
        manifest[entry["url"]] = entry  # failures are logged too, so retries can target them
        if "error" not in entry:
            ok += 1
        else:
            fail += 1
        if i % 25 == 0 or i == len(todo):
            print(f"{i}/{len(todo)} done ({ok} ok, {fail} failed)")
            save_manifest(manifest)
    save_manifest(manifest)
    print(f"finished: {ok} ok, {fail} failed; manifest has {len(manifest)} entries")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
