---
name: land-cover-baseline-and-change
description: Establish a baseline-year land-cover composition for each AOI in a portfolio and compute year-over-year deltas per class. Feeds CSRD ESRS E4 (biodiversity & ecosystems) ecosystem-extent disclosure and TNFD's Evaluate phase.
license: MIT
---

# Land-cover baseline and change

Use this skill to characterise what's on a site (forest, cropland, urban, water, …) and how that changes over time. Required input for CSRD E4 ecosystem extent and TNFD's Evaluate phase.

## Prerequisites

- [`screen-portfolio`](../screen-portfolio/SKILL.md) — to subscribe a categorical land-cover dataset to each plot.

## Steps

1. **Subscribe Land Cover 9-Class** (or another categorical land-cover dataset) to the portfolio via [`screen-portfolio`](../screen-portfolio/SKILL.md).

2. **For each plot, count pixels per class per timestep.**

   ```python
   import numpy as np

   classes = ds[list(ds.data_vars)[0]]      # confirm the variable name from ds.data_vars
   nodata = classes.attrs.get("_FillValue")
   if nodata is not None:
       classes = classes.where(classes != nodata)

   results_by_time = {}
   times = classes["time"].values if "time" in classes.dims else [None]
   for t in times:
       slice_da = classes.sel(time=t) if t is not None else classes
       values = np.ravel(slice_da.values)
       valid = values[~np.isnan(values)].astype(int)
       unique, counts = np.unique(valid, return_counts=True)
       results_by_time[str(t)] = {int(c): int(n) for c, n in zip(unique, counts)}
   ```

3. **Pick a baseline year.** Typically the earliest available timestep, or a reporting-framework-specific year (CSRD reporters often use 2020 or a company-specific baseline).

4. **Compute deltas.** For each comparison year, subtract baseline counts class-by-class to get net change in pixels per class. Convert to hectares using `aoi.hectares × class_count / total_valid_count`.

5. **Decode class codes to readable names.** Class codes are dataset-specific. Fetch the variable's `reference_table` to map integer codes to names:

   ```python
   dataset = client.get_dataset(dataset_id)
   var = next(v for v in dataset.variables if v.name == "<variable>")
   code_to_name = {row["code"]: row["name"] for row in var.reference_table}
   ```

   Never guess class codes; always derive them from `reference_table`.

## Important constraints

- **Pick the right dataset.** Land-cover datasets differ in classes, resolution, and update frequency. Check the catalogue and pick one that matches the user's reporting framework.
- **Consistency over time.** Some land-cover datasets re-classify pixels between releases for reasons unrelated to actual change (updated training data, methodology revisions). When possible, compare years from the same release.
- **Tiny plots.** For plots smaller than a few pixels, class composition is noisy; flag low-confidence cases.

## References

- [`screen-portfolio`](../screen-portfolio/SKILL.md)
- [Cecil SDK reference](https://docs.cecil.earth/sdk)
- CSRD ESRS E4 — Biodiversity and ecosystems
- TNFD LEAP approach (Evaluate phase)
