"""
load.py
--------

Loads the transformed Walmart Sales dataset into PostgreSQL.

Steps:
1. Read environment variables
2. Connect to Supabase PostgreSQL
3. Execute schema.sql
4. Transform data
5. Save processed CSV
6. Load data into PostgreSQL
7. Verify data load

Author: Store Pulse Team
"""

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

from etl.extract import extract_data
from etl.transform import transform_data


# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
    raise ValueError("One or more database environment variables are missing.")


# ==========================================================
# Project Paths
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

SQL_FILE = BASE_DIR / "sql" / "schema.sql"

PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(exist_ok=True)

OUTPUT_CSV = PROCESSED_DIR / "clean_sales.csv"
SOURCE_STATE_FILE = PROCESSED_DIR / "source_change_state.json"
SOURCE_SNAPSHOT_DIR = PROCESSED_DIR / "source_snapshots"
CORE_TABLE_COLUMNS = {
    "store",
    "dept",
    "date",
    "weekly_sales",
    "isholiday",
    "type",
    "size",
    "temperature",
    "fuel_price",
    "markdown1",
    "markdown2",
    "markdown3",
    "markdown4",
    "markdown5",
    "cpi",
    "unemployment",
}


# ==========================================================
# Source Change Tracking
# ==========================================================

def column_fingerprint(series: pd.Series) -> str:
    """Create a stable fingerprint for one input column, including nulls."""

    values = pd.util.hash_pandas_object(series, index=False, categorize=True)
    digest = hashlib.sha256()
    digest.update(str(series.dtype).encode("utf-8"))
    digest.update(values.to_numpy().tobytes())
    return digest.hexdigest()


def profile_sources(sources: dict[str, pd.DataFrame]) -> dict:
    """Record row counts and fingerprints for each input file and column."""

    return {
        source_name: {
            "rows": len(df),
            "columns": {
                str(column): {
                    "dtype": str(df[column].dtype),
                    "fingerprint": column_fingerprint(df[column]),
                }
                for column in df.columns
            },
        }
        for source_name, df in sources.items()
    }


def load_previous_source_profile() -> dict | None:
    """Return the profile from the last successful pipeline run, if present."""

    if not SOURCE_STATE_FILE.exists():
        return None

    try:
        return json.loads(SOURCE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("Warning: source-change history could not be read; a new baseline will be saved.")
        return None


def build_source_change_report(current: dict, previous: dict | None) -> list[dict]:
    """Describe file and column-level changes since the last successful run."""

    if previous is None:
        return [{"source": "baseline", "status": "baseline_created"}]

    report = []
    for source_name, current_source in current.items():
        previous_source = previous.get(source_name, {"rows": 0, "columns": {}})
        current_columns = current_source["columns"]
        previous_columns = previous_source["columns"]

        added_columns = sorted(set(current_columns) - set(previous_columns))
        removed_columns = sorted(set(previous_columns) - set(current_columns))
        changed_columns = sorted(
            column
            for column in set(current_columns) & set(previous_columns)
            if current_columns[column] != previous_columns[column]
        )

        report.append({
            "source": source_name,
            "row_delta": current_source["rows"] - previous_source["rows"],
            "added_columns": added_columns,
            "removed_columns": removed_columns,
            "changed_columns": changed_columns,
        })

    return report


def source_snapshot_path(source_name: str) -> Path:
    """Return the one retained, compressed snapshot path for an input file."""

    return SOURCE_SNAPSHOT_DIR / f"{Path(source_name).stem}.parquet"


def load_previous_source_snapshots(source_names) -> dict[str, pd.DataFrame]:
    """Load successful-run snapshots used to locate individual cell edits."""

    snapshots = {}
    for source_name in source_names:
        snapshot_file = source_snapshot_path(source_name)
        if snapshot_file.exists():
            try:
                snapshots[source_name] = pd.read_parquet(snapshot_file)
            except (OSError, ValueError):
                print(f"Warning: could not read the prior snapshot for {source_name}.")
    return snapshots


def display_change_value(value) -> str:
    """Format a changed cell value clearly, including missing values."""

    return "<missing>" if pd.isna(value) else str(value)


def add_cell_change_details(
    report: list[dict],
    current_sources: dict[str, pd.DataFrame],
    previous_snapshots: dict[str, pd.DataFrame],
):
    """Attach counts and samples for edits/replacements at existing cell positions."""

    report_by_source = {item["source"]: item for item in report}
    for source_name, current_df in current_sources.items():
        previous_df = previous_snapshots.get(source_name)
        report_item = report_by_source.get(source_name)
        if previous_df is None or report_item is None:
            continue

        common_columns = [
            column for column in current_df.columns if column in previous_df.columns
        ]
        row_count = min(len(current_df), len(previous_df))
        cell_changes = []
        changed_cell_count = 0

        for column in common_columns:
            before = previous_df[column].iloc[:row_count].reset_index(drop=True)
            after = current_df[column].iloc[:row_count].reset_index(drop=True)
            equal_values = before.eq(after) | (before.isna() & after.isna())
            changed_positions = equal_values[~equal_values].index.tolist()
            changed_cell_count += len(changed_positions)

            for position in changed_positions:
                if len(cell_changes) >= 5:
                    break
                cell_changes.append({
                    # Add one for the zero-based DataFrame index and one for
                    # the CSV header, so this matches the editor's line number.
                    "row": position + 2,
                    "column": column,
                    "before": display_change_value(before.iloc[position]),
                    "after": display_change_value(after.iloc[position]),
                })

        report_item["changed_cell_count"] = changed_cell_count
        report_item["cell_change_samples"] = cell_changes


def print_source_change_report(report: list[dict]):
    """Print a concise, actionable input-change summary at pipeline completion."""

    print("\n" + "=" * 60)
    print("SOURCE CHANGE REPORT")
    print("=" * 60)

    if report[0].get("status") == "baseline_created":
        print("Baseline created. The next successful run will report file and column changes.")
        return

    for item in report:
        changes = []
        if item["row_delta"]:
            changes.append(f"rows {item['row_delta']:+,}")
        if item["added_columns"]:
            changes.append(f"columns added: {', '.join(item['added_columns'])}")
        if item["removed_columns"]:
            changes.append(f"columns removed: {', '.join(item['removed_columns'])}")
        if item["changed_columns"]:
            changes.append(f"values changed in: {', '.join(item['changed_columns'])}")
        if item.get("changed_cell_count"):
            changes.append(f"cells replaced: {item['changed_cell_count']:,}")

        detail = "; ".join(changes) if changes else "no changes"
        print(f"{item['source']}: {detail}")
        for sample in item.get("cell_change_samples", []):
            print(
                f"  line {sample['row']}, {sample['column']}: "
                f"{sample['before']} -> {sample['after']}"
            )


def save_source_profile(profile: dict):
    """Save source state only after the database load succeeds."""

    SOURCE_STATE_FILE.parent.mkdir(exist_ok=True)
    SOURCE_STATE_FILE.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def save_source_snapshots(sources: dict[str, pd.DataFrame]):
    """Keep only the latest compressed input snapshots for cell-level diffs."""

    SOURCE_SNAPSHOT_DIR.mkdir(exist_ok=True)
    for source_name, df in sources.items():
        df.to_parquet(source_snapshot_path(source_name), index=False)


# ==========================================================
# Database Engine
# ==========================================================

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

engine = create_engine(DATABASE_URL)


# ==========================================================
# Test Connection
# ==========================================================

def test_connection():
    """Tests PostgreSQL connection."""

    print("\n" + "=" * 60)
    print("TESTING DATABASE CONNECTION")
    print("=" * 60)

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))

            print("✓ Connected Successfully")
            print(result.fetchone()[0])

    except Exception as e:
        print("✗ Connection Failed")
        raise e


# ==========================================================
# Execute Schema
# ==========================================================

def execute_schema():
    """Executes schema.sql."""

    print("\n" + "=" * 60)
    print("CREATING DATABASE TABLE")
    print("=" * 60)

    try:
        with open(SQL_FILE, "r", encoding="utf-8") as file:
            sql = file.read()

        with engine.begin() as connection:
            connection.execute(text(sql))

        print("✓ Table created successfully")

    except Exception as e:
        print("✗ Failed creating table")
        raise e


# ==========================================================
# Save Processed CSV
# ==========================================================

def save_processed_csv(df):
    """Saves transformed dataset."""

    print("\n" + "=" * 60)
    print("SAVING PROCESSED DATASET")
    print("=" * 60)

    try:
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"✓ Saved to:\n{OUTPUT_CSV}")

    except Exception as e:
        print("✗ Failed to save CSV!")
        raise e


# ==========================================================
# Load Data
# ==========================================================

def infer_postgres_type(series: pd.Series) -> str:
    """Return a safe PostgreSQL type for a newly discovered CSV column."""

    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_numeric_dtype(series):
        return "DOUBLE PRECISION"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    return "TEXT"


def ensure_table_columns(df: pd.DataFrame):
    """Add columns from an evolving CSV before appending data.

    `schema.sql` defines the core analytics fields.  This function preserves
    additional columns that users add to an input CSV, such as a new promotion
    or operational metric, rather than dropping them during the database load.
    """

    existing_columns = {
        column["name"].lower()
        for column in inspect(engine).get_columns("clean_sales")
    }
    identifier_preparer = engine.dialect.identifier_preparer

    with engine.begin() as connection:
        for column_name in df.columns:
            if column_name in existing_columns:
                continue

            if not column_name or len(column_name) > 63:
                raise ValueError(
                    f"Invalid new column name '{column_name}'. PostgreSQL names must be 1-63 characters."
                )

            quoted_name = identifier_preparer.quote(column_name)
            column_type = infer_postgres_type(df[column_name])
            connection.execute(
                text(f"ALTER TABLE clean_sales ADD COLUMN {quoted_name} {column_type}")
            )
            print(f"Added new Supabase column: {column_name} ({column_type})")


def clear_existing_data():
    """Replace table contents without blocking concurrent dashboard reads.

    ``TRUNCATE`` requires an ACCESS EXCLUSIVE lock, so even a long-running
    read from Supabase can cause it to hit the project's statement timeout.
    ``DELETE`` permits ordinary SELECT queries to continue while the next
    snapshot is being prepared.
    """

    with engine.begin() as connection:
        # The table contains a few hundred thousand rows, which can take
        # longer than Supabase's default statement timeout to remove.
        connection.execute(text("SET LOCAL statement_timeout = '120s'"))
        connection.execute(text("DELETE FROM clean_sales"))


def remove_obsolete_dynamic_columns(df: pd.DataFrame):
    """Remove Supabase columns whose user-provided source columns were removed."""

    current_columns = set(df.columns)
    existing_columns = {
        column["name"].lower()
        for column in inspect(engine).get_columns("clean_sales")
    }
    obsolete_columns = existing_columns - CORE_TABLE_COLUMNS - current_columns
    identifier_preparer = engine.dialect.identifier_preparer

    with engine.begin() as connection:
        for column_name in sorted(obsolete_columns):
            quoted_name = identifier_preparer.quote(column_name)
            connection.execute(text(f"ALTER TABLE clean_sales DROP COLUMN {quoted_name}"))
            print(f"âœ“ Removed Supabase column: {column_name}")


def load_to_database(df):
    """Replace table data while retaining dynamically added Supabase columns."""

    print("\n" + "=" * 60)
    print("LOADING DATA INTO POSTGRESQL")
    print("=" * 60)

    try:
        # PostgreSQL uses lowercase identifiers for the existing schema.
        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.lower()

        if df.columns.duplicated().any():
            duplicate_columns = df.columns[df.columns.duplicated()].tolist()
            raise ValueError(f"Duplicate column names after normalization: {duplicate_columns}")

        ensure_table_columns(df)
        remove_obsolete_dynamic_columns(df)
        # The table structure persists, but the data is a fresh snapshot of
        # the source CSVs. This prevents duplicate records across runs.
        clear_existing_data()

        df.to_sql(
            name="clean_sales",
            con=engine,
            if_exists="append",
            index=False,
            chunksize=500
        )

        print(f"✓ {len(df):,} rows inserted.")

    except Exception as e:
        print("✗ Data load failed")
        print(type(e))
        print(str(e))
        raise

   
# ==========================================================
# Verify Load
# ==========================================================

def verify_load():
    """Verifies inserted rows."""

    print("\n" + "=" * 60)
    print("VERIFYING DATA")
    print("=" * 60)

    with engine.connect() as connection:

        result = connection.execute(
            text("SELECT COUNT(*) FROM clean_sales")
        )

        rows = result.scalar()

    print(f"Rows in database : {rows:,}")


# ==========================================================
# Main Pipeline
# ==========================================================

def main():

    # Step 1
    test_connection()

    # Step 2
    execute_schema()

    # Step 3
    train_df, stores_df, features_df = extract_data()
    source_data = {
        "train.csv": train_df,
        "stores.csv": stores_df,
        "features.csv": features_df,
    }
    source_profile = profile_sources(source_data)
    source_change_report = build_source_change_report(
        source_profile,
        load_previous_source_profile(),
    )
    add_cell_change_details(
        source_change_report,
        source_data,
        load_previous_source_snapshots(source_data),
    )

    # Step 4
    final_df = transform_data(
        train_df,
        stores_df,
        features_df
    )

    # Step 5
    save_processed_csv(final_df)

    # Step 6
    load_to_database(final_df)

    # Step 7
    verify_load()

    # Save the comparison baseline only after all load steps complete.
    save_source_profile(source_profile)
    save_source_snapshots(source_data)
    print_source_change_report(source_change_report)

    print("\n" + "=" * 60)
    print("ETL PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":
    main()
