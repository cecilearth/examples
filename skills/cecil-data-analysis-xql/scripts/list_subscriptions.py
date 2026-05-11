#!/usr/bin/env python
"""List the user's Cecil subscriptions with the dataset behind each one.

Used by the cecil-data-analysis-xql skill to figure out which datasets are
already paid for before suggesting analysis. Output is intentionally compact
and machine-readable so the calling model can scan it quickly.

Usage:
    uv run python scripts/list_subscriptions.py            # text output
    uv run python scripts/list_subscriptions.py --json     # JSON output
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cecil

from _env import load_dotenv
load_dotenv()


def _row(sub, ds) -> dict:
    return {
        "subscription_id": sub.id,
        "dataset_id": sub.dataset_id,
        "dataset_name": ds.name,
        "type": ds.type,
        "categories": ds.categories,
        "aoi_id": getattr(sub, "aoi_id", None),
        "external_ref": getattr(sub, "external_ref", None),
        "variables": [
            {"name": v.name, "units": v.units, "categorical": bool(v.reference_table)}
            for v in ds.variables
        ],
        "spatial_resolution": ds.spatial_resolution.nominal,
        "temporal_coverage": ds.temporal_coverage.nominal,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--include-archived", action="store_true", help="include archived subs"
    )
    args = parser.parse_args()

    if not os.environ.get("CECIL_API_KEY"):
        print("error: CECIL_API_KEY is not set", file=sys.stderr)
        return 2

    client = cecil.Client()
    subs = client.list_subscriptions(archived=args.include_archived)
    if not subs:
        print("no subscriptions found")
        return 0

    rows = []
    for sub in subs:
        try:
            ds = client.get_dataset(sub.dataset_id)
        except Exception as e:  # network / auth issues shouldn't kill the whole list
            print(
                f"warn: could not fetch dataset {sub.dataset_id}: {e}",
                file=sys.stderr,
            )
            continue
        rows.append(_row(sub, ds))

    if args.json:
        json.dump(rows, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    for r in rows:
        print(f"- subscription: {r['subscription_id']}")
        print(f"    dataset:    {r['dataset_name']}  ({r['dataset_id']})")
        print(f"    type:       {r['type']}   categories: {', '.join(r['categories'])}")
        print(f"    resolution: {r['spatial_resolution']}   coverage: {r['temporal_coverage']}")
        if r["aoi_id"]:
            print(f"    aoi:        {r['aoi_id']}")
        var_names = [v["name"] for v in r["variables"]]
        cat_names = [v["name"] for v in r["variables"] if v["categorical"]]
        print(f"    variables:  {', '.join(var_names) or '(none)'}")
        if cat_names:
            print(f"    categorical: {', '.join(cat_names)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
