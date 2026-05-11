# xarray-sql patterns for Cecil data

`xarray_sql.XarrayContext` is a `datafusion.SessionContext` subclass that
treats an `xarray.Dataset` as a queryable SQL table. Source:
`.venv/lib/python3.14/site-packages/xarray_sql/sql.py`.

## Setup pattern

```python
import re, cecil
import pandas as pd
import xarray_sql as xql

client = cecil.Client()
ds  = client.load_xarray(subscription_id)

# Derive table name from the dataset (e.g. "land_cover_9_class")
raw = ds.attrs.get("dataset_name", "cecil")
if "—" in raw:
    raw = raw.split("—", 1)[1]
table_name = re.sub(r"[^a-z0-9]+", "_", raw.lower().strip()).strip("_")

ctx = xql.XarrayContext().from_dataset(table_name, ds)

# Register every variable's reference_table as a sidecar SQL table
dataset = client.get_dataset(ds.attrs["dataset_id"])
for var in dataset.variables:
    if var.reference_table:
        ctx.from_pandas(pd.DataFrame(var.reference_table), f"ref_{var.name}")
```

After this you can `ctx.sql("SELECT ... FROM <table_name>")` and join to
`ref_<varname>`. Use `ctx.tables()` to inspect what's registered.

`scripts/run_analysis.py` does all of this automatically and prints the
table name in its output.

## Inspect first

Always start by checking what columns exist before writing real SQL. Column
names are not always obvious from the dataset description:

```python
ctx.sql("DESCRIBE <table_name>").to_pandas()
```

This is much faster than trial-and-error and avoids hallucinating column
names. Each Cecil xarray Dataset's coords (`x`, `y`, `time`) become SQL
columns, plus one column per data variable.

## Quoting rules

- Bareword identifiers like `land_cover_9_class`, `time`, `land_cover_class`
  work without quotes.
- Reference-table columns from the API often use **PascalCase** (e.g.
  `"Index"`, `"Name"`) — these **must** be double-quoted in SQL because
  datafusion lower-cases unquoted identifiers. The demo gets this right:

  ```sql
  JOIN ref_table ref ON r.land_cover_class = ref."Index"
  ```

  Get this wrong and you'll see `Schema error: No field named index`.

## Idioms

### Top class per timestamp (`ROW_NUMBER OVER`)

The dominant value of a categorical variable, per time slice.
Example assumes the "Impact Observatory — Land Cover 9-Class" dataset
(table `land_cover_9_class`):

```sql
SELECT r.time, r.land_cover_class, ref."Name", r.cnt
FROM (
    SELECT
        time,
        land_cover_class,
        COUNT(*) AS cnt,
        ROW_NUMBER() OVER (PARTITION BY time ORDER BY COUNT(*) DESC) AS rn
    FROM land_cover_9_class
    GROUP BY time, land_cover_class
) r
JOIN ref_land_cover_class ref ON r.land_cover_class = ref."Index"
WHERE r.rn = 1
ORDER BY r.time;
```

### Change detection (`LAG OVER`)

Where did a pixel's class change between consecutive time steps:

```sql
WITH changes AS (
    SELECT
        x, y, time,
        land_cover_class AS new_class,
        LAG(land_cover_class) OVER (PARTITION BY x, y ORDER BY time) AS prev_class,
        LAG(time)             OVER (PARTITION BY x, y ORDER BY time) AS prev_time
    FROM land_cover_9_class
)
SELECT c.x, c.y, c.prev_time, c.time AS change_time,
       old."Name" AS prev_class_name,
       new."Name" AS new_class_name
FROM changes c
JOIN ref_land_cover_class old ON c.prev_class = old."Index"
JOIN ref_land_cover_class new ON c.new_class  = new."Index"
WHERE c.new_class IS DISTINCT FROM c.prev_class
  AND c.prev_class IS NOT NULL
ORDER BY c.time, c.x, c.y;
```

### Time series aggregation

Mean of a continuous variable over the AOI per timestamp.
Example assumes a biomass dataset (table `aboveground_biomass_stock_and_change_10m`):

```sql
SELECT time, AVG(aboveground_biomass) AS mean_biomass
FROM aboveground_biomass_stock_and_change_10m
WHERE aboveground_biomass IS NOT NULL
GROUP BY time
ORDER BY time;
```

### Spatial summary at a single time

```sql
SELECT x, y, aboveground_biomass
FROM aboveground_biomass_stock_and_change_10m
WHERE time = TIMESTAMP '2023-01-01';
```

## Time filtering and the `cftime` UDF

For datasets that use **non-Gregorian** calendars (`360_day`, `julian`, etc.),
`from_dataset` automatically registers a `cftime()` scalar UDF so you can
write date strings:

```sql
SELECT * FROM <table_name> WHERE time >= cftime('2020-01-01');
```

For ordinary Gregorian time axes (the common case for Cecil rasters), use
`TIMESTAMP '...'` literals or compare against ISO strings — the auto-UDF is
not registered and won't be available.

**Caveat from the source:** only one `cftime()` UDF is registered per context,
based on the calendar of the *first* non-Gregorian coordinate seen. If you
ever register two datasets with two different non-Gregorian calendars in the
same context, the second one's filters may be wrong. Use a fresh
`XarrayContext` per calendar in that case.

## Performance notes

- The xarray Dataset is dask-backed; SQL aggregations stream through chunks,
  but `SELECT *` on a multi-year, sub-meter dataset will pull a lot of data.
  Always narrow with `WHERE time = ...` or `LIMIT` while exploring.
- `ctx.tables()` lists all registered tables — use it to confirm the table
  name if you're unsure.
- Datafusion plan inspection: `ctx.sql(query).explain()` shows the physical
  plan if a query is unexpectedly slow.
