"""The canonical leaderboard schema.

This is a published contract: Power BI binds to these column names, and the
PowerPoint updater reads them. Renaming a column here breaks the .pbix and the
deck script, so add columns rather than renaming them.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, fields
from typing import Optional

# Column order is the CSV's column order, and matches the slide left-to-right
# for the columns the slide shows.
COLUMNS = [
    "organization",
    "model",
    "gpqa",
    "aime_2025",
    "input_usd_per_m",
    "output_usd_per_m",
    "context_window",
    "is_open_source",
    "license",
    "as_of_date",
    "source_url",
]


@dataclass
class ModelRow:
    organization: str
    model: str
    gpqa: Optional[float] = None            # percent, 0-100
    aime_2025: Optional[float] = None       # percent, 0-100
    input_usd_per_m: Optional[float] = None  # USD per 1M input tokens
    output_usd_per_m: Optional[float] = None
    context_window: Optional[int] = None
    is_open_source: Optional[bool] = None
    license: Optional[str] = None
    as_of_date: str = ""
    source_url: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


assert [f.name for f in fields(ModelRow)] == COLUMNS, "COLUMNS must mirror ModelRow"


# Reference values transcribed from slide 144 of the training deck
# ("As of december 2025"). The scraper asserts against these for models whose
# figures should not have moved, which catches a silent column-order change
# far more reliably than a row count does.
#
# A mismatch here means the *mapping* is wrong, not that the site changed:
# a genuinely updated score moves by a little, a mis-mapped column is nonsense.
SLIDE_REFERENCE = {
    "Gemini 3 Pro":    {"organization": "Google",    "gpqa": 91.9, "aime_2025": 100.0, "input_usd_per_m": 2.00, "output_usd_per_m": 12.00},
    "Grok-4 Heavy":    {"organization": "xAI",       "gpqa": 88.4, "aime_2025": 100.0, "input_usd_per_m": None, "output_usd_per_m": None},
    "GPT-5.1":         {"organization": "OpenAI",    "gpqa": 88.1, "aime_2025": 94.0,  "input_usd_per_m": 1.25, "output_usd_per_m": 10.00},
    "Grok-4":          {"organization": "xAI",       "gpqa": 87.5, "aime_2025": 91.7,  "input_usd_per_m": 3.00, "output_usd_per_m": 15.00},
    "Claude Opus 4.5": {"organization": "Anthropic", "gpqa": 87.0, "aime_2025": None,  "input_usd_per_m": 5.00, "output_usd_per_m": 25.00},
    "Gemini 2.5 Pro":  {"organization": "Google",    "gpqa": 86.4, "aime_2025": 88.0,  "input_usd_per_m": 1.25, "output_usd_per_m": 10.00},
}

# Reference values that no longer match, each with a reason. Documented in
# docs/DEVIATIONS.md. These are reported but do not count as unexplained
# mismatches, so the mapping check stays sensitive to real breakage.
#
# Removing an entry here is a claim that the divergence went away - the next
# run will tell you whether that is true.
KNOWN_DIVERGENCES = {
    ("Gemini 2.5 Pro", "gpqa"): "D1",
    ("Gemini 2.5 Pro", "aime_2025"): "D1",
    ("Gemini 3 Pro", "input_usd_per_m"): "D2",
    ("Gemini 3 Pro", "output_usd_per_m"): "D2",
    ("Grok-4", "input_usd_per_m"): "D2",
    ("Grok-4", "output_usd_per_m"): "D2",
    ("Claude Opus 4.5", "input_usd_per_m"): "D2",
    ("Claude Opus 4.5", "output_usd_per_m"): "D2",
}

DEVIATIONS = {
    "D1": "Slide row 'Gemini 2.5 Pro' splices two models: the 86.4/88.0 scores "
          "belong to 'Gemini 2.5 Pro Preview 06-05', the 1.25/10.00 prices to "
          "the GA 'Gemini 2.5 Pro' (83.0/83.0). The pipeline uses one model "
          "consistently.",
    "D2": "llm-stats no longer publishes pricing for these models (87 of 340 "
          "records carry a price). Rendered 'n/a', as the slide already does "
          "for Grok-4 Heavy - never as 0.00.",
}


# The eight rows the slide prints, in slide order. deck/update_slide.py uses
# this when the deck should keep showing exactly this shortlist.
SLIDE_MODELS = [
    "Gemini 3 Pro",
    "Grok-4 Heavy",
    "GPT-5.1",
    "GPT-5.1 Instant",
    "GPT-5.1 Thinking",   # the slide abbreviates this to "GPT-5.1 Think."
    "Grok-4",
    "Claude Opus 4.5",
    "Gemini 2.5 Pro",
]
