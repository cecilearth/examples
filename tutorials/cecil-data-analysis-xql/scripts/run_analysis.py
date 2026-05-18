#!/usr/bin/env python
"""Run an xarray-sql query against a Cecil subscription.

Loads the subscription's xarray Dataset, registers it under a table name
derived from the dataset name, registers every variable's reference_table
as `ref_<varname>`, runs the SQL, and writes:

  - result.csv               raw rows
  - result.md                Markdown table + the SQL that was run
  - result.png               chart, when the result has a plottable shape

Also prints a short Markdown summary on stdout so the calling skill can show
the answer immediately without re-reading files.

The main table is named after the dataset (e.g. ``land_cover_9_class``
for "Impact Observatory — Land Cover 9-Class").  Pass ``--table-name``
to override.

Usage:
    uv run python scripts/run_analysis.py \\
        --subscription <subscription_id> \\
        --sql 'SELECT DISTINCT land_cover_class FROM land_cover_9_class'

    # Vector datasets (IBAT family — protected areas, KBA, species ranges):
    uv run python scripts/run_analysis.py --vector \\
        --subscription <subscription_id> \\
        --sql 'SELECT * FROM wdpa_protected_areas LIMIT 5'

    uv run python scripts/run_analysis.py \\
        --subscription <subscription_id> \\
        --sql-file query.sql \\
        --output-dir ./out
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import cecil
import pandas as pd
import xarray_sql as xql

from _env import load_dotenv
load_dotenv()


def _to_table_name(dataset_name: str) -> str:
    """Turn a dataset name like 'Impact Observatory — Land Cover 9-Class'
    into a valid SQL identifier like 'land_cover_9_class'."""
    # Strip provider prefix before the em-dash / double-hyphen
    if "—" in dataset_name:
        dataset_name = dataset_name.split("—", 1)[1]
    elif " - " in dataset_name:
        dataset_name = dataset_name.split(" - ", 1)[1]
    name = dataset_name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")


def _read_sql(args) -> str:
    if args.sql and args.sql_file:
        raise SystemExit("error: pass either --sql or --sql-file, not both")
    if args.sql:
        return args.sql
    if args.sql_file:
        return Path(args.sql_file).read_text()
    raise SystemExit("error: --sql or --sql-file is required")


def _build_context(
    client: cecil.Client,
    subscription_id: str,
    table_name_override: str | None = None,
    vector: bool = False,
):
    """Load the subscription, register the dataset table and every reference_table.

    raster (default): load_xarray + XarrayContext.from_dataset
    vector (--vector): load_dataframe + XarrayContext.from_pandas
    """
    if vector:
        df = client.load_dataframe(subscription_id)
        dataset_id = df.attrs.get("dataset_id")
        dataset_name = df.attrs.get("dataset_name", "")
    else:
        ds = client.load_xarray(subscription_id)
        dataset_id = ds.attrs.get("dataset_id")
        dataset_name = ds.attrs.get("dataset_name", "")

    # Derive table name: explicit override > dataset name > fallback
    if table_name_override:
        tbl = table_name_override
    elif dataset_name:
        tbl = _to_table_name(dataset_name)
    else:
        tbl = "cecil"

    ctx = xql.XarrayContext()
    if vector:
        ctx.from_pandas(df, tbl)
        data = df
    else:
        ctx.from_dataset(tbl, ds)
        data = ds

    registered_refs: list[str] = []
    if dataset_id:
        try:
            dataset = client.get_dataset(dataset_id)
        except Exception as e:
            print(
                f"warn: could not fetch dataset metadata ({e}); reference tables not registered",
                file=sys.stderr,
            )
        else:
            for var in dataset.variables:
                if var.reference_table:
                    ref_name = f"ref_{var.name}"
                    ctx.from_pandas(pd.DataFrame(var.reference_table), ref_name)
                    registered_refs.append(ref_name)
    return data, ctx, tbl, registered_refs


def _save_outputs(df: pd.DataFrame, sql: str, refs: list[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "result.csv"
    df.to_csv(csv_path, index=False)

    md_path = out_dir / "result.md"
    with md_path.open("w") as f:
        f.write("# Cecil analysis result\n\n")
        f.write("## SQL\n\n```sql\n")
        f.write(sql.strip())
        f.write("\n```\n\n")
        if refs:
            f.write(f"Reference tables registered: `{'`, `'.join(refs)}`\n\n")
        f.write(f"Rows: **{len(df)}**\n\n")
        if len(df) > 0:
            preview = df.head(50)
            f.write(preview.to_markdown(index=False))
            f.write("\n")
            if len(df) > 50:
                f.write(f"\n_… {len(df) - 50} more rows in result.csv_\n")
        else:
            f.write("_(empty result)_\n")


def _maybe_chart(df: pd.DataFrame, out_dir: Path) -> Path | None:
    """Best-effort chart. Returns the path written, or None if nothing plotted."""
    if df.empty:
        return None

    # Lazy import — matplotlib pulls in a lot of state
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cols = list(df.columns)
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    chart_path = out_dir / "result.png"

    # 1) Time series: a `time`-ish column + at least one numeric measure
    time_col = next(
        (c for c in cols if c.lower() in {"time", "timestamp", "date", "year"}), None
    )
    if time_col and numeric_cols:
        measure_cols = [c for c in numeric_cols if c != time_col][:5]
        if measure_cols:
            fig, ax = plt.subplots(figsize=(8, 4))
            for c in measure_cols:
                ax.plot(df[time_col], df[c], marker="o", label=c)
            ax.set_xlabel(time_col)
            ax.set_ylabel(", ".join(measure_cols))
            ax.legend()
            ax.set_title("Cecil time series")
            fig.autofmt_xdate()
            fig.tight_layout()
            fig.savefig(chart_path, dpi=120)
            plt.close(fig)
            return chart_path

    # 2) Spatial scatter / heatmap: x + y + numeric measure
    if "x" in cols and "y" in cols and numeric_cols:
        measure = next((c for c in numeric_cols if c not in ("x", "y")), None)
        if measure is not None:
            fig, ax = plt.subplots(figsize=(6, 5))
            sc = ax.scatter(df["x"], df["y"], c=df[measure], s=4, cmap="viridis")
            ax.set_xlabel("x")
            ax.set_ylabel("y")
            ax.set_title(f"Cecil spatial: {measure}")
            fig.colorbar(sc, ax=ax, label=measure)
            fig.tight_layout()
            fig.savefig(chart_path, dpi=120)
            plt.close(fig)
            return chart_path

    # 3) Bar chart: a single label column + a single numeric column, small N
    if len(cols) == 2 and len(numeric_cols) == 1 and len(df) <= 30:
        label_col = next(c for c in cols if c not in numeric_cols)
        measure = numeric_cols[0]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(df[label_col].astype(str), df[measure])
        ax.set_xlabel(label_col)
        ax.set_ylabel(measure)
        ax.set_title(f"Cecil: {measure} by {label_col}")
        # Rotate categorical labels so long names don't collide
        for label in ax.get_xticklabels():
            label.set_rotation(30)
            label.set_horizontalalignment("right")
        fig.tight_layout()
        fig.savefig(chart_path, dpi=120)
        plt.close(fig)
        return chart_path

    return None


def _print_summary(df: pd.DataFrame, sql: str, table_name: str, chart: Path | None, out_dir: Path) -> None:
    print("## Cecil analysis")
    print()
    print(f"**Table:** `{table_name}`")
    print()
    print("```sql")
    print(sql.strip())
    print("```")
    print()
    print(f"**Rows:** {len(df)}")
    print()
    if not df.empty:
        preview = df.head(20)
        print(preview.to_markdown(index=False))
        if len(df) > 20:
            print()
            print(f"_…{len(df) - 20} more rows in {out_dir / 'result.csv'}_")
    else:
        print("_(empty result)_")
    print()
    print(f"Saved: `{out_dir / 'result.csv'}`, `{out_dir / 'result.md'}`"
          + (f", `{chart}`" if chart else " (no chart generated)"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True, help="Cecil subscription_id")
    parser.add_argument("--sql", help="SQL string to run against the dataset table")
    parser.add_argument("--sql-file", help="File containing the SQL to run")
    parser.add_argument(
        "--table-name",
        default=None,
        help="SQL table name for the dataset (default: derived from dataset name)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory to write result.csv / result.md / result.png (default: cwd)",
    )
    parser.add_argument(
        "--vector",
        action="store_true",
        help="Treat this subscription as vector (use load_dataframe instead of load_xarray)",
    )
    args = parser.parse_args()

    if not os.environ.get("CECIL_API_KEY"):
        print("error: CECIL_API_KEY is not set", file=sys.stderr)
        return 2

    sql = _read_sql(args)
    out_dir = Path(args.output_dir)

    client = cecil.Client()
    _, ctx, tbl, refs = _build_context(client, args.subscription, args.table_name, args.vector)

    result = ctx.sql(sql)
    df = result.to_pandas()

    _save_outputs(df, sql, refs, out_dir)
    chart = _maybe_chart(df, out_dir)
    _print_summary(df, sql, tbl, chart, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
