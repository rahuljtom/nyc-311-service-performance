"""Build the DuckDB database from the raw CSV files and export every result table.

Usage:
    python src/pipeline.py --raw-glob "data/raw/311_2024_*.csv" --db data/311.duckdb --out outputs/tables
"""
import argparse
import sys
from pathlib import Path

import duckdb

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
RESULT_TABLE_PATTERN = "^r[0-9]{2}_"


def build(con, raw_glob):
    """Run every numbered SQL file in order against an open DuckDB connection."""
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        con.execute(path.read_text().replace("__RAW_GLOB__", raw_glob))


def result_tables(con):
    rows = con.execute(
        "select table_name from information_schema.tables "
        "where regexp_matches(table_name, ?) order by table_name",
        [RESULT_TABLE_PATTERN],
    ).fetchall()
    return [r[0] for r in rows]


def export(con, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in result_tables(con):
        target = out_dir / (name + ".csv")
        con.execute(f"copy {name} to '{target}' (header, delimiter ',')")
    return result_tables(con)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-glob", default="data/raw/311_*.csv")
    ap.add_argument("--db", default="data/311.duckdb")
    ap.add_argument("--out", default="outputs/tables")
    args = ap.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    if Path(args.db).exists():
        Path(args.db).unlink()
    con = duckdb.connect(args.db)
    build(con, args.raw_glob)
    for name in export(con, args.out):
        print("wrote", name)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
