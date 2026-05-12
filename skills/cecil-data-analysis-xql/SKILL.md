---
name: cecil-data-analysis-xql
description: Use this skill when the user asks an analysis question about Cecil earth-observation data — forest carbon, biomass, deforestation, land cover, soil moisture, biodiversity, protected areas, ecosystem integrity. The skill writes SQL with xarray-sql (xql) against the user's existing subscription and presents query → result table → plain-English interpretation as one compact block.
license: MIT
---

# Cecil data analysis with xarray-sql

Use this skill for questions like *"how has tree cover changed in my AOI?"* or *"what's the dominant land cover here?"* — anything that wants to **query** an existing Cecil subscription with SQL.

For setup, installation, and the runnable scripts that drive these queries, see [`tutorials/cecil-data-analysis-xql/`](../../tutorials/cecil-data-analysis-xql/). This SKILL.md covers only what an agent needs to know in-context.

## Related skills

- [`subscribe-and-load`](../subscribe-and-load/SKILL.md) — sets up the subscription + AOI that the queries below assume.
- [`land-cover-baseline-and-change`](../land-cover-baseline-and-change/SKILL.md) — the hand-written numpy/xarray counterpart for readers who want to skip the SQL layer.

## When this skill is in scope

**Yes:** dominant-class, time-series, change-detection, area, or overlap questions on Cecil rasters (biomass, LULC, soil moisture, BII, FLII) or vector datasets (IBAT family — protected areas, KBA, species ranges).

**No:** weather forecasts, atmospheric chemistry / GHGs, ocean / marine data, generic Python help, anything without a spatial AOI. Cecil doesn't carry that data — say so plainly and stop. Don't force-fit a dataset.

## Subscription gate (the rule that protects the wallet)

**Default: read-only on existing subscriptions.** Run `scripts/list_subscriptions.py` first. If a subscription for the chosen dataset already exists, go straight to the SQL.

If no matching subscription exists:

1. Summarise what you'd subscribe to: dataset name, provider, coverage, relevant variables.
2. Show the exact calls you'd make: `client.create_aoi(geometry=...)` (if no AOI) and `client.create_subscription(aoi_id=..., dataset_id=...)`.
3. **Stop and ask the user to confirm** before calling either method. Subscriptions are billed. Get explicit confirmation for *this* dataset *now*, even if the user agreed to a different one earlier in the conversation.

If the user declines, say so and stop. Don't try to find a free substitute that might silently answer a different question.

## Golden rule: query → table → insight

Whenever this skill is in scope, present every analysis as one compact block, in this order:

1. **SQL** — fenced `sql` block. Applies at every stage: `DESCRIBE`, exploratory queries, final analysis.
2. **Result table** — Markdown, **capped at 10 rows**. If longer, end with *"… N more in result.csv"*. Never dump 200 rows inline.
3. **Interpretation** — two or three sentences of plain-English insight. No header, no "here are the results:" preamble.

For exploratory queries with nothing to interpret (`DESCRIBE`, etc.), just show 1 + 2.

## Table naming

The xarray Dataset is registered under a name derived from the dataset (provider prefix stripped, slugified):

| Dataset name | Table name |
|---|---|
| Impact Observatory — Land Cover 9-Class | `land_cover_9_class` |
| Chloris — Aboveground Biomass Stock and Change 10m | `aboveground_biomass_stock_and_change_10m` |
| Lobelia Earth — Surface Soil Moisture 30m | `surface_soil_moisture_30m` |

Use the same name in your SQL (`FROM land_cover_9_class`, not `FROM cecil`). `scripts/run_analysis.py` does the derivation automatically and prints the table name.

## SQL idioms

**Always start with `DESCRIBE`** to confirm column names before writing real SQL:

```sql
DESCRIBE land_cover_9_class;
```

**Top class per timestamp** — `ROW_NUMBER OVER`:

```sql
SELECT time, ref."Name", cnt
FROM (
  SELECT time, land_cover_class, COUNT(*) AS cnt,
    ROW_NUMBER() OVER (PARTITION BY time ORDER BY COUNT(*) DESC) AS rn
  FROM land_cover_9_class
  GROUP BY time, land_cover_class
) r
JOIN ref_land_cover_class ref ON r.land_cover_class = ref."Index"
WHERE rn = 1
ORDER BY time;
```

**Change detection** — `LAG OVER` per pixel:

```sql
SELECT x, y, time,
  land_cover_class AS new_class,
  LAG(land_cover_class) OVER (PARTITION BY x, y ORDER BY time) AS prev_class
FROM land_cover_9_class;
```

Filter with `WHERE prev_class IS DISTINCT FROM new_class AND prev_class IS NOT NULL` to keep only changed pixels.

**Time-series aggregation** — plain `GROUP BY time`:

```sql
SELECT time, AVG(aboveground_biomass) AS mean_biomass
FROM aboveground_biomass_stock_and_change_10m
WHERE aboveground_biomass IS NOT NULL
GROUP BY time
ORDER BY time;
```

## Quoting rule (datafusion gotcha)

Reference-table columns from the API are **PascalCase** (`"Index"`, `"Name"`). **Double-quote them in SQL** — datafusion lower-cases unquoted identifiers and you'll see *"Schema error: no field named index"*. Get this right and joins work.

## Vector vs raster datasets

Most Cecil datasets are raster (`load_xarray`). The **IBAT family** (IUCN Red List, KBA, WDPA, STAR) is vector — use `load_dataframe`. `run_analysis.py` accepts `--vector` for these:

```bash
uv run python scripts/run_analysis.py --vector \
  --subscription <id> --sql 'SELECT * FROM wdpa_protected_areas LIMIT 5'
```

The full SDK gotchas (auth, `subscription_id` vs `dataset_id`, AOI geometry rules) live in [`tutorials/cecil-data-analysis-xql/references/sdk.md`](../../tutorials/cecil-data-analysis-xql/references/sdk.md).

## Failure modes — say so plainly

- **No subscriptions and no clear dataset match** → say what you looked for, list candidates, stop.
- **SQL fails twice with the same error** → stop and show the user. Often the fix is the `DESCRIBE` you skipped.
- **Question isn't really about Cecil data** → decline. Better than silently producing a confident-sounding irrelevant answer.

For the full worked end-to-end example (dominant land cover 2020 vs 2023 with chart), see the tutorial.
