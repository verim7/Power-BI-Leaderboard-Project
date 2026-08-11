# Building the .pbix

Power BI Desktop is Windows-only and cannot be scripted from this repository,
so the model is assembled once by hand from the queries and measures here.
Budget about an hour the first time.

Everything below assumes the refresh workflow is already publishing
`data/leaderboard_latest.csv`.

---

## 0. Decide how Power BI reaches the CSV — do this first

`verim7/Power-BI-Leaderboard-Project` is **private**, so
`raw.githubusercontent.com` will not serve the file anonymously. Two ways out,
and the choice changes step 2.

### A. Publish the data publicly (recommended)

The CSV holds nothing confidential: it is public benchmark and pricing data
scraped from a public website. The *deck* is the confidential asset, and it is
not in this repository.

Either make this repository public — after confirming no Synpulse material has
been committed — or push `data/` to a small public companion repo from the same
workflow.

Then in `Leaderboard.m` set `UseGitHubApi = false`.

- no token, no rotation, no secret in the .pbix
- scheduled refresh in the Service works with **Anonymous** auth and no gateway
- anyone with the URL can read the CSV, which for this data is fine

### B. Keep everything private, authenticate with a PAT

Create a **fine-grained** personal access token: this repository only,
*Contents: Read-only*, with an expiry you will actually diarise.

In `Leaderboard.m` keep `UseGitHubApi = true` and put the token in the
`GitHubToken` parameter.

- the repository stays private
- the token is stored in the .pbix and in the Service's data source credentials,
  so anyone you send the file to inherits read access to the repo
- it expires, and refresh fails when it does

Option A is less to get wrong. Option B is defensible if the repository will
ever hold anything sensitive.

---

## 1. Create the file

Power BI Desktop → **Blank report** → save as `powerbi/AI-Leaderboard.pbix`.

Do not commit the .pbix if you chose option B — it contains the token.

## 2. Add the Leaderboard query

**Home → Transform data → New Source → Blank Query**, then **Advanced Editor**,
and paste the whole of `powerbi/queries/Leaderboard.m`. Name the query
`Leaderboard`.

Edit the configuration block at the top: `Branch` should be `main` once this
work is merged, and set `UseGitHubApi` per step 0.

When prompted for credentials choose **Anonymous** — under option B the token
travels in the header, not in Power BI's credential store.

Check in the preview:
- `gpqa` and the price columns are **Decimal Number**, and blanks are blanks
- `as_of_date` is **Date**
- `is_open_source` is **True/False**

## 3. Add the shortlist query

Another blank query, paste `powerbi/queries/SlideShortlist.m`, name it
`SlideShortlist`. It references `Leaderboard`, so create it second.

**Close & Apply.**

## 4. Add the measures

**Modeling → New measure**, once per measure in
`powerbi/measures/measures.dax`. Paste the whole block including its comment —
the comments explain the intent and cost nothing.

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
