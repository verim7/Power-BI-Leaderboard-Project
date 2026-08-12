# Building the .pbix

Power BI Desktop is Windows-only and cannot be scripted from this repository,
so the model is assembled once by hand from the queries and measures here.
Budget about an hour the first time.

Everything below assumes the refresh workflow is already publishing
`data/leaderboard_latest.csv`.

---

## 0. How Power BI reaches the CSV

**Already decided: the repository is public and the queries are set up for it.**
`UseGitHubApi = false`, anonymous, nothing to configure. Skip to step 1 unless
the repository is ever made private again.

### A. Public repository (current setup)

The CSV holds nothing confidential: it is public benchmark and pricing data
scraped from a public website. The *deck* is the confidential asset, and it is
not in this repository.

This repository is public and holds no deck material, so the CSV is served
anonymously from `raw.githubusercontent.com`.

- no token, no rotation, no secret in the .pbix
- scheduled refresh in the Service works with **Anonymous** auth and no gateway
- anyone with the URL can read the CSV, which for this data is fine

### B. If the repository ever goes private again

Create a **fine-grained** personal access token: this repository only,
*Contents: Read-only*, with an expiry you will actually diarise.

In `Leaderboard.m` keep `UseGitHubApi = true` and put the token in the
`GitHubToken` parameter.

- the repository stays private
- the token is stored in the .pbix and in the Service's data source credentials,
  so anyone you send the file to inherits read access to the repo
- it expires, and refresh fails when it does

Option A is what is configured. Option B is the fallback if the repository ever
has to hold something sensitive.

---

## 1. Create the file

Power BI Desktop → **Blank report** → save as `powerbi/AI-Leaderboard.pbix`.

The .gitignore excludes `*.pbix`, which matters under option B where the file
would contain the token.

## 2. Add the Leaderboard query

**Home → Transform data → New Source → Blank Query**, then **Advanced Editor**,
and paste the whole of `powerbi/queries/Leaderboard.m`. Name the query
`Leaderboard`.

The configuration block at the top is already set for this repository:
`Branch = "main"`, `UseGitHubApi = false`.

When prompted for credentials choose **Anonymous** — under option B the token
travels in the header, not in Power BI's credential store.

Check in the preview:
- `gpqa` and the price columns are **Decimal Number**, and blanks are blanks
- `as_of_date` is **Date**
- `is_open_source` is **True/False**

## 3. Add the shortlist query — optional

Another blank query, paste `powerbi/queries/SlideShortlist.m`, name it
`SlideShortlist`. It references `Leaderboard`, so create it second.

**Skippable.** No measure reads it; it only pins the slide's eight rows to a
fixed order. Without it, build the table visual on `Leaderboard` and filter to
the models you want. Add it later if you get tired of maintaining that filter
by hand.

**Close & Apply.**

## 4. Add the measures

**Modeling → New measure**, once per measure in
`powerbi/measures/measures.dax`. Every block begins with its measure name and
the comments sit underneath it, because the formula bar rejects a comment
placed above the name. Select from the name down to the blank line and paste
the lot.

### If you are short on time

Nine of the twenty carry the argument and the honesty. Do these first and add
the rest when you want them:

| Measure | Why it earns its place |
|---|---|
| `Data as of` | the slide's footnote, live |
| `Days since refresh` | feeds the two below |
| `Freshness warning` | says nothing until the pipeline stalls |
| `GPQA display`, `AIME display` | render a missing benchmark as `n/a` |
| `Input price display`, `Output price display` | render a withdrawn price as `n/a` |
| `Price spread near the top` | the "N× more expensive for the same accuracy" number |
| `Best value near the top` | names the model the slide implies but never states |

Skipping the four display measures is survivable — Power BI shows a blank cell,
which is honest if less explicit. What must never happen is a blank rendering
as `0.00`, and using the raw columns with a "0.00" format string would do
exactly that.

Set formatting: percentages to 1 decimal, prices to 2, `Days since refresh` to
whole number.

## 5. Build the pages

### Page 1 — "Leaderboard" (this is the page the deck embeds)

Sized to sit on the slide: **View → Page view → Actual size**, then
**Format → Canvas settings → Custom, 1280 × 720**.

- **Table** visual on `SlideShortlist`: `organization`, `model`, `GPQA display`,
  `AIME display`, `Input price display`, `Output price display`. Sort by
  `slide_order`.
- Cards: `Data as of`, `Models tracked`, `Best value near the top`.
- Card: `Freshness warning`. Conditional-format the background on
  `Freshness state` — transparent at 0, amber at 1, red at 2. It shows nothing
  while the pipeline is healthy, which is the point.

### Page 2 — "Preis vs. Leistung"

The visual the slide's own argument asks for and does not have.

- **Scatter chart**: X `gpqa`, Y `output_usd_per_m`, legend `organization`,
  details `model`, size `input_usd_per_m`.
- Filter to `has_public_pricing = True`, and put `Pricing coverage label` in a
  card beside it so the omission is stated rather than hidden.
- Y axis logarithmic — prices span two orders of magnitude and a linear axis
  flattens everything cheap into the floor.
- Card: `Price spread near the top`. "Within 2 GPQA points of the leader, the
  dearest model costs N× the cheapest" is the sentence the whole slide is for.

### Page 3 — "Verlauf" (once history has accumulated)

Add a query over `data/history/*.csv` and plot `output_usd_per_m` over
`as_of_date` for a handful of models. Skip this until there are a few weeks of
snapshots; an empty chart teaches nothing.

## 6. Publish

**Home → Publish** → your workspace.

In the Service: **Semantic model → Settings → Data source credentials**
(Anonymous), then **Scheduled refresh** on, daily, an hour after the workflow's
05:15 UTC run — 07:00 UTC is a safe slot.

Run **Refresh now** once and confirm it succeeds before trusting the schedule.

---

## 7. Put it on the slide

You have Pro and only you need the live view, so the add-in path works: you see
live data signed in, and everyone else sees the snapshot.

1. In the Service, open the report → **Export → PowerPoint → Embed live data**,
   or copy the report page URL.
2. In PowerPoint: **Insert → Add-ins → Power BI**, paste the URL.
3. Size the add-in to the area slide 144's table occupies.

**Save a snapshot before you distribute the deck.** On the add-in, use
**Show as saved image** (or the ⋯ menu → *Save snapshot*). Without one, a
recipient without access sees an error panel instead of a table. With one, they
see the numbers as of your last save — which is the intended experience here.

Requires Office 2312 or newer.

### Keeping the native table as well

The add-in is a separate object; it cannot edit the existing table. Two sane
layouts:

- **Recommended.** Leave the native table on slide 144 and keep it accurate with
  `deck/update_slide.py`. Put the live add-in on a hidden slide straight after,
  and jump to it when you want to show the dashboard live. The handout stays
  correct offline; the live view is there when you want it.
- Replace the table with the add-in. Simpler, but the deck then shows an error
  panel or a stale image to anyone without workspace access.

---

## When the numbers look wrong

1. Is `Days since refresh` large? The pipeline stopped — check the Actions tab.
2. Did the last refresh workflow fail? It refuses to publish a bad parse and
   leaves the previous CSV, so a red run and a stale dashboard go together.
3. Does a single model look wrong? Check `docs/DEVIATIONS.md` before assuming a
   bug — D1 and D2 are known and deliberate.
