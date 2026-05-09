---
name: compute-area-by-threshold
description: Compute the area within an AOI where a variable from a Cecil dataset crosses a threshold (e.g., "hectares of forest with biomass above 100 Mg/ha"). Reports per-timestep pixel counts, percentage, and an approximate hectare figure.
license: MIT
---

# Compute area-by-threshold

Use this skill when the user asks "how much area meets condition X?" — e.g. forest with biomass above a level, cropland with NDVI below a value, pixels of a specific land-cover class.

## Prerequisites

Run the [`subscribe-and-load`](../subscribe-and-load/SKILL.md) skill first to get:
- a loaded `ds: xarray.Dataset`
- the source `aoi: AOI` (for the `aoi.hectares` figure)

## Steps

1. **Pick the variable and threshold.** Choose `variable_name` from `ds.data_vars` and a threshold appropriate to that variable's units. Pick an operator matching the user's question.

   ```python
   import numpy as np

   variable_name = "..."             # e.g. "loss_year", "tree_cover"
   threshold = ...                    # numeric
   operator = np.greater_equal        # or np.greater, np.less, np.less_equal, np.equal, np.not_equal
   ```

2. **Mask fill values and apply the threshold per-timestep.**

   ```python
   da = ds[variable_name]
   nodata = da.attrs.get("_FillValue")
   if nodata is not None:
       da = da.where(da != nodata)

   time_values = da["time"].values if "time" in da.dims else [None]

   results = []
   for t in time_values:
       slice_da = da.sel(time=t) if t is not None else da
       values = np.ravel(slice_da.values)
       valid = values[~np.isnan(values)]
       if valid.size == 0:
           continue
       matched = int(np.count_nonzero(operator(valid, threshold)))
       pct = matched / valid.size * 100.0
       results.append({
           "time": str(t) if t is not None else None,
           "valid_pixels": int(valid.size),
           "matched_pixels": matched,
           "percentage": pct,
           "approx_hectares": pct / 100.0 * aoi.hectares,
       })
   ```

3. **Inspect or plot `results`.** Each entry summarises one timestep (or the whole dataset if there's no `time` dim).

## Important constraints

- **Equal-area approximation.** This treats every pixel as having identical area. That is reasonable for small AOIs but biases outwards from the equator. For high-latitude AOIs or AOIs spanning many degrees of latitude, weight by actual pixel area (via `rioxarray` and the dataset's CRS) instead of using `aoi.hectares` directly.
- **`_FillValue` masking is essential** — counting no-data pixels as zero or as a numeric value silently distorts the percentage.
- **Categorical variables** (e.g. land-cover class) are valid here — use `np.equal` with the integer class code as the threshold.

## References

- [`subscribe-and-load`](../subscribe-and-load/SKILL.md)
- [Cecil MCP server](https://github.com/cecilearth/mcp) — `analyze_thresholded_area_summary` is the reference implementation this skill mirrors
- [`tutorials/raster/detect-change.ipynb`](../../tutorials/raster/detect-change.ipynb) — thresholding for change detection
- [`use-cases/calculate-total-carbon-storage.ipynb`](../../use-cases/calculate-total-carbon-storage.ipynb) — converting per-pixel summaries to AOI-scale totals
