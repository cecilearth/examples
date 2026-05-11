---
name: cecil-data-analysis-xql
description: Use whenever the user asks an analysis question about earth-observation, geospatial, or environmental data — forest carbon, aboveground biomass, deforestation, land cover or land use, crop type, soil moisture, protected areas, key biodiversity areas, threatened species, biodiversity intactness, ecosystem integrity, forest landscape integrity. Even if the user does not say "Cecil", if the question is "for my AOI, how has X changed over time" or "what's the dominant Y in this area", this is the skill. It matches the question to a Cecil dataset, loads it via the Cecil SDK, writes SQL with xarray-sql (xql), and returns the SQL, a result table, a chart, and a written summary.
license: MIT
---

# Cecil data analysis with xarray-sql

Ask earth-observation questions in plain English. This skill picks a Cecil
dataset, loads it via the Cecil SDK, writes SQL with
[xarray-sql](https://github.com/xarray-contrib/xarray-sql) (`xql`), and
returns the query, a result table, a chart, and a written summary.

## Why xql

- **SQL beats pandas chains** for joining categorical reference tables —
  no integer class codes leaking into the user-visible answer.
- **Windows like `ROW_NUMBER OVER` / `LAG OVER`** make dominant-class and
  pixel-level change-detection queries one-liners.
- **DataFusion streams over the dask-backed xarray Dataset** the Cecil SDK
  already hands you — no rematerialisation, no second copy of the data.

A taste — pixel counts per land-cover class per year, with class names
joined in from the reference table:

```sql
SELECT date_part('year', time) AS year, ref."Name" AS class, COUNT(*) AS px
FROM land_cover_9_class
JOIN ref_land_cover_class ref ON land_cover_class = ref."Index"
GROUP BY 1, 2
ORDER BY 1, 3 DESC;
```

See *One worked example end to end* at the bottom for a full dominant-class
+ year-over-year-change loop.

## Related skills in this repo

- [`subscribe-and-load`](../subscribe-and-load/SKILL.md) — prerequisite;
  sets up the subscription and AOI that `load_xarray` expects.
- [`land-cover-baseline-and-change`](../land-cover-baseline-and-change/SKILL.md) —
  the hand-written numpy/xarray counterpart to the SQL approach here.
  Useful for readers who want to see the same answer without a SQL layer.

## When this skill is in scope

**Yes, use it for:**
- "How has tree cover / biomass / land use changed in my AOI since YEAR?"
- "What's the dominant land cover class for this site?"
- "Show me deforestation hotspots in <region> over the last N years."
- "What threatened species ranges intersect this AOI?"
- "How wet was the soil in <field> during planting last spring?"
- "Is this AOI inside a protected area or a Key Biodiversity Area?"
- "Compare biomass between two pilot sites."
- Anything involving categorical land-cover codes, forest carbon, soil
  moisture, biodiversity layers, or ecosystem integrity at a specific AOI.

**No, don't use it for:**
- Weather *forecasts* (Cecil is monitoring/observation, not forecasting).
- Atmospheric chemistry, GHG concentrations, air quality.
- Marine / ocean data.
- Anything with no spatial AOI at all (e.g. "what's the global GDP of X").
- Generic Python / pandas help that has nothing to do with Cecil data.

If you're unsure, scan `references/datasets.md` first — if no dataset there
plausibly answers the question, say so plainly and stop. Don't force-fit a
dataset that won't actually answer what was asked.

## Golden rule: always show query and results

Whenever this skill is in scope, **always show the SQL and the result
table** together as one compact block. The user should never have to ask
"what query did you run?" or "what did the data actually say?" Present
them in this order — query, data, insight — with no filler in between:

1. **SQL** — fenced `sql` block. Applies at every stage: `DESCRIBE`,
   exploratory queries, final analysis, follow-ups.
2. **Result table** — Markdown table, **capped at 10 rows**. If there are
   more rows, end with a one-line note like *"… 184 more rows in
   result.csv"*. Never dump a 200-row table inline.
3. **Interpretation** — two or three sentences of plain-English insight
   right after the table. No separate header needed.

Keep all three tight — no extra headings, no blank-line padding, no
"here are the results:" preamble. A single scroll should show the full
picture. For exploratory queries (like `DESCRIBE`) where there's nothing
to interpret, just show 1 + 2.

## How the skill is laid out

```
cecil-data-analysis-xql/
├── SKILL.md                       (this file)
├── references/
│   ├── datasets.md                catalog pointers — read first when picking a dataset
│   ├── sdk.md                     condensed Cecil SDK reference
│   └── xarray_sql.md              XarrayContext patterns and SQL gotchas
└── scripts/
    ├── list_subscriptions.py      what's already paid for
    ├── inspect_dataset.py         variables, units, reference_table, constraints
    └── run_analysis.py            load → register → run SQL → save outputs
```

Read reference files only when you actually need them — they exist so this
SKILL.md can stay short.

## Step 0 — Check prerequisites (always run this first)

Before running any script, verify the environment is ready. Skipping this
leads to confusing import errors and wasted turns.

**Important:** each Bash tool call runs in a fresh shell — environment
variables from a previous call do not carry over. The skill scripts
auto-load `.env` from the working directory (via `scripts/_env.py`), so
the user only needs a `.env` file with `CECIL_API_KEY=...` in it. For
the one-liner checks below, inline `source .env` in the same command.

1. **Check Python dependencies are installed:**

   ```bash
   uv run python -c "import cecil, xarray_sql, pandas, matplotlib, tabulate; print('ok')"
   ```

   If that fails, try the local venv:

   ```bash
   .venv/bin/python -c "import cecil, xarray_sql, pandas, matplotlib, tabulate; print('ok')"
   ```

   If any import fails, install with `uv`:

   ```bash
   uv add cecil xarray-sql matplotlib pandas tabulate
   ```

   Do not proceed until imports succeed.

2. **Check `CECIL_API_KEY` is available:**

   The scripts auto-load `.env`, so just confirm the file exists:

   ```bash
   test -f .env && grep -q CECIL_API_KEY .env && echo "ok" || echo "MISSING"
   ```

   If missing, tell the user to create a `.env` file:

   ```
   CECIL_API_KEY=your-key-here
   ```

3. **Verify the key works (source .env inline):**

   ```bash
   set -a && source .env && set +a && uv run python -c "import cecil; cecil.Client().list_datasets(); print('authenticated')"
   ```

   If this returns 401, the key is invalid or expired. Tell the user and
   stop.

Only proceed to Step 1 once all three checks pass.

## Step 1 — Pick a dataset

1. Call `cecil.Client().list_datasets()` for the live catalog. Each
   `Dataset` carries the full schema (`name`, `categories`, `variables`,
   `spatial_resolution`, `temporal_coverage`, `pricing`, `constraints`).
   `references/datasets.md` adds *selection guidance* (which dataset for
   which question) and the cross-cutting gotchas — read it after you've
   seen the live list to narrow the candidate set.
2. Run `scripts/list_subscriptions.py` to see what the user is already
   paying for. **Strongly prefer datasets in this list** — they're free at
   the margin and the data is already provisioned.
3. If the question is genuinely vague between two datasets (e.g. Chloris vs
   Sylvera for biomass), present 2–3 candidates with one-line trade-offs and
   ask the user to pick. Don't guess silently.
4. Once a dataset is chosen, run `scripts/inspect_dataset.py <dataset_id>`
   to see its variables, units, and any `reference_table` you'll need to
   join in SQL.

Why this order: dataset selection is the highest-leverage decision in the
workflow. Picking the wrong dataset wastes the rest of the turn and can
suggest a paid subscription the user doesn't need.

## Step 2 — Subscription gate (the rule that protects the wallet)

**Default: read-only on existing subscriptions.** If `list_subscriptions.py`
shows a sub for the chosen dataset, proceed straight to Step 3.

If no matching subscription exists:

1. Print a short summary: dataset name, provider, spatial/temporal coverage,
   relevant variables, and the dataset's pricing tier (from
   `inspect_dataset.py`).
2. Print what you would do: `client.create_subscription(aoi_id=..., dataset_id=...)`,
   and `client.create_aoi(geometry=...)` first if no AOI exists.
3. **Stop and ask the user to confirm** before calling either method.
   Subscriptions are billed; do not create them on your own initiative even
   if the user said "go ahead" earlier in the conversation about something
   else. Get explicit confirmation for *this* dataset *now*.

If the user declines, say so and stop — don't try to find a free
substitute that might silently answer a different question.

## Step 3 — Load + register

The canonical pattern (wrapped by `scripts/run_analysis.py`):

```python
import cecil, pandas as pd, xarray_sql as xql

client = cecil.Client()
ds  = client.load_xarray(SUBSCRIPTION_ID)        # NB: subscription_id, not dataset_id
table_name = ...  # derived from ds.attrs["dataset_name"], see below
ctx = xql.XarrayContext().from_dataset(table_name, ds)

dataset = client.get_dataset(ds.attrs["dataset_id"])
for var in dataset.variables:
    if var.reference_table:
        ctx.from_pandas(pd.DataFrame(var.reference_table), f"ref_{var.name}")
```

**Table naming convention:** the main table is named after the dataset, not
a generic `"cecil"`. `run_analysis.py` derives the name automatically by
stripping the provider prefix (everything before "—") and slugifying the
rest:

| Dataset name | Table name |
|---|---|
| Impact Observatory — Land Cover 9-Class | `land_cover_9_class` |
| Chloris — Aboveground Biomass Stock and Change 10m | `aboveground_biomass_stock_and_change_10m` |
| Lobelia Earth — Surface Soil Moisture 30m | `surface_soil_moisture_30m` |

Use the same name in your SQL (`FROM land_cover_9_class`, not `FROM cecil`).
If you need a custom name, pass `--table-name` to override.

You almost never need to write this by hand. `scripts/run_analysis.py`
encapsulates exactly this and adds output handling — call it instead:

```bash
uv run python scripts/run_analysis.py \
    --subscription <subscription_id> \
    --sql 'SELECT DISTINCT land_cover_class FROM land_cover_9_class'
```

Why register reference tables: raw values for categorical variables
(`land_cover_class`, etc.) are integer codes that mean nothing without the
lookup. Joining `ref_<varname>."Name"` is what turns a result of "class 7
has 14921 pixels" into "Built area covers 14921 pixels".

**Common gotcha:** `load_xarray` and `load_dataframe` take a
`subscription_id`, not a `dataset_id`. See `references/sdk.md` for that
and the other SDK gotchas.

## Step 4 — Write the SQL

1. If you don't already know the columns, run `DESCRIBE <table>` first
   (e.g. `DESCRIBE land_cover_9_class`). This is one round-trip and saves
   you from hallucinating column names.
2. Build the query using the idioms in `references/xarray_sql.md`:
   - `LAG(...) OVER (PARTITION BY x, y ORDER BY time)` for change detection.
   - `ROW_NUMBER() OVER (PARTITION BY time ORDER BY COUNT(*) DESC)` for top-N
     per group.
   - Plain `GROUP BY time` for time-series aggregations.
3. **Quote `"Name"` and `"Index"` columns from reference tables in double
   quotes** — they're PascalCase and datafusion lower-cases unquoted
   identifiers. Get this wrong and you'll see "no field named index".
4. Narrow with `WHERE time = ...` or `LIMIT` while exploring — the dataset
   is dask-backed and `SELECT *` on a multi-year, sub-meter raster will pull
   a lot of data.
5. **Show every query to the user** — even a `DESCRIBE` — in a fenced
   `sql` block. After it runs, show the result table too. (See *Golden
   rule* above.)

## Step 5 — Run, present, and save

Run the SQL through `scripts/run_analysis.py`. It saves `result.csv`,
`result.md`, and (when plottable) `result.png`, and prints a Markdown
summary on stdout.

Present the output using the golden-rule format:

```
<sql block>          ← the query you ran
<markdown table>     ← first 10 rows; "… N more in result.csv" if longer
<interpretation>     ← 2-3 sentences translating the numbers into insight
```

Example of what the user should see after a run:

> ```sql
> SELECT year, ref."Name" AS class, px
> FROM yearly JOIN ref_land_cover_class ref ON …  -- table: land_cover_9_class
> ```
>
> | year | class      |    px |
> |------|------------|------:|
> | 2020 | Forest     | 52014 |
> | 2023 | Forest     | 48831 |
>
> Forest dominated in both years but dropped 6% — most loss is in the
> southeast quadrant, consistent with built-area expansion at the edges.

Don't add filler between these three pieces. If there's a chart, mention
the saved path after the interpretation. If the answer is a single scalar,
skip the table — the interpretation alone is fine.

## Failure modes — say so plainly

- **`CECIL_API_KEY` not set** → tell the user to set it; do not invent a
  fallback.
- **No subscriptions and no obvious dataset match** → say what you looked
  for and stop.
- **The SQL fails twice in a row with the same error class** → stop and
  show the user the error rather than churning through random rewrites.
  Often the fix is a `DESCRIBE` round-trip you skipped in Step 4.
- **Question isn't really about Cecil data** → say so and decline. The
  worst outcome is silently producing a confident-sounding but irrelevant
  analysis.

## One worked example end to end

User: *"For our project AOI, what's the dominant land cover class in 2023
and how does it compare to 2020?"*

1. `list_subscriptions.py` shows a sub for "Impact Observatory — Land Cover
   9-Class". Use it. Table name → `land_cover_9_class`.
2. `inspect_dataset.py` confirms the variable is `land_cover_class` with a
   `reference_table` of nine classes.
3. Write the SQL, run it via `run_analysis.py`, and present the
   golden-rule block:

   ```sql
   WITH yearly AS (
     SELECT
       date_part('year', time) AS year,
       land_cover_class,
       COUNT(*) AS px,
       ROW_NUMBER() OVER (
         PARTITION BY date_part('year', time)
         ORDER BY COUNT(*) DESC
       ) AS rn
     FROM land_cover_9_class
     WHERE date_part('year', time) IN (2020, 2023)
     GROUP BY 1, 2
   )
   SELECT y.year, ref."Name" AS dominant_class, y.px
   FROM yearly y
   JOIN ref_land_cover_class ref ON y.land_cover_class = ref."Index"
   WHERE y.rn = 1
   ORDER BY y.year;
   ```

   | year | dominant_class |    px |
   |------|----------------|------:|
   | 2020 | Forest         | 52014 |
   | 2023 | Forest         | 48831 |

   Forest dominated the AOI in both years (52k pixels in 2020, 49k in
   2023). The 6% drop is offset by an increase in built area, suggesting
   modest expansion at the edges. Chart saved to `result.png`.

That's the loop. Read references when you need them, run scripts instead of
re-implementing them, gate paid actions on explicit confirmation, and
present query → data → insight as one block.
