"""
models/build.py

Loads raw CSVs into DuckDB, runs the four SQL transformation models in order,
and writes the output tables to data/output/ as CSV files.

The app reads directly from data/output/, so this script must be run
before the app (or use the committed outputs).
"""

import duckdb
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_SAMPLE  = ROOT / "data" / "sample"
DATA_OUTPUT  = ROOT / "data" / "output"
MODELS_DIR   = ROOT / "models"

DATA_OUTPUT.mkdir(exist_ok=True)

SQL_ORDER = [
    "stg_events.sql",
    "fct_channel_performance.sql",
    "fct_geo_performance.sql",
    "fct_creative_performance.sql",
]

OUTPUT_TABLES = [
    "stg_events",
    "fct_channel_performance",
    "fct_geo_performance",
    "fct_creative_performance",
]


def main():
    print("Running DuckDB model pipeline...")

    # DuckDB in-process, no persistent file needed
    con = duckdb.connect()

    # Set working directory so relative paths in SQL resolve correctly
    con.execute(f"SET FILE_SEARCH_PATH='{ROOT}';")

    for sql_file, table in zip(SQL_ORDER, OUTPUT_TABLES):
        sql_path = MODELS_DIR / sql_file
        sql = sql_path.read_text()
        print(f"  Running {sql_file}...")
        con.execute(sql)

        out_path = DATA_OUTPUT / f"{table}.csv"
        con.execute(
            f"COPY {table} TO '{out_path}' (HEADER, DELIMITER ',');"
        )
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"    -> {out_path.name}: {count:,} rows")

    con.close()
    print("Build complete. Outputs in data/output/")


if __name__ == "__main__":
    main()
