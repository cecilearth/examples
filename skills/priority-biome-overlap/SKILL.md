---
name: priority-biome-overlap
description: Determine whether AOIs intersect priority forest types or sensitive biomes by subscribing Global Forest Type / Global Forest Cover (or similar) and reporting per-class area per plot. Supports TNFD Locate (sensitive locations).
license: MIT
---

# Priority biome / forest-type overlap

Use this skill for TNFD Locate when the user needs to check whether their portfolio overlaps with sensitive ecosystems — primary forest, mangroves, peat, etc. Generalises to any categorical raster of biome / ecosystem types.

## Prerequisites

- [`screen-portfolio`](../screen-portfolio/SKILL.md)
- [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md) — applied per class with `np.equal`.

## Steps

1. **Subscribe a forest-type or biome dataset** (e.g. Global Forest Type, Global Forest Cover) to the portfolio via [`screen-portfolio`](../screen-portfolio/SKILL.md). Confirm the dataset id and the list of class codes against [docs.cecil.earth/datasets](https://docs.cecil.earth/datasets) and `client.get_dataset(dataset_id).variables`.

2. **Define the priority class set.** Either:
   - Per-framework: e.g. TNFD's "high-integrity natural ecosystems".
   - Per-user: a list of class codes the user cares about.

3. **For each plot, count pixels per class:**

   ```python
   import numpy as np

   classes = ds[list(ds.data_vars)[0]]      # confirm against ds.data_vars
   values = np.ravel(classes.values)
   valid = values[~np.isnan(values)].astype(int)
   unique, counts = np.unique(valid, return_counts=True)
   composition = {int(c): int(n) for c, n in zip(unique, counts)}

   priority_pixels = sum(composition.get(c, 0) for c in priority_class_codes)
   priority_pct = (priority_pixels / valid.size) * 100.0 if valid.size else 0.0
   priority_hectares = priority_pct / 100.0 * aoi.hectares
   ```

4. **Build the verdict per plot:**

   ```python
   {
       "plot_id": plot_id,
       "aoi_hectares": aoi.hectares,
       "priority_hectares": priority_hectares,
       "priority_pct": priority_pct,
       "composition": composition,            # full breakdown by code
       "intersects_priority": priority_pixels > 0,
   }
   ```

5. **Roll up the portfolio.** Surface plots that intersect priority biomes at all, and rank by priority footprint for follow-up.

## Important constraints

- **Class codes are dataset-specific.** Use `client.get_dataset(...).variables[i].reference_table` to map codes to names — never guess.
- **Priority definitions are framework-specific.** TNFD, IUCN KBA, and country-specific lists each have their own definitions. Document which definition you applied.
- **Overlap ≠ impact.** Spatial overlap is necessary but not sufficient evidence of impact; pair with land-cover change or activity data for the impact assessment.

## References

- [`screen-portfolio`](../screen-portfolio/SKILL.md)
- [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md)
- TNFD LEAP approach (Locate phase)
- [Cecil dataset catalogue](https://docs.cecil.earth/datasets)
