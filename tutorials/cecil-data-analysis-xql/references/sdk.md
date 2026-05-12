# Cecil Python SDK gotchas

The Cecil SDK has **no docstrings** — every method's `__doc__` is `None`.
So:

- **Signatures**: `inspect.signature(client.method_name)` — discoverable live.
- **Method list**: `dir(client)` — covers subscriptions, AOIs, datasets,
  settings, webhooks.

This file only documents the things `inspect.signature` and `list_datasets`
/ `get_dataset` *can't* tell you — the gotchas you'll trip over.

## Auth

```python
import os, cecil
os.environ["CECIL_API_KEY"] = "..."   # required
client = cecil.Client()
```

There is **no constructor argument for the API key** — env-var only. The
Client raises `SDKError("Environment variable CECIL_API_KEY not set")` if
the variable is missing.

## Loading data

```python
ds = client.load_xarray(subscription_id)      # raster datasets
df = client.load_dataframe(subscription_id)   # vector datasets (IBAT)
```

**Critical gotcha:** these take a **`subscription_id`**, *not* a
`dataset_id`. If you get a 404 from either method, you almost certainly
passed a dataset id by mistake.

- Use `load_xarray` for **raster** datasets — the vast majority (biomass,
  LULC, soil moisture, BII, FLII, etc.).
- Use `load_dataframe` for **vector** datasets — currently the IBAT
  family (IUCN Red List, KBA, WDPA, STAR).

The returned xarray Dataset has dims `(time, y, x)` and attrs
`provider_name`, `dataset_name`, `dataset_id`, `aoi_id`, `subscription_id`.
Backing arrays are lazy dask arrays.

## AOIs

```python
client.create_aoi(geometry={...}, external_ref=None)
```

`geometry` must be **GeoJSON `Polygon` or `MultiPolygon` in EPSG:4326**.
Subject to each dataset's `Constraints.aoi_min_hectares` /
`aoi_max_hectares` / `aoi_geometry_types` / `aoi_max_vertices` — read
those from `client.get_dataset(...).constraints` before creating the AOI.

## Datasets and reference tables

```python
ds = client.get_dataset(dataset_id)
for var in ds.variables:
    if var.reference_table:        # list[dict], may be empty
        ...
```

`reference_table` is the lookup that turns integer class codes (e.g. an
Impact Observatory Land Cover code of `7`) into human names (e.g.
`"Built area"`). When non-empty, register it as a sidecar pandas table
and JOIN to it in SQL — see `xarray_sql.md`.

`Subscription` objects carry `id, dataset_id, aoi_id, external_ref,
status, timestamps` — they do **not** include the dataset's variables.
Follow up with `client.get_dataset(sub.dataset_id)` if you need the schema.

## What's deliberately not covered

Webhooks, user/org management, and `_load_xarray_v2` (an internal
preview) aren't used by this skill. Read `client.py` directly if you
need them.
