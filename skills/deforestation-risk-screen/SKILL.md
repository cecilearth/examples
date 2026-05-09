---
name: deforestation-risk-screen
description: Run a Hansen Global Forest Change screen across a portfolio of AOIs and report total forest loss, loss-by-year, and percent of AOI lost per plot. Useful for TNFD Locate, CSRD E4, and supply-chain risk assessment (without the EUDR-specific cutoff).
license: MIT
---

# Deforestation risk screen

Use this skill to assess forest-loss exposure across multiple sites — supplier farms, owned land, planned acquisitions — without the regulatory framing of the EUDR check. Common for TNFD Locate (sensitive locations), CSRD E4 (ecosystem extent change), and general supply-chain risk.

For the EUDR-specific version with the 31 December 2020 cutoff and DDS-shaped output, use [`eudr-due-diligence`](../eudr-due-diligence/SKILL.md) instead.

## Prerequisites

- [`screen-portfolio`](../screen-portfolio/SKILL.md) — to subscribe Hansen Global Forest Change to each plot.
- [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md) — to count loss pixels per year.

## Steps

1. **Screen the portfolio with Hansen.** Run [`screen-portfolio`](../screen-portfolio/SKILL.md) with `dataset_id=<hansen-uuid>`. Confirm the dataset id against [docs.cecil.earth/datasets](https://docs.cecil.earth/datasets).

2. **For each plot, count loss pixels.** Hansen's `loss_year` band encodes the year of forest loss (1 = 2001, …, 24 = 2024). For each plot's loaded `ds`:

   ```python
   import numpy as np

   loss = ds["loss_year"]
   nodata = loss.attrs.get("_FillValue")
   if nodata is not None:
       loss = loss.where(loss != nodata)

   values = np.ravel(loss.values)
   valid = values[~np.isnan(values)]
   any_loss = valid[valid > 0]

   loss_by_year = {
       int(y) + 2000: int((any_loss == y).sum()) for y in np.unique(any_loss)
   }
   total_loss_pct = (any_loss.size / valid.size) * 100.0 if valid.size else 0.0
   total_loss_hectares = total_loss_pct / 100.0 * aoi.hectares
   ```

3. **Build the per-plot record.**

   ```python
   {
       "plot_id": plot_id,
       "aoi_hectares": aoi.hectares,
       "total_loss_hectares": total_loss_hectares,
       "total_loss_pct": total_loss_pct,
       "loss_by_year": loss_by_year,
       "first_loss_year": min(loss_by_year, default=None),
       "last_loss_year": max(loss_by_year, default=None),
   }
   ```

4. **Roll up the portfolio.** Sum totals, rank plots by `total_loss_pct`, and surface the worst-affected sites for follow-up.

## Important constraints

- **Hansen scope.** Hansen reports forest loss but does not directly report degradation, replanting, or short-rotation cycles — interpret `loss_by_year` accordingly. Use the `tree_cover` band as the year-2000 baseline if relevant.
- **Equal-area approximation.** Hectare conversion uses `aoi.hectares × pixel-percentage`. For high-latitude or very large AOIs, weight by actual pixel area (via `rioxarray` and the dataset's CRS) instead.
- **Not a replacement for EUDR.** This skill does not produce a Due Diligence Statement. Use [`eudr-due-diligence`](../eudr-due-diligence/SKILL.md) for that.

## References

- [`screen-portfolio`](../screen-portfolio/SKILL.md)
- [`compute-area-by-threshold`](../compute-area-by-threshold/SKILL.md)
- [`eudr-due-diligence`](../eudr-due-diligence/SKILL.md)
- Hansen et al., *High-Resolution Global Maps of 21st-Century Forest Cover Change*, Science 2013
