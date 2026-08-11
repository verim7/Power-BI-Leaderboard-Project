"""Fetch and normalise the llm-stats.com leaderboard.

The site publishes no API and renders with the Next.js App Router, so the
model records arrive as JSON embedded in the RSC "flight" payload:
self.__next_f.push([1, "<escaped chunk>"]). Concatenating the chunks, undoing
the JS string escaping and brace-matching from each '{"model_id"' anchor
recovers the records exactly as the server sent them.

That is far steadier than scraping rendered markup: the field names are the
site's own API contract with its client, so they change only when the site's
data model changes, not when someone restyles a table.

Modes:
  --report   diagnostics about the payload (used to develop the parser)
  --check    parity against the December 2025 slide figures, no files written
  (default)  write data/leaderboard_latest.{csv,json} + data/history/<date>.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

import requests

sys.path.insert(0, str(Path(__file__).parent))
from schema import (  # noqa: E402
    COLUMNS,
    DEVIATIONS,
    KNOWN_DIVERGENCES,
    SLIDE_REFERENCE,
    ModelRow,
)

URL = "https://llm-stats.com/leaderboards/llm-leaderboard"
UA = (
    "Mozilla/5.0 (compatible; PowerBI-Leaderboard-Sync/1.0; "
    "+https://github.com/verim7/Power-BI-Leaderboard-Project) "
    "training-material data sync, one request per day"
)
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# A leaderboard that suddenly has 3 models, or none, is a parse failure rather
# than news. Refuse to publish it.
MIN_MODELS = 15

# Below this share of matching reference values, assume the mapping broke
# rather than that the whole leaderboard was revised at once.
PARITY_FLOOR = 0.5


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def fetch_html(url: str = URL) -> str:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    resp.raise_for_status()
    return resp.text


def decode_flight(html: str) -> str:
    """Concatenate and unescape the RSC flight chunks."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    out: list[str] = []
    for chunk in chunks:
        try:
            # The chunk is a JS string literal body; JSON decoding is the
            # correct unescaping (handles \", \\, \n and \uXXXX properly,
            # unlike unicode_escape which mangles UTF-8).
            out.append(json.loads(f'"{chunk}"'))
        except Exception:  # noqa: BLE001
            out.append(chunk)
    return "".join(out)


def iter_json_objects(text: str, key: str) -> Iterator[dict[str, Any]]:
    """Yield every JSON object in `text` that has `key` among its own keys.

    A single string-aware pass keeps a stack of '{' positions, so each closing
    brace gives a complete object span. Spans are parsed innermost-first, and
    the `key in obj` test then selects the record objects rather than the
    wrappers that merely contain them.

    Scanning rather than regex matters here: model records hold string values
    containing braces, and a naive backwards search for '{' lands inside one.
    """
    stack: list[int] = []
    in_str = esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}" and stack:
            start = stack.pop()
            span = text[start : i + 1]
            if f'"{key}"' not in span:
                continue
            try:
                obj = json.loads(span)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(obj, dict) and key in obj:
                yield obj


def extract_records(html: str) -> list[dict[str, Any]]:
    """All model records, de-duplicated by model_id (the payload repeats them)."""
    flight = decode_flight(html)
    seen: dict[str, dict[str, Any]] = {}
    for obj in iter_json_objects(flight, "gpqa_score"):
        key = obj.get("model_id") or obj.get("name")
        if not key:
            continue
        # keep the record with the most populated fields
        best = seen.get(key)
        if best is None or _filled(obj) > _filled(best):
            seen[key] = obj
    return list(seen.values())


def _filled(obj: dict[str, Any]) -> int:
    return sum(1 for v in obj.values() if v is not None)


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------

def _score(value: Any) -> float | None:
    """Benchmark scores arrive on a 0-1 scale; the slide shows percent."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num < 0:
        return None
    # Tolerate a source that already publishes percent.
    return round(num * 100, 2) if num <= 1.5 else round(num, 2)


def _price(value: Any) -> float | None:
    """Normalise to USD per 1M tokens, whatever unit the source used."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    # A per-token price (1.25e-6) scaled to per-million is 1.25. Anything
    # below 0.001 must be per-token; real per-million prices start around 0.02.
    if num < 0.001:
        num *= 1_000_000
    return round(num, 4)


def to_rows(records: list[dict[str, Any]], as_of: str) -> list[ModelRow]:
    rows: list[ModelRow] = []
    for rec in records:
        name = (rec.get("name") or "").strip()
        if not name:
            continue
        lic = (rec.get("license") or "").strip()
        rows.append(
            ModelRow(
                organization=(rec.get("organization") or "").strip(),
                model=name,
                gpqa=_score(rec.get("gpqa_score")),
                aime_2025=_score(rec.get("aime_2025_score")),
                input_usd_per_m=_price(rec.get("input_price")),
                output_usd_per_m=_price(rec.get("output_price")),
                context_window=rec.get("context") if isinstance(rec.get("context"), int) else None,
                is_open_source=(lic.lower() != "proprietary") if lic else None,
                license=lic or None,
                as_of_date=as_of,
                source_url=URL,
            )
        )
    rows.sort(key=lambda r: (r.gpqa is None, -(r.gpqa or 0), r.model))
    return rows


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def parity_report(rows: list[ModelRow]) -> tuple[int, int, list[str]]:
    """Compare against the December 2025 slide.

    This checks the field *mapping*, not freshness. Three outcomes per value:
    a match; a divergence already documented in docs/DEVIATIONS.md; or an
    unexplained mismatch. Only the third kind counts against the parity floor,
    which keeps the check sensitive to a column moving without wedging the
    pipeline every time llm-stats revises a score.

    Returns (checked, passed, notes) where `passed` counts matches plus
    documented divergences.
    """
    by_name = {r.model: r for r in rows}
    checked = passed = 0
    notes: list[str] = []
    for name, expected in SLIDE_REFERENCE.items():
        row = by_name.get(name)
        if row is None:
            notes.append(f"  {name}: no longer on the leaderboard (models retire)")
            continue
        for field, want in expected.items():
            got = getattr(row, field)
            checked += 1
            if want is None and got is None:
                passed += 1
                continue
            if want is not None and got is not None:
                if isinstance(want, str):
                    ok = str(got).lower() == want.lower()
                else:
                    ok = abs(float(got) - float(want)) < 0.06
                if ok:
                    passed += 1
                    continue
            code = KNOWN_DIVERGENCES.get((name, field))
            if code:
                passed += 1
                notes.append(
                    f"  {name}.{field}: slide={want} now={got}  [{code}] {DEVIATIONS[code][:60]}..."
                )
            else:
                notes.append(
                    f"  {name}.{field}: slide={want} now={got}  <-- UNEXPLAINED, investigate"
                )
    return checked, passed, notes


def sanity_check(rows: list[ModelRow]) -> list[str]:
    problems: list[str] = []
    if len(rows) < MIN_MODELS:
        problems.append(f"only {len(rows)} models parsed (expected >= {MIN_MODELS})")
    if not any(r.gpqa is not None for r in rows):
        problems.append("no GPQA score on any row")
    if not any(r.output_usd_per_m is not None for r in rows):
        problems.append("no price on any row")
    for r in rows:
        if r.gpqa is not None and not 0 <= r.gpqa <= 100:
            problems.append(f"{r.model}: GPQA out of range ({r.gpqa})")
        if r.output_usd_per_m is not None and r.output_usd_per_m > 10_000:
            problems.append(f"{r.model}: implausible output price ({r.output_usd_per_m})")
    return problems


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def write_csv(rows: list[ModelRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())


def report(html: str, records: list[dict[str, Any]], rows: list[ModelRow]) -> None:
    print(f"\nHTML {len(html):,} bytes -> {len(records)} unique model records")
    if records:
        keys = sorted({k for r in records for k in r})
        print(f"\nfields present across records ({len(keys)}):\n  {keys}")
        priced = [r for r in records if r.get("input_price") or r.get("output_price")]
        print(f"\nrecords carrying a price: {len(priced)}/{len(records)}")
        for rec in priced[:3]:
            print(f"  {rec.get('name')}: input={rec.get('input_price')} output={rec.get('output_price')}")
        if not priced:
            print("  !! no prices on model records - looking for a separate price structure")
            flight = decode_flight(html)
            for pat in ('"input_price"', '"price"', '"pricing"', '"providers"', '"provider_models"'):
                idx = flight.find(pat)
                print(f"  {pat}: {'absent' if idx == -1 else f'at {idx}'}")
                if idx != -1:
                    print(f"    context: ...{flight[max(0,idx-300):idx+500]}...")
        print("\nfirst record verbatim:")
        print(json.dumps(records[0], indent=2)[:900])
    print(f"\nnormalised rows: {len(rows)}")
    for row in rows[:12]:
        print(
            f"  {row.model:<24} {row.organization:<12} "
            f"GPQA={row.gpqa!s:<7} AIME={row.aime_2025!s:<7} "
            f"in={row.input_usd_per_m!s:<8} out={row.output_usd_per_m!s:<8} {row.license}"
        )


def inspect(html: str, needle: str) -> None:
    """Every record matching `needle`, before de-duplication.

    De-duplication keeps the fullest record per model_id, so a parity mismatch
    is either a genuine revision upstream or the wrong record winning. This
    shows which.
    """
    flight = decode_flight(html)
    matches = [
        obj for obj in iter_json_objects(flight, "gpqa_score")
        if needle.lower() in str(obj.get("name", "")).lower()
    ]
    print(f"\n{len(matches)} raw record(s) matching {needle!r}:")
    for obj in matches:
        interesting = {
            k: obj.get(k) for k in
            ("model_id", "name", "organization", "release_date", "license",
             "gpqa_score", "aime_2025_score", "input_price", "output_price")
        }
        print(f"  {json.dumps(interesting)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="diagnostics only")
    ap.add_argument("--inspect", metavar="NAME", help="dump raw records matching NAME")
    ap.add_argument("--check", action="store_true", help="parity + sanity, write nothing")
    args = ap.parse_args()

    as_of = dt.date.today().isoformat()
    html = fetch_html()
    records = extract_records(html)
    rows = to_rows(records, as_of)

    if args.inspect:
        inspect(html, args.inspect)
    if args.report:
        report(html, records, rows)

    checked, passed, notes = parity_report(rows)
    print(f"\nslide parity: {passed}/{checked} reference values match")
    for note in notes:
        print(note)

    problems = sanity_check(rows)
    # Individual drift is expected - llm-stats revises scores and drops pricing
    # for models that are no longer served, and the slide is months old. A
    # wholesale mismatch is different: that means the column mapping broke.
    if checked and passed / checked < PARITY_FLOOR:
        problems.append(
            f"slide parity collapsed to {passed}/{checked} "
            f"(floor {PARITY_FLOOR:.0%}) - the field mapping has probably changed"
        )
    if problems:
        print("\nSANITY CHECK FAILED:")
        for p in problems:
            print(f"  - {p}")
        if not args.report:
            print("\nRefusing to publish. The last good CSV stays in place.")
            return 1

    if args.report or args.check:
        return 0

    write_csv(rows, DATA / "leaderboard_latest.csv")
    (DATA / "leaderboard_latest.json").write_text(
        json.dumps([r.as_dict() for r in rows], indent=2) + "\n", encoding="utf-8"
    )
    write_csv(rows, DATA / "history" / f"{as_of}.csv")
    print(f"\nwrote {len(rows)} rows, as of {as_of}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
