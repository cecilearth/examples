---
name: screen-portfolio
description: Subscribe a chosen Cecil dataset to a portfolio of plots in one batch and return a tidy table mapping each input to its AOI id and subscription id. The foundation for any multi-site analysis (TNFD, CSRD, EUDR, supply chain).
license: MIT
---

# Screen a portfolio of AOIs

Use this skill when the user has more than one site/plot/property and wants the same dataset subscribed against all of them. Most regulatory and supply-chain workflows start here.

## Prerequisites

- [`subscribe-and-load`](../subscribe-and-load/SKILL.md) — this skill applies it across many AOIs.

## Steps

1. **Inputs.** A list of plots, each with:
   - `plot_id` — a stable identifier (supplier code, asset id, etc.).
   - `geometry` — GeoJSON Polygon or Point.

   Plus a single `dataset_id` (the dataset to subscribe to all plots).

2. **Look up existing AOIs to keep runs idempotent.** Re-running a screen shouldn't create duplicate AOIs. Use `external_ref=plot_id`.

   ```python
   existing = {a.external_ref: a for a in client.list_aois() if a.external_ref}
   ```

3. **Create AOIs and subscriptions per plot.**

   ```python
   records = []
   for plot in plots:
       aoi = existing.get(plot["plot_id"]) or client.create_aoi(
           geometry=plot["geometry"],
           external_ref=plot["plot_id"],
       )
       subscription = client.create_subscription(
           aoi_id=aoi.id,
           dataset_id=dataset_id,
           external_ref=plot["plot_id"],
       )
       records.append({
           "plot_id": plot["plot_id"],
           "aoi_id": aoi.id,
           "aoi_hectares": aoi.hectares,
           "subscription_id": subscription.id,
       })
   ```

4. **Wait for staging.** Subscriptions process asynchronously. Poll each one (or all of them in parallel) using the `subscribe-and-load` polling pattern. For large portfolios, fan out with `concurrent.futures.ThreadPoolExecutor` so plots stage in parallel.

5. **Return the result table** as a `pandas.DataFrame`. Downstream skills (`deforestation-risk-screen`, `land-cover-baseline-and-change`, `priority-biome-overlap`, `eudr-due-diligence`) take this table as input.

## Important constraints

- **Dataset constraints.** Some datasets enforce min/max AOI hectares or vertex counts — see `client.get_dataset(dataset_id).constraints`. Validate inputs against these before bulk-creating subscriptions, otherwise individual plots will fail mid-batch.
- **Cost.** Every subscription is potentially billable. Check `client.get_dataset(dataset_id).pricing` before running across a large portfolio.
- **Cleanup.** For exploratory runs, archive aggressively: `client.archive_subscription(s.id)` and `client.archive_aoi(a.id)`.

## References

- [`subscribe-and-load`](../subscribe-and-load/SKILL.md)
- [Cecil SDK reference](https://docs.cecil.earth/sdk)
- [Dataset catalogue](https://docs.cecil.earth/datasets)
