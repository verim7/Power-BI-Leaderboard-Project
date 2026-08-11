"""Reconnaissance for the llm-stats.com leaderboard.

We cannot reach llm-stats.com from the dev container (egress policy), so this
script runs on a GitHub Actions runner and reports the page's structure back
through the job log. Its only job is to answer: where do the numbers live?

  1. server-rendered <table> markup
  2. Next.js payload (__NEXT_DATA__ or the App Router's self.__next_f chunks)
  3. a JSON endpoint the page calls itself
  4. nothing static -> we need headless Chromium

Run:  python scraper/probe.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

URL = "https://llm-stats.com/leaderboards/llm-leaderboard"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
OUT = Path("probe-output")

# Values read off the December 2025 slide. If we find these in the payload we
# have found the data, whatever shape it is in.
NEEDLES = ["Gemini 3 Pro", "GPQA", "91.9", "Grok-4", "Claude Opus 4.5", "AIME"]


def banner(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def fetch(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"}, timeout=45)
        print(f"GET {url} -> {r.status_code} ({len(r.content):,} bytes, {r.headers.get('content-type','?')})")
        return r
    except Exception as exc:  # noqa: BLE001 - diagnostics only
        print(f"GET {url} -> FAILED: {type(exc).__name__}: {exc}")
        return None


def report_needles(label: str, text: str) -> int:
    hits = [n for n in NEEDLES if n in text]
    print(f"{label}: {len(hits)}/{len(NEEDLES)} marker strings present -> {hits}")
    return len(hits)


def describe_json(obj, path: str = "$", depth: int = 0, max_depth: int = 4) -> None:
    """Print a shallow shape summary so we can see where the rows are."""
    pad = "  " * depth
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        print(f"{pad}{path} = object({len(obj)}) keys={list(obj)[:14]}")
        for k, v in list(obj.items())[:14]:
            if isinstance(v, (dict, list)):
                describe_json(v, f"{path}.{k}", depth + 1, max_depth)
    elif isinstance(obj, list):
        print(f"{pad}{path} = array[{len(obj)}]")
        if obj and isinstance(obj[0], (dict, list)):
            describe_json(obj[0], f"{path}[0]", depth + 1, max_depth)
        elif obj:
            print(f"{pad}  sample: {json.dumps(obj[:4])[:200]}")


def main() -> int:
    OUT.mkdir(exist_ok=True)

    banner("1. Fetch the leaderboard page")
    resp = fetch(URL)
    if resp is None or resp.status_code != 200:
        print("\nFATAL: could not fetch the page at all.")
        return 1

    html = resp.text
    (OUT / "leaderboard.html").write_text(html, encoding="utf-8")
    print(f"saved -> {OUT / 'leaderboard.html'}")
    report_needles("raw HTML", html)

    banner("2. HTML tables")
    tables = re.findall(r"<table[^>]*>", html, re.I)
    rows = re.findall(r"<tr[^>]*>", html, re.I)
    print(f"<table> elements: {len(tables)}   <tr> elements: {len(rows)}")
    if tables:
        first = html[html.lower().find("<table") : html.lower().find("<table") + 2500]
        print("--- first 2500 chars of first table ---")
        print(first)

    banner("3. Next.js payloads")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        print("__NEXT_DATA__ FOUND (Pages Router)")
        try:
            data = json.loads(m.group(1))
            (OUT / "next_data.json").write_text(json.dumps(data, indent=2)[:4_000_000], encoding="utf-8")
            describe_json(data)
        except Exception as exc:  # noqa: BLE001
            print(f"could not parse __NEXT_DATA__: {exc}")
    else:
        print("__NEXT_DATA__ absent")

    flight = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    print(f"self.__next_f.push chunks (App Router RSC flight data): {len(flight)}")
    if flight:
        joined = "".join(flight)
        try:
            joined = joined.encode().decode("unicode_escape")
        except Exception:  # noqa: BLE001
            pass
        (OUT / "flight.txt").write_text(joined, encoding="utf-8", errors="replace")
        print(f"decoded flight payload: {len(joined):,} chars -> {OUT / 'flight.txt'}")
        report_needles("flight payload", joined)
        for needle in ("Gemini 3 Pro", "gpqa", "GPQA"):
            i = joined.find(needle)
            if i != -1:
                print(f"\n--- context around {needle!r} (offset {i}) ---")
                print(joined[max(0, i - 700) : i + 1400])
                break

    banner("4. Embedded JSON script tags")
    blobs = re.findall(r'<script[^>]+type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', html, re.S)
    print(f"application/json script tags: {len(blobs)}")
    for i, blob in enumerate(blobs[:5]):
        try:
            describe_json(json.loads(blob), f"blob[{i}]")
        except Exception:  # noqa: BLE001
            print(f"blob[{i}] not valid JSON ({len(blob)} chars)")

    banner("5. Candidate API endpoints referenced by the page")
    paths = sorted(set(re.findall(r'["\'](/api/[a-zA-Z0-9_\-/\.]+)["\']', html)))
    print(f"/api/ paths in HTML: {paths[:40]}")
    for guess in ["/api/models", "/api/leaderboard", "/api/leaderboards/llm-leaderboard", "/api/v1/models"]:
        r = fetch("https://llm-stats.com" + guess)
        if r is not None and r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            print(f"  ^ JSON endpoint works: {guess}")
            (OUT / f"api_{guess.strip('/').replace('/', '_')}.json").write_text(r.text, encoding="utf-8")
            try:
                describe_json(r.json(), guess)
            except Exception:  # noqa: BLE001
                pass

    banner("6. Verdict")
    print("Read sections 2-5 above: whichever section contains the marker strings")
    print("is the extraction strategy for scraper/fetch_leaderboard.py.")
    print("If only section 1 has them and 2-5 are empty, the table is client-rendered")
    print("and we need Playwright + headless Chromium.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
