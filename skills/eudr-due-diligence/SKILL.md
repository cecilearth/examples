---
name: eudr-due-diligence
description: Run an EUDR (EU Regulation 2023/1115) deforestation-free check on production plots. Subscribes Hansen Global Forest Change to each plot, detects any forest loss after the 31 December 2020 cutoff, and returns a per-plot verdict suitable for a Due Diligence Statement.
license: MIT
---

# EUDR due-diligence check

Use this skill when the user needs to determine whether one or more production plots are EUDR-compliant — i.e. free of deforestation after the 31 December 2020 cutoff defined in [EU Regulation 2023/1115](https://eur-lex.europa.eu/eli/reg/2023/1115/oj). The output is intended for inclusion in the regulatory Due Diligence Statement (DDS).

## Scope and assumptions

- **Cutoff:** any forest loss in calendar year 2021 or later flags the plot as not-clear. With Hansen's `loss_year` encoding (1 = 2001, 2 = 2002, …), the threshold is `loss_year ≥ 21`.
- **Commodities:** EUDR covers cattle, cocoa, coffee, palm oil, rubber, soy, wood, and certain derived products. The skill itself is commodity-agnostic — pass the commodity through to the output for record-keeping.
- **Geolocation format:** EUDR requires polygons for plots ≥4 ha and points for plots <4 ha. Both are valid GeoJSON inputs to `client.create_aoi`.
- **Data source:** Hansen Global Forest Change. Confirm the dataset id against [docs.cecil.earth/datasets](https://docs.cecil.earth/datasets) before relying on it.

## Prerequisites

- [`subscribe-and-load`](../subscribe-and-load/SKILL.md) — for each plot, this skill creates an AOI, subscribes Hansen, and waits for staging.
- [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md) — for the loss-area calculation per plot.

## Steps

1. **Inputs.** A list of plots, each with:
   - `plot_id` — a stable identifier (e.g. supplier farm code).
   - `geometry` — GeoJSON Polygon (≥4 ha) or Point (<4 ha).
   - `commodity` — the EUDR-relevant commodity (optional; recorded in output).

2. **Subscribe Hansen per plot.** Following [`subscribe-and-load`](../subscribe-and-load/SKILL.md): create an AOI, then `client.create_subscription(aoi_id=aoi.id, dataset_id="<hansen-uuid>")`, then poll for staging. Use `external_ref=plot_id` so repeat runs can look up existing AOIs via `client.list_aois()` instead of creating duplicates.

3. **Threshold `loss_year` against the EUDR cutoff.** Apply [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md) with:

   ```python
   variable_name = "loss_year"
   threshold = 21              # 2021 — first non-compliant year
   operator = np.greater_equal
   ```

   This yields `matched_pixels` and `approx_hectares` of post-2020 loss for the plot.

4. **Build the per-plot verdict.**

   ```python
   from datetime import datetime, timezone
   import numpy as np

   loss = ds["loss_year"]
   nodata = loss.attrs.get("_FillValue")
   if nodata is not None:
       loss = loss.where(loss != nodata)

   loss_values = np.ravel(loss.values)
   post_cutoff = loss_values[loss_values >= 21]
   loss_years = sorted({int(y) + 2000 for y in post_cutoff})

   record = {
       "plot_id": plot_id,
       "commodity": commodity,
       "aoi_id": aoi.id,
       "subscription_id": subscription.id,
       "eudr_status": "clear" if matched_pixels == 0 else "not_clear",
       "loss_hectares_post_2020": approx_hectares,
       "loss_years": loss_years,
       "methodology": "Hansen Global Forest Change as served by Cecil; cutoff 2020-12-31 per EUDR Art. 2(13)",
       "checked_at": datetime.now(timezone.utc).isoformat(),
   }
   ```

   Aggregate records across plots into a `pandas.DataFrame` for inclusion in the DDS.

## Important constraints

- **Hansen resolution.** Hansen is 30 m — about 0.09 ha per pixel. Plots smaller than ~0.5 ha (a handful of pixels) sit at the limit of what the data can resolve; flag these as low-confidence in your output.
- **Forest definition.** Hansen baselines "forest" as a tree-cover percentage in the year 2000 (the `tree_cover` band, in %). EUDR follows FAO and counts canopy cover ≥10%. If the strict EUDR definition matters, mask `loss_year` to pixels where `tree_cover ≥ 10` before counting — otherwise you may either under- or over-report depending on the dataset's default forest mask.
- **Hansen version.** Hansen is updated annually; the upper bound on `loss_year` shifts each release. Record the version (or, at minimum, the date you ran the check) in the methodology field of every record.
- **Not legal advice.** This skill produces evidence to support a DDS. The operator placing products on the EU market is responsible for the DDS itself, its risk assessment, and its compliance interpretation.

## References

- [EU Regulation 2023/1115 (EUDR)](https://eur-lex.europa.eu/eli/reg/2023/1115/oj)
- [EU Observatory on Deforestation and Forest Degradation](https://forest-observatory.ec.europa.eu/)
- Hansen et al., *High-Resolution Global Maps of 21st-Century Forest Cover Change*, Science 2013
- [`subscribe-and-load`](../subscribe-and-load/SKILL.md)
- [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md)
- [Cecil quickstart](https://docs.cecil.earth/quickstart) and [SDK reference](https://docs.cecil.earth/sdk)
