"""Emmi Climate Hazard Diagnostics (CHD) helpers for the Cecil SDK.

Plain functions composing ``cecil.Client`` calls into the common CHD patterns:
hectare-scale point Areas of Interest (AOIs), safe re-runnable provisioning,
scenario-aware sampling. Requires ``CECIL_API_KEY`` in the environment.

Public API:
    DATASETS, METRICS, SCENARIOS_BY_HAZARD   catalogue (all keyed by hazard)
    VALID_METRICS                            flat set of every metric name
    list_variables                           discover valid variable names
    verify_catalog                           cross-check the catalogue against the live API
    point_aoi                                build a square AOI for an asset
    estimate_cost                            preview $ before subscribing
    provision                                create or reuse AOIs + subscriptions
    load, sample                             read data from a subscription
    screen                                   one-call portfolio sweep

Portfolio shape:
    Functions taking a ``portfolio`` argument expect a pandas DataFrame with:

        name        str         unique label per asset (used as a key)
        lat         float       latitude  in degrees, EPSG:4326
        lon         float       longitude in degrees, EPSG:4326
        value_usd   float       asset value (optional; drives ``total_usd``)
"""
import logging
import math

import numpy as np
import pandas as pd
import xarray as xr

log = logging.getLogger(__name__)


# ---------- Catalogue ----------------------------------------------------

DATASETS = {
    "wildfire":       "a70e1872-aaa6-480d-b2fc-f778e0343de5",
    "cyclones":       "158e774c-fd11-4402-b6ce-2596960f4637",
    "coastal_floods": "e4de28e6-6e9b-412b-97e2-45e3c7c80e6e",
    "fluvial_floods": "9e2f989c-1df1-44d6-b281-9252002f388a",
}

# Metrics each hazard publishes. Keyed by hazard so it matches the shape of
# DATASETS and SCENARIOS_BY_HAZARD. See the README for units and methodology.
METRICS = {
    "wildfire":       ["average_annual_loss", "intensity", "probability", "fire_danger_days"],
    "cyclones":       ["average_annual_loss", "intensity", "probability", "wind_speed_mps"],
    "coastal_floods": ["average_annual_loss", "intensity", "probability", "depth_meters"],
    "fluvial_floods": ["average_annual_loss", "intensity", "probability", "depth_meters"],
}

# Flat set of every metric name, for cheap "is this a valid metric?" checks.
VALID_METRICS = frozenset({m for ms in METRICS.values() for m in ms})

# Floods are only published for baseline / rcp4p5 / rcp8p5.
SCENARIOS_BY_HAZARD = {
    "wildfire":       ["baseline", "rcp2p6", "rcp4p5", "rcp6p0", "rcp8p5"],
    "cyclones":       ["baseline", "rcp2p6", "rcp4p5", "rcp6p0", "rcp8p5"],
    "coastal_floods": ["baseline", "rcp4p5", "rcp8p5"],
    "fluvial_floods": ["baseline", "rcp4p5", "rcp8p5"],
}

VALID_SCENARIOS = ("baseline", "rcp2p6", "rcp4p5", "rcp6p0", "rcp8p5")
VALID_FUTURE_YEARS = (2030, 2050, 2080)
BASELINE_YEAR = 1980

# Variables that exist in Cecil's response but are deliberately omitted from
# METRICS (not useful for portfolio-style continuous sampling). verify_catalog
# subtracts these so they don't show up as drift.
KNOWN_EXCLUDED = frozenset(f"land_mask_{s}" for s in VALID_SCENARIOS)


def list_variables(metric: str | None = None,
                   scenario: str | None = None,
                   hazard: str | None = None,
                   client=None,
                   verify: bool = True) -> list[str]:
    """Return CHD variable names matching the filters. ``None`` means any.

        list_variables()                       # every valid name
        list_variables(metric="intensity")     # intensity_* across applicable hazards
        list_variables(scenario="rcp4p5")      # *_rcp4p5 across applicable metrics
        list_variables(hazard="wildfire")      # only what wildfire publishes

    If ``client`` is provided and ``verify=True`` (default), the live Cecil
    catalogue is cross-checked via :func:`verify_catalog` and any drift is
    logged as warnings. Pass ``verify=False`` to skip the check even when a
    client is given. With no client, returns the static catalogue.
    """
    names = sorted({
        f"{m}_{s}"
        for h, ms in METRICS.items() if hazard in (None, h)
        for m in ms if metric in (None, m)
        for s in SCENARIOS_BY_HAZARD[h] if scenario in (None, s)
    })
    if client is not None and verify:
        for h, info in verify_catalog(client).items():
            if info["missing"]:
                log.warning(f"{h}: catalogue expects variables not in live data: {sorted(info['missing'])}")
            if info["extra"]:
                log.warning(f"{h}: live data has variables not in catalogue: {sorted(info['extra'])}")
    return names


_ALL_VARIABLES = frozenset(list_variables())


def verify_catalog(client) -> dict[str, dict]:
    """Cross-check the hardcoded catalogue against Cecil's live dataset metadata.

    Queries each dataset in :data:`DATASETS` for its actual variable list and
    compares to what :func:`list_variables` predicts. Useful at session start
    to detect drift if Emmi adds/renames variables between releases.

    Returns ``{hazard: {...}}`` with these fields per hazard:

    * ``missing``  -- expected but not in live (drift: maybe Emmi removed it).
    * ``extra``    -- in live but neither expected nor in :data:`KNOWN_EXCLUDED`
                       (drift: maybe Emmi added something new).
    * ``excluded`` -- live variables that match :data:`KNOWN_EXCLUDED`. Confirms
                       which intentional omissions are actually present. If this
                       shrinks unexpectedly, our exclusion list is stale.
    * ``live``, ``expected`` -- the raw sets, for reference.

    Non-empty ``missing`` or ``extra`` indicates the catalogue should be updated.
    """
    report = {}
    for hazard, dataset_id in DATASETS.items():
        ds = client.get_dataset(dataset_id)
        live = {v.name for v in ds.variables}
        expected = set(list_variables(hazard=hazard))
        report[hazard] = {
            "live":     live,
            "expected": expected,
            "missing":  expected - live,
            "extra":    live - expected - KNOWN_EXCLUDED,
            "excluded": live & KNOWN_EXCLUDED,
        }
    return report


# ---------- AOI geometry -------------------------------------------------

def point_aoi(lat: float, lon: float, target_ha: float = 1.0) -> dict:
    """GeoJSON Polygon of area ``target_ha`` centred on (lat, lon).

    Lat/lon buffers correct for longitude shrinkage so the AOI is square on
    the ground at any latitude (1 ha = 100 m x 100 m anywhere).
    """
    side_m = math.sqrt(target_ha * 10_000)
    half = side_m / 2
    lat_buf = half / 111_000
    lon_buf = half / (111_000 * math.cos(math.radians(lat)))
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - lon_buf, lat - lat_buf],
            [lon + lon_buf, lat - lat_buf],
            [lon + lon_buf, lat + lat_buf],
            [lon - lon_buf, lat + lat_buf],
            [lon - lon_buf, lat - lat_buf],
        ]],
    }


# ---------- Cost ---------------------------------------------------------

def estimate_cost(client, portfolio: pd.DataFrame, target_ha: float = 1.0) -> dict:
    """Print and return a bundle-priced cost estimate, using live Cecil rates.

    Per-hectare rates are fetched from ``Dataset.pricing.tiers`` on one CHD
    dataset (CHD is bundle priced, so all four share the same per-ha rate).
    Billable hectares = ``len(portfolio) * target_ha``.

    Returns ``{"total_ha": float, "rates_per_ha": {tier: $/ha},
    "totals": {tier: $}}``.
    """
    n_assets = len(portfolio)
    total_ha = float(n_assets * target_ha)

    # All four CHD datasets share bundle pricing; query one.
    ds = client.get_dataset(DATASETS["wildfire"])
    rates = {t.volume.nominal: t.price.amount for t in (ds.pricing.tiers or [])}
    totals = {tier: total_ha * rate for tier, rate in rates.items()}

    log.info(f"Per-asset AOI area: {target_ha:.3f} ha")
    log.info(f"Assets: {n_assets} (all four hazards bundled into one $/ha charge)")
    log.info(f"Total billable hectares: {total_ha:.3f}")
    for tier, rate in rates.items():
        log.info(f"  {tier:25s} @ ${rate}/ha: ${totals[tier]:>8,.2f}")
    for line in (ds.pricing.description or []):
        log.info(f"Pricing details: {line}")

    return {
        "total_ha": total_ha,
        "rates_per_ha": rates,
        "totals": totals,
    }


# ---------- Provisioning -------------------------------------------------

def provision(client,
              portfolio: pd.DataFrame,
              datasets: dict | None = None,
              target_ha: float = 1.0,
              tag: str = "emmi-chd") -> dict:
    """Create or reuse AOIs and subscriptions for portfolio x datasets.

    Safe to re-run. AOIs match by ``external_ref`` (includes ``tag`` and
    ``target_ha``); subscriptions match by ``(aoi_id, dataset_id)``.
    Returns ``{asset_name: {hazard: Subscription}}``.
    """
    if datasets is None:
        datasets = DATASETS

    existing_aois = {a.external_ref: a for a in client.list_aois() if a.external_ref}
    existing_subs = {(s.aoi_id, s.dataset_id): s for s in client.list_subscriptions()}

    aois_new = aois_reused = 0
    subs_new = subs_reused = 0
    out = {}

    for _, row in portfolio.iterrows():
        name = row["name"]
        aoi_ref = f"{name} | {tag} | {target_ha}ha"

        aoi = existing_aois.get(aoi_ref)
        if aoi is None:
            aoi = client.create_aoi(
                external_ref=aoi_ref,
                geometry=point_aoi(row["lat"], row["lon"], target_ha),
            )
            aois_new += 1
            log.info(f"  + AOI created   {name:<28} ({aoi.hectares:.3f} ha)")
        else:
            aois_reused += 1
            log.info(f"  = AOI reused    {name:<28} ({aoi.hectares:.3f} ha)")

        out[name] = {}
        for hazard, dataset_id in datasets.items():
            sub = existing_subs.get((aoi.id, dataset_id))
            if sub is None:
                sub = client.create_subscription(
                    external_ref=f"{hazard} - {name}",
                    aoi_id=aoi.id,
                    dataset_id=dataset_id,
                )
                subs_new += 1
            else:
                subs_reused += 1
            out[name][hazard] = sub

    log.info(f"AOIs:          {aois_new + aois_reused:>3} total  ({aois_new} new, {aois_reused} reused)")
    log.info(f"Subscriptions: {subs_new + subs_reused:>3} total  ({subs_new} new, {subs_reused} reused)")

    return out


# ---------- Sampling -----------------------------------------------------

def load(client, subscription, cache: dict | None = None) -> xr.Dataset:
    """Load a subscription's dataset. Pass a ``cache`` dict to dedupe loads."""
    if cache is not None and subscription.id in cache:
        return cache[subscription.id]
    ds = client.load_xarray(subscription.id)
    if cache is not None:
        cache[subscription.id] = ds
    return ds


def sample(ds: xr.Dataset, variable: str, year: int | None = None) -> float:
    """Sample one scalar from a sub-pixel CHD subscription.

    ``variable`` is the full name (e.g. ``"average_annual_loss_rcp4p5"``).
    ``year`` filters time; ``None`` picks the only populated entry via
    nan-aware mean. Returns NaN if variable/time has no data. Raises
    ``ValueError`` for an unknown variable name.
    """
    if variable not in _ALL_VARIABLES:
        raise ValueError(
            f"Unknown CHD variable {variable!r}. See chd.list_variables()."
        )
    if variable not in ds or ds[variable].size == 0:
        return float("nan")

    da = ds[variable]
    if year is not None and "time" in da.dims:
        years = _years_from_time(da["time"])
        matches = np.where(years == year)[0]
        if matches.size == 0:
            return float("nan")
        da = da.isel(time=int(matches[0]))

    return float(da.mean(skipna=True).values)


# ---------- Get hazard data for portfolio ------------------------------------------

def screen(
    client,
    portfolio: pd.DataFrame,
    scenario: str | list[str] = "rcp4p5",
    year: int | list[int] = 2050,
    metric: str | list[str] = "average_annual_loss",
    hazards: list[str] | None = None,
    delta: bool = True,
    target_ha: float = 1.0,
    tag: str = "emmi-chd",
    subs: dict | None = None,
    cache: dict | None = None,
    require_confirmation: bool = True,
) -> pd.DataFrame | None:
    """End-to-end multi-hazard portfolio screen.

    Default: per-asset per-hazard climate-attributable delta in AAL under
    RCP4.5 at 2050. ``scenario``, ``year``, ``metric`` accept lists to sweep.

    Args:
        client:    a connected ``cecil.Client``.
        portfolio: DataFrame with ``name``, ``lat``, ``lon``, optional ``value_usd``.
        scenario:  ``baseline, rcp2p6, rcp4p5, rcp6p0, rcp8p5``, or a list.
        year:      2030, 2050, 2080, or a list. Baseline rows always use 1980.
        metric:    one of :data:`VALID_METRICS`, or a list.
        hazards:   subset of :data:`DATASETS`. ``None`` means all four.
        delta:     ``True`` -- hazard columns hold ``future - baseline``.
                   ``False`` -- hazard columns hold the absolute value.
                   Baseline rows always return absolute (delta is meaningless).
        target_ha: AOI size per asset.
        tag:       inserted into the AOI ``external_ref`` for namespacing.
        subs:      reuse the output of :func:`provision` instead of re-running
                   it. Useful when calling :func:`screen` multiple times.
        cache:     dict; reuse xarray cache across calls. Each subscription
                   downloads once; repeat screens are much faster.
        require_confirmation: print cost and prompt y/n. Returns ``None`` on abort.

    Returns:
        Long-format DataFrame, one row per ``(asset, scenario, year, metric)``.
        Columns: ``name, [value_usd,] scenario, year, metric, <hazards...>,
        total[, total_usd]``. NaN propagates for combos Emmi doesn't publish.
    """
    scenarios = scenario if isinstance(scenario, list) else [scenario]
    years     = year     if isinstance(year, list)     else [year]
    metrics   = metric   if isinstance(metric, list)   else [metric]
    if hazards is None:
        hazards = list(DATASETS.keys())

    for m in metrics:
        if m not in VALID_METRICS:
            raise ValueError(f"Unknown metric: {m!r}. Valid: {sorted(VALID_METRICS)}")
    for s in scenarios:
        if s not in VALID_SCENARIOS:
            raise ValueError(f"Unknown scenario: {s!r}. Valid: {list(VALID_SCENARIOS)}")
    for h in hazards:
        if h not in DATASETS:
            raise ValueError(f"Unknown hazard: {h!r}. Valid: {list(DATASETS)}")

    if require_confirmation:
        estimate_cost(client, portfolio, target_ha=target_ha)
        try:
            response = input("\nProceed? [y/N]: ").strip().lower()
        except EOFError:
            response = ""
        if response not in ("y", "yes"):
            log.info("Aborted.")
            return None

    if subs is None:
        selected_datasets = {h: DATASETS[h] for h in hazards}
        subs = provision(client, portfolio, selected_datasets, target_ha=target_ha, tag=tag)
    if cache is None:
        cache = {}

    use_value = "value_usd" in portfolio.columns
    combos = _build_combos(scenarios, years, metrics)
    combos_df = pd.DataFrame(combos, columns=["scenario", "year", "metric"])
    keep_cols = ["name"] + (["value_usd"] if use_value else [])
    df = portfolio[keep_cols].merge(combos_df, how="cross")

    records = df.to_dict(orient="records")
    for h in hazards:
        df[h] = [
            _sample_one(client, subs[r["name"]][h], h,
                        r["metric"], r["scenario"], r["year"], delta, cache)
            for r in records
        ]

    # Aggregate across hazards by summing. See:
    # https://support.emmi.io/questions/climate-hazard-diagnostics-multi-hazard-aggregation
    df["total"] = df[list(hazards)].sum(axis=1, skipna=False)
    if use_value:
        df["total_usd"] = df["total"] * df["value_usd"]

    id_cols = ["name"] + (["value_usd"] if use_value else []) + ["scenario", "year", "metric"]
    data_cols = list(hazards) + ["total"] + (["total_usd"] if use_value else [])
    return df[id_cols + data_cols]


# ---------- Private helpers ----------------------------------------------

def _exists(metric: str, scenario: str, hazard: str) -> bool:
    """True if ``(metric, scenario)`` is published for ``hazard``."""
    if metric not in METRICS.get(hazard, []):
        return False
    if scenario == "baseline":
        return True
    return scenario in SCENARIOS_BY_HAZARD.get(hazard, [])


def _build_combos(scenarios: list[str],
                  years: list[int],
                  metrics: list[str]) -> list[tuple[str, int, str]]:
    """Cartesian product of (scenario, year, metric). Baseline forced to 1980."""
    combos = []
    for s in scenarios:
        for m in metrics:
            if s == "baseline":
                combos.append((s, BASELINE_YEAR, m))
            else:
                for y in years:
                    combos.append((s, y, m))
    return list(dict.fromkeys(combos))


def _sample_one(client,
                sub,
                hazard: str,
                metric: str,
                scenario: str,
                year: int | None,
                delta: bool,
                cache: dict) -> float:
    """Sample one (asset, hazard) cell. NaN for invalid combos; baseline rows
    always return the absolute value (delta is meaningless against itself)."""
    if not _exists(metric, scenario, hazard):
        return float("nan")

    ds = load(client, sub, cache=cache)

    if scenario == "baseline":
        return sample(ds, f"{metric}_baseline")

    future = sample(ds, f"{metric}_{scenario}", year=year)
    if not delta or pd.isna(future):
        return future

    baseline = sample(ds, f"{metric}_baseline")
    if pd.isna(baseline):
        return float("nan")
    return future - baseline


def _years_from_time(time_da: xr.DataArray) -> np.ndarray:
    """Return an int array of years for whatever time encoding xarray returns."""
    vals = time_da.values
    if np.issubdtype(vals.dtype, np.datetime64):
        return pd.DatetimeIndex(vals).year.to_numpy()
    return vals.astype(int)
