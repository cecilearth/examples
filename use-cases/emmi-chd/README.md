# Emmi Climate Hazard Diagnostics

Portfolio and single-asset examples using Emmi's Climate Hazard Diagnostics (CHD) datasets via Cecil:

- [Wildfire](https://docs.cecil.earth/datasets/a70e1872-aaa6-480d-b2fc-f778e0343de5)
- [Tropical Cyclones](https://docs.cecil.earth/datasets/158e774c-fd11-4402-b6ce-2596960f4637)
- [Coastal Floods](https://docs.cecil.earth/datasets/e4de28e6-6e9b-412b-97e2-45e3c7c80e6e)
- [Fluvial Floods](https://docs.cecil.earth/datasets/9e2f989c-1df1-44d6-b281-9252002f388a)

See the Cecil Docs for the full per-dataset variable list and methodology notes.

Wildfire and cyclones are provided on a ~0.1° (~11 km) global grid; floods are finer at ~0.0089° (~1 km). All datasets carry a historical baseline (1980, calibrated to present-day) and futures at 2030 / 2050 / 2080 under IPCC Representative Concentration Pathways (RCPs) 2.6 / 4.5 / 6.0 / 8.5. Floods are not provided for RCP2.6 or RCP6.0.

## Examples

- [`single-asset-deep-dive.ipynb`](single-asset-deep-dive.ipynb): notebook that picks one asset (Channelview Cogeneration Plant) and pulls every variable Emmi publishes for it; intensity, probability, AAL, fire-danger-days, wind speed and depth, across baseline plus four RCP scenarios.
- [`portfolio-screening-east-texas.ipynb`](portfolio-screening-east-texas.ipynb): multi-hazard screening of a small US power-generation portfolio in East Texas. Uses small per-asset AOIs to keep cost low and prints an upfront cost estimate before any subscription is created.

Both notebooks share a `chd.py` helper (in this directory) that wraps the Cecil SDK with hectare-scale point AOIs, safe re-runnable provisioning, and scenario-aware sampling.

## Cecil Dataset IDs

| Hazard | Dataset UUID |
|---|---|
| Wildfire | `a70e1872-aaa6-480d-b2fc-f778e0343de5` |
| Cyclones | `158e774c-fd11-4402-b6ce-2596960f4637` |
| Coastal floods | `e4de28e6-6e9b-412b-97e2-45e3c7c80e6e` |
| Fluvial floods | `9e2f989c-1df1-44d6-b281-9252002f388a` |

## Cost note

Cecil charges per hectare of Area of Interest (AOI). Emmi CHD is **bundle priced**: one `$/ha` covers all four hazard datasets and every layer they publish (intensity, probability, Average Annual Loss (AAL), fire-danger-days, wind speed, flood depth) across baseline plus four RCP scenarios. You do **not** multiply by the number of datasets.

The examples here use 1 hectare AOIs per asset (well below the 0.1° / ~11 km CHD pixel), so the whole 5-asset portfolio costs cents at the subscription tier.

## License

The example code in this directory (notebooks, `chd.py`) is released under the [MIT License](../../LICENSE), same as the rest of `cecil_examples`.

The Emmi Climate Hazard Diagnostics **datasets themselves are commercial** and licensed through Cecil under their standard data agreement. Running the notebooks creates Cecil subscriptions against your account; you'll need a valid Cecil API key and the associated data entitlement. See the [Cecil dataset pages](https://docs.cecil.earth/datasets) for current licensing terms, and contact Cecil for commercial use beyond this example.
