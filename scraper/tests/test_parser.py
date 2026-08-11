"""Offline tests for the extraction and normalisation logic.

The fixture is a verbatim model record captured from the live RSC payload by
scraper/probe.py, wrapped in the same self.__next_f.push escaping the site
uses. That lets the parser be tested without touching the network.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_leaderboard import (  # noqa: E402
    _price,
    _score,
    decode_flight,
    extract_records,
    iter_json_objects,
    parity_report,
    sanity_check,
    to_rows,
)

# Captured verbatim from the probe run (offset 61947 of the flight payload).
GEMINI = {
    "model_id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "organization": "Google",
    "organization_id": "google", "organization_country": "US", "params": None,
    "context": None, "release_date": "2025-11-18", "multimodal": True,
    "license": "proprietary", "knowledge_cutoff": "2025-01-31",
    "input_price": 2.0, "output_price": 12.0,
    "aime_2025_score": 1, "hle_score": 0.458, "gpqa_score": 0.919,
    "swe_bench_verified_score": 0.762, "mmmlu_score": 0.918, "index_general": 39.01,
}
OPUS = {
    "model_id": "claude-opus-4-5", "name": "Claude Opus 4.5", "organization": "Anthropic",
    "license": "proprietary", "context": 200000,
    "input_price": 5.0, "output_price": 25.0,
    "aime_2025_score": None, "gpqa_score": 0.87,
}
LLAMA = {
    "model_id": "llama-4-maverick", "name": "Llama 4 Maverick", "organization": "Meta",
    "license": "llama-4-community", "context": 1000000,
    "input_price": 0.00000027, "output_price": 0.00000085,
    "aime_2025_score": 0.42, "gpqa_score": 0.694,
}


def build_html(records: list[dict]) -> str:
    """Wrap records the way the App Router serialises them."""
    payload = 'a:["$","div",null,{"models":' + json.dumps(records, separators=(",", ":")) + "}]"
    escaped = json.dumps(payload)[1:-1]  # JS string literal body
    return (
        "<!DOCTYPE html><html><body>"
        f'<script>self.__next_f.push([1,"{escaped}"])</script>'
        "</body></html>"
    )


def test_decode_flight_roundtrip():
    html = build_html([GEMINI])
    flight = decode_flight(html)
    assert '"model_id":"gemini-3-pro-preview"' in flight.replace(", ", ",")
    assert "\\u" not in flight


def test_iter_json_objects_is_string_aware():
    text = '{"a":"has { and } inside","gpqa_score":0.5,"n":{"deep":1}}'
    objs = list(iter_json_objects(text, "gpqa_score"))
    assert len(objs) == 1
    assert objs[0]["a"] == "has { and } inside"
    assert objs[0]["n"] == {"deep": 1}


def test_extract_and_normalise():
    rows = to_rows(extract_records(build_html([GEMINI, OPUS, LLAMA])), "2026-08-11")
    assert len(rows) == 3
    by = {r.model: r for r in rows}

    g = by["Gemini 3 Pro"]
    assert g.gpqa == 91.9          # 0.919 -> percent, matches the slide
    assert g.aime_2025 == 100.0    # 1 -> percent
    assert g.input_usd_per_m == 2.0
    assert g.is_open_source is False

    # per-token pricing is rescaled to per-million
    m = by["Llama 4 Maverick"]
    assert m.input_usd_per_m == 0.27
    assert m.output_usd_per_m == 0.85
    assert m.is_open_source is True

    # a null benchmark stays null rather than becoming a confident zero
    assert by["Claude Opus 4.5"].aime_2025 is None


def test_rows_sort_by_gpqa_desc():
    rows = to_rows(extract_records(build_html([OPUS, LLAMA, GEMINI])), "2026-08-11")
    assert [r.model for r in rows][0] == "Gemini 3 Pro"


def test_duplicate_records_keep_the_fullest():
    sparse = dict(GEMINI, input_price=None, output_price=None, hle_score=None)
    rows = to_rows(extract_records(build_html([sparse, GEMINI])), "2026-08-11")
    assert len(rows) == 1
    assert rows[0].input_usd_per_m == 2.0


def test_parity_against_the_slide():
    rows = to_rows(extract_records(build_html([GEMINI, OPUS])), "2026-08-11")
    checked, passed, notes = parity_report(rows)
    mismatches = [n for n in notes if "MISMATCH" in n or "null mismatch" in n]
    assert not mismatches, mismatches
    assert passed == checked > 0


def test_known_divergence_is_reported_but_not_an_unexplained_mismatch():
    """D1: the GA Gemini 2.5 Pro scores differ from the slide, by design."""
    ga = dict(
        GEMINI, model_id="gemini-2.5-pro", name="Gemini 2.5 Pro",
        gpqa_score=0.83, aime_2025_score=0.83, input_price=1.25, output_price=10.0,
    )
    rows = to_rows(extract_records(build_html([ga])), "2026-08-11")
    checked, passed, notes = parity_report(rows)
    assert not [n for n in notes if "UNEXPLAINED" in n]
    assert [n for n in notes if "[D1]" in n], notes
    assert passed == checked   # documented divergences still count as passing


def test_sanity_check_rejects_a_broken_parse():
    assert sanity_check([]) != []
    rows = to_rows(extract_records(build_html([GEMINI])), "2026-08-11")
    assert "only 1 models parsed" in " ".join(sanity_check(rows))


def test_score_and_price_edges():
    assert _score(None) is None
    assert _score(0) == 0.0
    assert _score(1) == 100.0
    assert _score(88.1) == 88.1      # already percent
    assert _price(None) is None
    assert _price(0) is None         # free/unknown is not a real price
    assert _price(1.25) == 1.25
    assert _price(0.00000125) == 1.25
