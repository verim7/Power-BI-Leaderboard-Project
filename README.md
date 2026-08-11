# Power BI LLM Leaderboard

Keeps the AI Leaderboard on slide 144 of the AI training deck honest, by
replacing a hand-typed table with a pipeline.

The slide was accurate in December 2025 and is being taught months later. Every
model launch and price cut quietly makes the teaching material wrong, and the
argument the slide makes — *"price becomes a key factor in selecting the right
model"* — rots fastest of all, because prices move faster than benchmarks.

```
llm-stats.com
     │  GitHub Actions, daily
     ▼
data/leaderboard_latest.csv  ─────────────► Power BI ──► live add-in on the slide
data/history/YYYY-MM-DD.csv                    │
     │                                         └──────► exported image
     └──────────────────────────────► deck/update_slide.py ──► native table
```

## Why the CSV in the middle

Pointing Power Query straight at the website is the obvious design and the wrong
one. Scraping inside M is brittle, and `Web.Page` does not survive scheduled
refresh in the Power BI Service. Splitting the job means the fragile part fails
in CI, loudly, where a failure is a red build rather than a wrong number in
front of a room.

It also makes every daily commit a price snapshot, so the deck can show how fast
this market actually moves.

## Layout

| Path | What it is |
|---|---|
| `scraper/fetch_leaderboard.py` | fetch, parse, normalise, validate |
| `scraper/schema.py` | the published column contract and the slide reference values |
| `scraper/probe.py` | on-demand diagnostic for when the site changes shape |
| `scraper/tests/` | offline tests, no network |
| `data/leaderboard_latest.csv` | what Power BI reads |
| `data/history/` | one snapshot per day the numbers moved |
| `powerbi/queries/*.m` | Power Query source |
| `powerbi/measures/measures.dax` | measures |
| `powerbi/BUILD.md` | click-by-click build and publish |
| `deck/update_slide.py` | rewrites the PowerPoint table from the CSV |
| `docs/DEVIATIONS.md` | every figure that no longer matches the slide, and why |

## How the data is obtained

llm-stats.com publishes no API, and its open-data repository is deprecated. The
site renders with the Next.js App Router, so its model records arrive as JSON
inside the RSC payload — `self.__next_f.push([1, "…"])`. Concatenating those
chunks, undoing the escaping and brace-matching out each record recovers the
data exactly as the server sent it. Those field names are the site's own
contract with its client, so they are steadier than rendered markup: they change
when the data model changes, not when someone restyles a table.

Scores arrive on a 0–1 scale and become the percentages the slide shows. Prices
are normalised to USD per million tokens. **Nulls stay null** — 87 of 340 models
currently have no published price, and on a slide about cost, "free" and
"unpriced" are opposite claims.

## Guardrails

- **Slide parity.** Every run compares against the December 2025 figures. That
  checks the column *mapping*, not freshness. Divergences that are understood
  are listed in `docs/DEVIATIONS.md`; anything else is flagged as unexplained,
  and if the mapping collapses below 50 % the run fails.
- **Sanity checks.** Too few models, no scores, no prices, a percentage out of
  range — any of these fail the job.
- **A failed run publishes nothing.** The previous CSV stays. A stale dashboard
  is recoverable; a confidently wrong one is not.
- **Pushes never publish.** Only the schedule commits data, so a parser being
  developed cannot overwrite good numbers.

## Running it

```bash
pip install -r scraper/requirements.txt
python scraper/fetch_leaderboard.py --check     # validate, write nothing
python scraper/fetch_leaderboard.py --report    # + diagnostics
python scraper/fetch_leaderboard.py             # write the CSVs
python -m pytest scraper/tests deck/tests -q
```

Updating the deck:

```bash
pip install -r deck/requirements.txt
python deck/update_slide.py --deck AI_Training.pptx --dry-run
python deck/update_slide.py --deck AI_Training.pptx
```

`--dry-run` prints every cell it would change. Without `--in-place` it writes a
copy and leaves the original alone.

## Before this goes live

The daily refresh runs from `main` — scheduled workflows only ever run on a
repository's default branch. GitHub also disables a schedule after 60 days
with no repository activity, and the daily data commits are enough to keep it
alive, but a long quiet spell is worth checking after.

The training deck is private and confidential material. This repository is
public, so the `.pptx`, exported slide images, and any branded asset must
never be committed here — see the `.gitignore`. Only the deck updater
script lives in the repo; it runs against a deck kept outside it.

## Source and attribution

Data from [llm-stats.com](https://llm-stats.com/leaderboards/llm-leaderboard),
fetched once a day with an identifying User-Agent. The slide already credits the
source; keep that credit.
