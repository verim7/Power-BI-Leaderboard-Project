# Deviations from slide 144

Every figure in `scraper/schema.py::SLIDE_REFERENCE` was read off slide 144 of
the training deck ("As of december 2025"). The scraper compares against them on
every run, because a wholesale mismatch is the clearest signal that llm-stats
moved a field and the parser is now reading the wrong column.

Individual figures do legitimately change. When one does, it gets an id here and
an entry in `KNOWN_DIVERGENCES`, and stops counting as an unexplained mismatch.
**Adding an entry is a claim that the new number is right and the slide is not.**
Do not add one to silence a failure you have not explained.

---

## D1 — the slide's "Gemini 2.5 Pro" row is two different models

*Slide:* Gemini 2.5 Pro, GPQA 86.4 %, AIME 88.0 %, $1.25 in / $10.00 out.

*Upstream:* llm-stats carries two records under that family.

| model_id | name | GPQA | AIME 2025 | in $/M | out $/M |
|---|---|---|---|---|---|
| `gemini-2.5-pro-preview-06-05` | Gemini 2.5 Pro Preview 06-05 | 86.4 | 88.0 | — | — |
| `gemini-2.5-pro` | Gemini 2.5 Pro | 83.0 | 83.0 | 1.25 | 10.00 |

The slide's **scores** come from the preview build; its **prices** come from the
GA model. Neither model has both. The row as printed describes something that
does not exist.

*Here:* the pipeline resolves the name `Gemini 2.5 Pro` to the GA record and
reports 83.0 / 83.0 / 1.25 / 10.00 — one model, consistently.

*Consequence for the deck:* the Gemini 2.5 Pro row will change when the slide is
regenerated. That is a correction, not a regression. If the preview build is
what you meant to show, add `Gemini 2.5 Pro Preview 06-05` to the shortlist in
`deck/config.yaml` and it will be printed under its real name.

---

## D2 — pricing withdrawn upstream for three slide models

*Slide:* Gemini 3 Pro $2.00/$12.00, Grok-4 $3.00/$15.00, Claude Opus 4.5
$5.00/$25.00.

*Upstream:* `input_price` and `output_price` are now null on all three. Only 87
of 340 records carry a price at all — llm-stats appears to drop pricing once a
model stops being generally served, which by August 2026 these have.

*Here:* null, rendered `n/a`. The slide already prints `n/a` for Grok-4 Heavy,
so the treatment is consistent with the original design.

The same applies to `GPT-5.1 Thinking` — printed on the slide as "GPT-5.1
Think." with $1.25/$10.00, now unpriced upstream. It is not in the parity
reference set, so it does not show up in the parity count.

A withdrawn price must never render as `0.00`: a free model and an unpriced one
are opposite claims, and on a slide arguing that price drives model selection,
that particular lie would be the expensive one.

---

## Not a deviation: the field has moved on

The December 2025 top eight are no longer the top eight. As of the first live
run the leader is 94.6 % GPQA against the slide's 91.9 %, and models that did
not exist in December (Claude Opus 4.6/4.7/4.8, GPT-5.4 through 5.6, Gemini 3.1
Pro, Grok 4.5, Kimi K3) sit above most of the slide's rows.

This is the pipeline working, not drift to be corrected. Decide deliberately
whether slide 144 should keep showing its historical eight (edit the shortlist
in `deck/config.yaml`) or track the current top eight (set `mode: top_n`).
