---
name: subscribe-and-load
description: Subscribe to a Cecil dataset over an Area of Interest and load the result as an xarray.Dataset (raster) or pandas.DataFrame (vector) for analysis in Python.
license: MIT
---

# Subscribe to a Cecil dataset and load it

Use this skill when the user wants to fetch a remote-sensing or geospatial dataset for an Area of Interest (AOI) from [Cecil](https://docs.cecil.earth) and analyse it in Python.

## Prerequisites

- A Cecil API key — see [docs.cecil.earth/quickstart](https://docs.cecil.earth/quickstart) to obtain one.
- `pip install cecil` — the [Cecil Python SDK](https://docs.cecil.earth/sdk).
- The key exported as `CECIL_API_KEY` in the environment.

## Steps

1. **Construct the client.** It reads `CECIL_API_KEY` lazily on the first request, so importing it is free.

   ```python
   from cecil import Client

   client = Client()
   ```

2. **Define an AOI as a GeoJSON polygon and create it.** `create_aoi` takes only `geometry` and an optional `external_ref` — there is no `name` parameter.

   ```python
   aoi = client.create_aoi(
       external_ref="my-aoi",
       geometry={
           "type": "Polygon",
           "coordinates": [[
               [-60.53, -20.81],
               [-60.53, -21.17],
               [-59.99, -21.17],
               [-59.99, -20.81],
               [-60.53, -20.81],
           ]],
       },
   )
   ```

   To reuse an existing AOI instead, look it up: `client.list_aois()` or `client.get_aoi(aoi_id)`.

3. **Pick a dataset.** Browse [docs.cecil.earth/datasets](https://docs.cecil.earth/datasets) or call `client.list_datasets()`. Note the `id` of the dataset you want.

4. **Create a subscription** for that dataset over the AOI.

   ```python
   subscription = client.create_subscription(
       aoi_id=aoi.id,
       dataset_id="<dataset-uuid>",
   )
   ```

5. **Wait for staging.** Subscriptions are processed asynchronously. While files are being staged, `load_xarray` may either raise `cecil.errors.HTTPError` or return an empty `xarray.Dataset`. Poll until variables are available, with a hard ceiling so a stuck subscription raises rather than hangs.

   ```python
   import time
   from cecil.errors import HTTPError

   for attempt in range(60):
       try:
           ds = client.load_xarray(subscription.id)
           if ds.data_vars:
               break
       except HTTPError:
           pass
       time.sleep(10)
   else:
       raise TimeoutError(f"Subscription {subscription.id} not ready after 10 min")
   ```

6. **Use the data.** `ds` is an `xarray.Dataset` backed by lazy dask arrays. Variables, dimensions, and CRS depend on the dataset.

   For vector datasets, swap step 5 for `client.load_dataframe(subscription.id)`, which returns a `pandas.DataFrame`.

## Important constraints

- `Subscription` does not expose a `status` field — readiness is determined by attempting to load.
- AOIs and subscriptions are billable resources. To clean up after exploration: `client.archive_aoi(aoi.id)` and `client.archive_subscription(subscription.id)`.
- Each dataset has its own AOI size / vertex / latitude constraints (see `Dataset.constraints`). Check before subscribing if the AOI is large or unusual.

## References

- [Cecil quickstart](https://docs.cecil.earth/quickstart)
- [SDK reference](https://docs.cecil.earth/sdk)
- [Dataset catalogue](https://docs.cecil.earth/datasets)
- Worked example: [`tutorials/quickstart.ipynb`](../../tutorials/quickstart.ipynb)
