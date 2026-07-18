"""
pipeline_logs.py
------------------

Tracks Pipeline Performance & Ops Metrics:
- How long the pipeline update took
- What changed: rows added, rows removed, or rows replaced/updated

This script only OBSERVES and REPORTS -- it doesn't run the ETL itself.
Wrap your pipeline call with this (see example at the bottom) to log
every run automatically.

Output: a JSON log entry per run, appended to pipeline_logs.jsonl,
plus printed to console, plus saved into a `pipeline_logs` table in Supabase.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

<<<<<<< HEAD
from etl.extract import read_features_data, read_store_data, read_train_data
from etl.load import (
    add_cell_change_details,
    build_source_change_report,
    load_previous_source_profile,
    load_previous_source_snapshots,
    profile_sources,
)

=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)
engine = create_engine(DATABASE_URL)

LOG_FILE = Path("pipeline_logs.jsonl")


def get_table_snapshot() -> dict:
    """Lightweight fingerprint of clean_sales, used to detect what changed."""

    with engine.connect() as connection:
        total_rows = connection.execute(text("SELECT COUNT(*) FROM clean_sales")).scalar()
        total_sales = connection.execute(text("SELECT SUM(weekly_sales) FROM clean_sales")).scalar()
        unique_stores = connection.execute(text("SELECT COUNT(DISTINCT store) FROM clean_sales")).scalar()

    return {
        "total_rows": total_rows,
        "total_sales_sum": float(total_sales) if total_sales else 0.0,
        "unique_stores": unique_stores,
    }


<<<<<<< HEAD
def diagnose_change(before: dict, after: dict, source_changes: list[dict]) -> str:
=======
def diagnose_change(before: dict, after: dict) -> str:
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    """
    Classifies what kind of change happened, based on row count and
    sales-sum movement between two snapshots.
    """

    row_delta = after["total_rows"] - before["total_rows"]
    sales_delta = after["total_sales_sum"] - before["total_sales_sum"]

<<<<<<< HEAD
    has_source_changes = any(
        item.get("row_delta")
        or item.get("added_columns")
        or item.get("removed_columns")
        or item.get("changed_columns")
        or item.get("changed_cell_count")
        for item in source_changes
        if item.get("status") != "baseline_created"
    )

    if has_source_changes:
        return "source_data_changed"
=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    if row_delta == 0 and abs(sales_delta) < 0.01:
        return "no_change"
    elif row_delta > 0 and sales_delta > 0:
        return "rows_added"
    elif row_delta < 0:
        return "rows_removed"
    elif row_delta == 0 and abs(sales_delta) > 0.01:
        return "rows_replaced_or_updated"
    else:
        return "mixed_change"


def ensure_pipeline_logs_table():
    """Creates pipeline_logs table if it doesn't exist yet -- safe to call every time."""

    create_sql = text("""
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id                  SERIAL PRIMARY KEY,
            run_label           TEXT NOT NULL,
            run_timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
            duration_seconds    NUMERIC(10,2),
            status              TEXT,
            error_message       TEXT,
            rows_before         INTEGER,
            rows_after          INTEGER,
            row_delta           INTEGER,
<<<<<<< HEAD
            change_type         TEXT,
            changed_files       INTEGER NOT NULL DEFAULT 0,
            changed_cell_count  INTEGER NOT NULL DEFAULT 0,
            source_changes      JSONB NOT NULL DEFAULT '[]'::jsonb
        );
    """)
    alter_sql = text("""
        ALTER TABLE pipeline_logs
            ADD COLUMN IF NOT EXISTS changed_files INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS changed_cell_count INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS source_changes JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)
    with engine.begin() as connection:
        connection.execute(create_sql)
        connection.execute(alter_sql)
=======
            change_type         TEXT
        );
    """)
    with engine.begin() as connection:
        connection.execute(create_sql)
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353


def save_log_to_supabase(log_entry: dict):
    """Inserts one log entry into the pipeline_logs table."""

    insert_sql = text("""
        INSERT INTO pipeline_logs
            (run_label, duration_seconds, status, error_message,
<<<<<<< HEAD
             rows_before, rows_after, row_delta, change_type,
             changed_files, changed_cell_count, source_changes)
        VALUES
            (:run_label, :duration_seconds, :status, :error_message,
             :rows_before, :rows_after, :row_delta, :change_type,
             :changed_files, :changed_cell_count, CAST(:source_changes AS jsonb))
=======
             rows_before, rows_after, row_delta, change_type)
        VALUES
            (:run_label, :duration_seconds, :status, :error_message,
             :rows_before, :rows_after, :row_delta, :change_type)
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    """)

    with engine.begin() as connection:
        connection.execute(insert_sql, {
            "run_label": log_entry["run_label"],
            "duration_seconds": log_entry["duration_seconds"],
            "status": log_entry["status"],
            "error_message": log_entry["error_message"],
            "rows_before": log_entry["rows_before"],
            "rows_after": log_entry["rows_after"],
            "row_delta": log_entry["row_delta"],
            "change_type": log_entry["change_type"],
<<<<<<< HEAD
            "changed_files": log_entry["changed_files"],
            "changed_cell_count": log_entry["changed_cell_count"],
            "source_changes": json.dumps(log_entry["source_changes"]),
=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
        })

    print(f"✓ Also saved to Supabase pipeline_logs table")


<<<<<<< HEAD
def collect_source_changes(previous_profile, previous_snapshots) -> list[dict]:
    """Build detailed source changes, including individual edited-cell samples."""

    source_data = {
        "train.csv": read_train_data(),
        "stores.csv": read_store_data(),
        "features.csv": read_features_data(),
    }
    report = build_source_change_report(profile_sources(source_data), previous_profile)
    add_cell_change_details(report, source_data, previous_snapshots)
    return report


=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
def run_with_logging(pipeline_fn, run_label: str = "manual_run"):
    """
    Wraps a pipeline function call, timing it and logging what changed.

    Usage:
        from etl.load import main as run_etl
        run_with_logging(run_etl, run_label="etl_load")
    """

    print("=" * 60)
    print(f"PIPELINE RUN: {run_label}")
    print("=" * 60)

    before = get_table_snapshot()
<<<<<<< HEAD
    previous_source_profile = load_previous_source_profile()
    previous_source_snapshots = load_previous_source_snapshots(
        ["train.csv", "stores.csv", "features.csv"]
    )
=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    start_time = time.time()
    status = "success"
    error_message = None

    try:
        pipeline_fn()
    except Exception as e:
        status = "failed"
        error_message = str(e)
        print(f"✗ Pipeline failed: {e}")

    duration_seconds = round(time.time() - start_time, 2)
    after = get_table_snapshot()
<<<<<<< HEAD
    source_changes = collect_source_changes(
        previous_source_profile,
        previous_source_snapshots,
    )
    change_type = diagnose_change(before, after, source_changes)
    changed_files = sum(
        1
        for item in source_changes
        if item.get("row_delta")
        or item.get("added_columns")
        or item.get("removed_columns")
        or item.get("changed_columns")
    )
    changed_cell_count = sum(item.get("changed_cell_count", 0) for item in source_changes)
=======
    change_type = diagnose_change(before, after)
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353

    log_entry = {
        "run_label": run_label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration_seconds,
        "status": status,
        "error_message": error_message,
        "rows_before": before["total_rows"],
        "rows_after": after["total_rows"],
        "row_delta": after["total_rows"] - before["total_rows"],
        "change_type": change_type,
<<<<<<< HEAD
        "changed_files": changed_files,
        "changed_cell_count": changed_cell_count,
        "source_changes": source_changes,
=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    }

    # Append to local log file (one JSON object per line)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Also save to Supabase, so the team can query pipeline history there
    ensure_pipeline_logs_table()
    save_log_to_supabase(log_entry)

    print(f"\nDuration     : {duration_seconds}s")
    print(f"Status       : {status}")
    print(f"Rows before  : {before['total_rows']:,}")
    print(f"Rows after   : {after['total_rows']:,}")
    print(f"Row delta    : {log_entry['row_delta']:+,}")
    print(f"Change type  : {change_type}")
<<<<<<< HEAD
    print(f"Files changed: {changed_files}")
    print(f"Cells changed: {changed_cell_count:,}")
=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    print(f"\n✓ Logged to {LOG_FILE}")

    return log_entry


if __name__ == "__main__":
    # Example: time a plain read (no actual pipeline change), just to test logging works
    def dummy_no_op():
        pass

    run_with_logging(dummy_no_op, run_label="test_run")

    print("\n--- To use this for real, wrap your actual pipeline call: ---")
    print("from etl.load import main as run_etl")
<<<<<<< HEAD
    print("run_with_logging(run_etl, run_label='etl_load')")
=======
    print("run_with_logging(run_etl, run_label='etl_load')")
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
