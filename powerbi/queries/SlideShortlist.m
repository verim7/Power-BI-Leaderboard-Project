// SlideShortlist - the eight rows slide 144 prints, in slide order.
//
// A separate query rather than a visual-level filter: the shortlist is an
// editorial decision about the deck, and keeping it as data means the slide
// and the PowerPoint updater agree on one list instead of two.
//
// Edit ShortlistNames to change what the slide shows. Names must match the
// `model` column exactly; a name that no longer exists upstream is reported
// by the Missing column rather than silently vanishing from the table.

let
    ShortlistNames = {
        "Gemini 3 Pro",
        "Grok-4 Heavy",
        "GPT-5.1",
        "GPT-5.1 Instant",
        "GPT-5.1 Think.",
        "Grok-4",
        "Claude Opus 4.5",
        "Gemini 2.5 Pro"
    },

    Ranked = Table.FromList(
        ShortlistNames,
        Splitter.SplitByNothing(),
        {"model"},
        null,
        ExtraValues.Error
    ),
    WithOrder = Table.AddIndexColumn(Ranked, "slide_order", 1, 1, Int64.Type),

    Joined = Table.NestedJoin(
        WithOrder, {"model"}, Leaderboard, {"model"}, "match", JoinKind.LeftOuter
    ),
    Missing = Table.AddColumn(
        Joined, "missing_upstream", each Table.IsEmpty([match]), type logical
    ),
    Expanded = Table.ExpandTableColumn(
        Missing,
        "match",
        {"organization", "gpqa", "aime_2025", "input_usd_per_m", "output_usd_per_m",
         "license", "is_open_source", "as_of_date", "output_usd_per_gpqa_point"}
    ),
    Sorted = Table.Sort(Expanded, {{"slide_order", Order.Ascending}})
in
    Sorted
