# Cecil data analysis with xarray-sql — tutorial

End-to-end walkthrough for querying Cecil earth-observation data with SQL via [xarray-sql](https://github.com/xarray-contrib/xarray-sql) (`xql`). This is the human-facing setup and worked example; the agent-facing condensed version lives in [`skills/cecil-data-analysis-xql/SKILL.md`](../../skills/cecil-data-analysis-xql/SKILL.md).

```
tutorials/cecil-data-analysis-xql/
├── README.md                       (this file)
├── references/
│   ├── datasets.md                 catalog pointers — read first when picking a dataset
│   ├── sdk.md                      condensed Cecil SDK reference
│   └── xarray_sql.md               XarrayContext patterns and SQL gotchas
└── scripts/
    ├── _env.py                     auto-loads .env so you don't have to
    ├── list_subscriptions.py       what's already paid for
    ├── inspect_dataset.py          variables, units, reference_table, constraints
    └── run_analysis.py             load → register → run SQL → save outputs
```

## Step 0 — Prerequisites

1. **Install Python dependencies** with `uv`:

   ```bash
   uv add cecil 'xarray-sql>=0.0.1,<0.1' matplotlib pandas tabulate
   ```

   `xarray-sql` is pre-1.0; pin to a sub-`0.1` range so `XarrayContext().from_dataset()` keeps working when the next minor lands.

2. **Create a `.env` file** in the working directory with your API key:

   ```
   CECIL_API_KEY=your-key-here
   ```

   The scripts auto-load `.env` via `scripts/_env.py` — no manual `source` needed.

3. **Verify the key works**. Open a shell with `.env` loaded and run:

   ```bash
   uv run python -c "import cecil; cecil.Client().list_datasets(); print('authenticated')"
   ```

   If this returns 401, the key is invalid or expired. Fix and re-run before proceeding.

## Step 1 — Pick a dataset

1. Call the live catalog from the SDK:

   ```python
   import cecil
   for d in cecil.Client().list_datasets():
       print(d.id, d.name, d.categories,
             d.spatial_resolution.nominal, d.temporal_coverage.nominal)
   ```

   See [`references/datasets.md`](references/datasets.md) for selection guidance — which dataset answers which question, plus the cross-cutting gotchas.

2. **See what's already paid for.** Strongly prefer existing subscriptions; they're free at the margin and the data is already provisioned:

   ```bash
   uv run python scripts/list_subscriptions.py
   ```

3. If two datasets are genuinely plausible for the question (e.g. Chloris vs Sylvera for biomass), present 2–3 candidates with one-line tradeoffs and let the user pick.

4. Once chosen, see its variables, units, and any reference tables you'll need to join:

   ```bash
   uv run python scripts/inspect_dataset.py <dataset_id>
   ```

## Step 2 — Subscription gate

**Default: read-only on existing subscriptions.** If `list_subscriptions.py` already shows the dataset, skip to Step 3.

If no matching subscription exists, **stop and confirm with the user before creating one** — subscriptions are billed. Print the exact calls you'd make (`client.create_aoi(geometry=...)` then `client.create_subscription(aoi_id=..., dataset_id=...)`) and wait for explicit confirmation.

## Step 3 — Load and register

The canonical pattern (wrapped by `scripts/run_analysis.py`):

```python
import cecil
import pandas as pd
import xarray_sql as xql

client = cecil.Client()
ds = client.load_xarray(subscription_id)              # raster
# ds = client.load_dataframe(subscription_id)         # vector (IBAT)

table_name = ...  # derived from ds.attrs["dataset_name"]
ctx = xql.XarrayContext().from_dataset(table_name, ds)

dataset = client.get_dataset(ds.attrs["dataset_id"])
for var in dataset.variables:
    if var.reference_table:
        ctx.from_pandas(pd.DataFrame(var.reference_table), f"ref_{var.name}")
```

**Critical gotcha:** `load_xarray` and `load_dataframe` take a `subscription_id`, **not** a `dataset_id`. If you get a 404, you almost certainly passed a dataset id. See [`references/sdk.md`](references/sdk.md) for the other SDK gotchas.

**Reference tables** turn integer class codes into human names. Without them, a result of "class 7 has 14921 pixels" means nothing; with them it becomes "Built area covers 14921 pixels".

## Step 4 — Write the SQL

1. **Always `DESCRIBE` first** to confirm column names. Saves a round-trip vs hallucinating them:

   ```sql
   DESCRIBE land_cover_9_class;
   ```

2. **Quote PascalCase columns** (`"Index"`, `"Name"`) from reference tables — datafusion lower-cases unquoted identifiers and you'll get *"Schema error: no field named index"*.

3. **Narrow exploratory queries** with `WHERE time = ...` or `LIMIT` — the xarray Dataset is dask-backed and `SELECT *` on a multi-year sub-meter raster pulls a lot of data.

4. **Idioms** (`ROW_NUMBER`, `LAG`, time-series aggregation) are in [`references/xarray_sql.md`](references/xarray_sql.md).

## Step 5 — Run, present, save

```bash
uv run python scripts/run_analysis.py \
    --subscription <subscription_id> \
    --sql 'SELECT DISTINCT land_cover_class FROM land_cover_9_class'
```

For vector datasets (IBAT — protected areas, KBA, species), add `--vector`:

```bash
uv run python scripts/run_analysis.py --vector \
    --subscription <subscription_id> \
    --sql 'SELECT * FROM wdpa_protected_areas LIMIT 5'
```

Outputs land in the current directory (or `--output-dir`):

- `result.csv` — raw rows
- `result.md` — markdown table + the SQL that was run
- `result.png` — chart, when the result has a plottable shape

Plus a markdown summary on stdout so the answer is visible immediately.

**Present the output using the golden rule** (the skill says the same): SQL → table (≤10 rows) → 2-3 sentence interpretation, in one compact block. No filler, no preamble.

## Worked example end to end

User: *"For our project AOI, what's the dominant land cover class in 2023 and how does it compare to 2020?"*

1. `list_subscriptions.py` shows a sub for "Impact Observatory — Land Cover 9-Class". Use it. Table name → `land_cover_9_class`.
2. `inspect_dataset.py <id>` confirms the variable is `land_cover_class` with a 9-row `reference_table`.
3. Write the SQL, run it via `run_analysis.py`, and present:

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

   Forest dominated the AOI in both years (52k pixels in 2020, 49k in 2023). The 6% drop is offset by an increase in built area, suggesting modest expansion at the edges. Chart saved to `result.png`.

That's the loop. Read references when you need them, run scripts instead of re-implementing them, gate paid actions on explicit confirmation, and present query → data → insight as one block.
