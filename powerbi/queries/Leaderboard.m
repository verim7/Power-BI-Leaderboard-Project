// Leaderboard - the fact table behind every visual.
//
// Reads data/leaderboard_latest.csv, which the GitHub Action refreshes daily.
// Paste into Power BI Desktop: Home > Transform data > New Source > Blank Query
// > Advanced Editor, then replace the contents with this.
//
// TWO SOURCE MODES, because the repository is currently private:
//
//   UseGitHubApi = false  ->  raw.githubusercontent.com, anonymous.
//                             Requires the repo (or a data-only repo) to be
//                             PUBLIC. Simplest by far: no token, no rotation,
//                             and scheduled refresh in the Service just works.
//
//   UseGitHubApi = true   ->  GitHub Contents API with a fine-grained PAT.
//                             Keeps the repo private, at the cost of a secret
//                             living in the .pbix and needing rotation.
//
// The base URL is a literal and the path is passed via RelativePath on purpose.
// Power BI refuses to schedule refresh for a "dynamic data source" - one whose
// URL is assembled by string concatenation - and this is the documented shape
// that stays static enough to pass that check.

let
    // ---- configuration -------------------------------------------------
    // Prefer defining these as Power BI parameters (Home > Manage parameters)
    // so they can be changed without editing M. Defaults are inline so the
    // query works when pasted as-is.
    Owner        = "verim7",
    Repo         = "Power-BI-Leaderboard-Project",
    Branch       = "main",
    FilePath     = "data/leaderboard_latest.csv",
    UseGitHubApi = true,
    // Fine-grained PAT, read-only, Contents: Read for this repo only.
    // Leave empty when UseGitHubApi = false.
    GitHubToken  = "",

    // ---- fetch -----------------------------------------------------------
    RawBinary =
        if UseGitHubApi then
            Web.Contents(
                "https://api.github.com",
                [
                    RelativePath = "repos/" & Owner & "/" & Repo & "/contents/" & FilePath,
                    Query        = [ ref = Branch ],
                    Headers      = [
                        #"Accept"               = "application/vnd.github.raw",
                        #"Authorization"        = "Bearer " & GitHubToken,
                        #"X-GitHub-Api-Version" = "2022-11-28"
                    ]
                ]
            )
        else
            Web.Contents(
                "https://raw.githubusercontent.com",
                [ RelativePath = Owner & "/" & Repo & "/" & Branch & "/" & FilePath ]
            ),

    Csv = Csv.Document(
        RawBinary,
        [ Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv ]
    ),
    Promoted = Table.PromoteHeaders(Csv, [PromoteAllScalars = true]),

    // ---- typing ----------------------------------------------------------
    // Prices and scores stay nullable. A model llm-stats no longer prices must
    // read as blank and print as "n/a" - exactly what the slide already does
    // for Grok-4 Heavy - never as a confident 0.00.
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"organization",     type text},
            {"model",            type text},
            {"gpqa",             type number},
            {"aime_2025",        type number},
            {"input_usd_per_m",  type number},
            {"output_usd_per_m", type number},
            {"context_window",   Int64.Type},
            {"license",          type text},
            {"as_of_date",       type date},
            {"source_url",       type text}
        }
    ),

    // "True"/"False" out of Python's csv writer, plus blanks.
    OpenSource = Table.TransformColumns(
        Typed,
        {{"is_open_source", each
            if _ = null or _ = "" then null else Text.Lower(Text.From(_)) = "true",
            type nullable logical}}
    ),

    // ---- derived -----------------------------------------------------------
    // Cost per GPQA point is the slide's argument made arithmetic: what a unit
    // of measured capability costs. Computed here rather than as a measure so
    // it can be used on an axis.
    WithCostPerPoint = Table.AddColumn(
        OpenSource,
        "output_usd_per_gpqa_point",
        each if [output_usd_per_m] = null or [gpqa] = null or [gpqa] = 0
             then null
             else Number.Round([output_usd_per_m] / [gpqa], 4),
        type nullable number
    ),

    WithPricing = Table.AddColumn(
        WithCostPerPoint,
        "has_public_pricing",
        each [input_usd_per_m] <> null or [output_usd_per_m] <> null,
        type logical
    ),

    Sorted = Table.Sort(WithPricing, {{"gpqa", Order.Descending}})
in
    Sorted
