#!/usr/bin/env python
"""Inspect a Cecil dataset by ID: variables, units, reference tables, constraints.

Used by the cecil-data-analysis-xql skill when narrowing down which dataset to use
or before writing SQL against an unfamiliar dataset. Reference tables are
truncated to a preview by default.

Usage:
    uv run python scripts/inspect_dataset.py <dataset_id>
    uv run python scripts/inspect_dataset.py <dataset_id> --json
    uv run python scripts/inspect_dataset.py <dataset_id> --full-reference-table
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cecil

from _env import load_dotenv
load_dotenv()


REF_TABLE_PREVIEW_ROWS = 10


def _dataset_to_dict(ds, include_full_ref: bool) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "type": ds.type,
        "crs": ds.crs,
        "categories": ds.categories,
        "providers": [p.name for p in ds.providers],
        "spatial_coverage": ds.spatial_coverage.nominal,
        "spatial_resolution": {
            "nominal": ds.spatial_resolution.nominal,
            "x": ds.spatial_resolution.x,
            "y": ds.spatial_resolution.y,
            "units": ds.spatial_resolution.units,
        },
        "temporal_coverage": ds.temporal_coverage.nominal,
        "temporal_resolution": ds.temporal_resolution.nominal,
        "constraints": {
            "aoi_min_hectares": ds.constraints.aoi_min_hectares,
            "aoi_max_hectares": ds.constraints.aoi_max_hectares,
            "aoi_min_latitude": ds.constraints.aoi_min_latitude,
            "aoi_max_latitude": ds.constraints.aoi_max_latitude,
            "aoi_max_vertices": ds.constraints.aoi_max_vertices,
            "aoi_geometry_types": ds.constraints.aoi_geometry_types,
            "organisation_verified_only": ds.constraints.organisation_verified_only,
        },
        "variables": [
            {
                "name": v.name,
                "type": v.type,
                "units": v.units,
                "no_data": v.no_data,
                "description": v.description,
                "usage_notes": v.usage_notes,
                "reference_table": (
                    v.reference_table
                    if include_full_ref
                    else v.reference_table[:REF_TABLE_PREVIEW_ROWS]
                ),
                "reference_table_total_rows": len(v.reference_table),
            }
            for v in ds.variables
        ],
        "description": ds.description,
        "usage_notes": ds.usage_notes,
    }


def _print_text(d: dict) -> None:
    print(f"{d['name']}  ({d['id']})")
    print(f"  type:        {d['type']}    crs: {d['crs']}")
    print(f"  providers:   {', '.join(d['providers']) or '(none)'}")
    print(f"  categories:  {', '.join(d['categories']) or '(none)'}")
    print(f"  spatial:     {d['spatial_coverage']} @ {d['spatial_resolution']['nominal']}")
    print(f"  temporal:    {d['temporal_coverage']} ({d['temporal_resolution']})")

    c = d["constraints"]
    aoi_bits = []
    if c["aoi_min_hectares"] is not None:
        aoi_bits.append(f"min {c['aoi_min_hectares']} ha")
    if c["aoi_max_hectares"] is not None:
        aoi_bits.append(f"max {c['aoi_max_hectares']} ha")
    if c["aoi_geometry_types"]:
        aoi_bits.append("geom: " + ",".join(c["aoi_geometry_types"]))
    if aoi_bits:
        print(f"  aoi limits:  {'; '.join(aoi_bits)}")

    print()
    print("  variables:")
    for v in d["variables"]:
        units = f" [{v['units']}]" if v["units"] else ""
        print(f"    - {v['name']}: {v['type']}{units}")
        if v["description"]:
            print(f"        {' '.join(v['description'])[:200]}")
        if v["reference_table_total_rows"]:
            print(
                f"        reference_table: {v['reference_table_total_rows']} rows; preview:"
            )
            for row in v["reference_table"]:
                print(f"          {row}")

    if d["description"]:
        print()
        print("  description:")
        for line in d["description"]:
            print(f"    {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_id", help="Cecil dataset UUID")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--full-reference-table",
        action="store_true",
        help="include all reference_table rows (default: preview only)",
    )
    args = parser.parse_args()

    if not os.environ.get("CECIL_API_KEY"):
        print("error: CECIL_API_KEY is not set", file=sys.stderr)
        return 2

    client = cecil.Client()
    ds = client.get_dataset(args.dataset_id)
    payload = _dataset_to_dict(ds, args.full_reference_table)

    if args.json:
        json.dump(payload, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
