---
name: land-use-carbon-flux
description: Estimate emissions or removals from land-use change across a portfolio by combining land-cover transitions with a carbon-density dataset. Approximate by design — feeds CSRD ESRS E1 (climate change) Scope 1/3 land-use disclosures.
license: MIT
---

# Land-use carbon flux

Use this skill to estimate the carbon impact of land-use change across a portfolio of sites — for CSRD E1 disclosures, science-based-targets validation, and corporate footprint reporting that includes Scope 3 land-use emissions.

This skill is deliberately an approximation: full IPCC-grade flux accounting requires species-specific carbon stocks, time-since-disturbance models, and disaggregation between living/dead biomass and soil carbon, none of which are fully inferrable from gridded products alone. Treat the output as a screening estimate.

## Prerequisites

- [`screen-portfolio`](../screen-portfolio/SKILL.md) — once per dataset (one run for land cover, another for carbon density).
- [`land-cover-baseline-and-change`](../land-cover-baseline-and-change/SKILL.md) — to obtain per-plot transitions between two timesteps.

## Steps

1. **Pick datasets.**
   - Land cover: e.g. Land Cover 9-Class.
   - Carbon density: e.g. Planet Forest Carbon Monitoring (`aboveground_live_carbon_density`, in Mg C / ha) — confirm against [docs.cecil.earth/datasets](https://docs.cecil.earth/datasets).

2. **Subscribe both datasets** to the portfolio via [`screen-portfolio`](../screen-portfolio/SKILL.md). You'll have two subscription ids per plot.

3. **Compute the land-cover transition matrix per plot.** For two timesteps `t0` and `t1`, count pixels for every (class@t0 → class@t1) pair:

   ```python
   import numpy as np

   lc_ds = client.load_xarray(lc_subscription.id)
   lc = lc_ds[list(lc_ds.data_vars)[0]]     # confirm against lc_ds.data_vars
   t0 = lc.sel(time=baseline_year).values
   t1 = lc.sel(time=comparison_year).values
   stack = np.stack([t0.ravel(), t1.ravel()], axis=1)
   pairs, counts = np.unique(stack, axis=0, return_counts=True)
   transitions = {
       tuple(p.astype(int)): int(c)
       for p, c in zip(pairs, counts)
       if not np.isnan(p).any()
   }
   ```

4. **Compute mean carbon density per plot.**

   ```python
   carbon_ds = client.load_xarray(carbon_subscription.id)
   acd = carbon_ds["aboveground_live_carbon_density"]
   mean_acd = float(acd.mean(dim=["x", "y"]).sel(time=baseline_year))   # Mg C / ha
   ```

5. **Apply per-transition emission/removal factors.** Document the factors you use — CSRD requires the methodology to be auditable. Conservative defaults for a screening estimate:

   ```python
   FOREST_LIKE = {1, 2, 3}      # dataset-specific class codes
   CROPLAND = {6}
   URBAN = {7}

   def factor(c0, c1):
       if c0 in FOREST_LIKE and c1 in (CROPLAND | URBAN):
           return 1.0              # full above-ground stock loss
       return 0.0

   per_pixel_ha = aoi.hectares / total_valid_pixels
   flux_mg_c = sum(
       count * per_pixel_ha * mean_acd * factor(c0, c1)
       for (c0, c1), count in transitions.items()
   )
   ```

6. **Build the per-plot record** with `flux_mg_c`, the underlying transition matrix, and a methodology string (factors applied, datasets used, baseline year, sign convention).

## Important constraints

- **Approximate.** The output is a screening estimate, not an inventory. For audit-grade reporting, replace the simple factors with peer-reviewed look-up tables (IPCC Tier 2/3, country-specific) and disaggregate above-/below-ground/soil pools.
- **Mean carbon density.** Step 4 takes the AOI-level mean. For plots with strong internal heterogeneity, weight `mean_acd` per land-cover class instead.
- **Sign convention.** Document whether positive flux is emission or removal — frameworks differ.
- **Not Scope attribution.** This estimates emissions associated with land-use change on the AOI; deciding which Scope they belong to is a corporate-accounting judgement separate from this skill.

## References

- [`screen-portfolio`](../screen-portfolio/SKILL.md)
- [`land-cover-baseline-and-change`](../land-cover-baseline-and-change/SKILL.md)
- [`use-cases/calculate-total-carbon-storage.ipynb`](../../use-cases/calculate-total-carbon-storage.ipynb)
- IPCC 2019 Refinement to the 2006 IPCC Guidelines for National Greenhouse Gas Inventories (AFOLU)
- CSRD ESRS E1 — Climate change
