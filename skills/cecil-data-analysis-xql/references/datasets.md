# Picking a Cecil dataset

For the live catalog of every published dataset, **call the SDK** — don't
trust a static list (this file used to be one and went stale within weeks):

```python
import cecil
for d in cecil.Client().list_datasets():
    print(d.id, d.name, d.categories,
          d.spatial_resolution.nominal, d.temporal_coverage.nominal)
```

Every `Dataset` carries `id, name, type, categories, providers, variables,
description, usage_notes, constraints, pricing, spatial_resolution,
temporal_coverage, …`. This file only adds the editorial layer the SDK
*can't* give you — which dataset to pick for which question — plus the
cross-cutting gotchas that affect SQL.

## Selection guidance

**Plant biomass / forest carbon** — Chloris (project-scale: 10 m from 2017+,
30 m from 2000+), Kanop (project monitoring; the Screening tier is the
cheap pre-flight pass), Planet Forest Carbon (Diligence 30 m, Monitoring
3.5 m quarterly), Sylvera (long-term atlas), UMD Hansen (industry standard
for tree loss / gain).

**Land use & land cover** — Impact Observatory 9-/15-/17-Class
(simplified → detailed → very-high-res; pick by class count + pixel size),
JRC Global Forest Cover / Type (2020 snapshots), USDA Cropland Data Layer
(US-only; 10 m for recent, 30 m for long history), USGS Annual NLCD
(40 years of US LULC change), WRI SBTN Natural Lands (SBTN-aligned, 2020),
WRI Tropical Tree Cover (tropics-only).

**Soil moisture** — Lobelia Earth 30 m (field-scale), Planet Soil Water
Content 20 m (frequent, very-high-res) or 1 km (regional, history back to
2002).

**Biodiversity** — IBAT family (IUCN Red List, KBA, WDPA, STAR) for
species / KBA / protected-area overlaps, NHM BII 1 km / 10 km for
biodiversity-intactness scoring.

**Ecosystem integrity** — WCS Forest Landscape Integrity Index
(landscape fragmentation, 2019 snapshot).

## Cross-cutting gotchas

- **LULC integer codes.** `land_cover_class` (and similar) are integer
  codes that mean nothing without joining the variable's `reference_table`.
  See `xarray_sql.md` for the join pattern.
- **IBAT is vector.** Use `client.load_dataframe(...)`, **not**
  `load_xarray`. IBAT datasets are pandas DataFrames, not gridded rasters.
- **US-only datasets.** USDA Cropland Data Layer and USGS NLCD don't cover
  non-US AOIs. WRI Tropical Tree Cover is tropics-only.
- **BII history stops in 2021.** If the question is about 2022+, BII
  won't help.

## Quick "what dataset answers what question" map

| User asks about... | Try... |
|---|---|
| Forest carbon stock or change | Chloris, Kanop, Planet Forest Carbon, Sylvera |
| Tree-cover loss / deforestation | UMD Hansen, JRC Forest Cover |
| Land cover class history | Impact Observatory (global) or USGS NLCD (US-only) |
| Crop type (US) | USDA Cropland Data Layer |
| Tropical forest extent | WRI Tropical Tree Cover, JRC Forest Cover |
| Soil moisture / drought | Lobelia Earth, Planet Soil Water Content |
| Threatened species overlap | IBAT IUCN Red List (vector — `load_dataframe`) |
| Protected area overlap | IBAT WDPA (vector) |
| Key Biodiversity Areas | IBAT KBA (vector) |
| Biodiversity intactness | NHM BII 1km / 10km |
| Forest landscape integrity | WCS Forest Landscape Integrity Index |

## Out of scope for this skill

Cecil does not cover weather forecasts, atmospheric chemistry / air
quality, GHG concentrations, or ocean / marine datasets. If a user asks
for one of these, tell them plainly that Cecil doesn't carry that data —
don't force-fit a dataset that doesn't really answer the question.
