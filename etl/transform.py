"""
transform.py
------------

Transforms the Walmart Sales datasets.

Steps:
1. Convert dates
2. Handle missing values
3. Merge datasets
4. Remove duplicate rows
5. Generate a data quality report

Author: Store Pulse Team
"""

import pandas as pd


<<<<<<< HEAD
FEATURE_NUMERIC_COLUMNS = [
    "Temperature",
    "Fuel_Price",
    "MarkDown1",
    "MarkDown2",
    "MarkDown3",
    "MarkDown4",
    "MarkDown5",
    "CPI",
    "Unemployment",
]


def normalise_is_holiday(df):
    """Convert holiday values to booleans, defaulting missing values to False."""

    if "IsHoliday" not in df.columns:
        df["IsHoliday"] = False
        return df

    values = df["IsHoliday"].astype("string").str.strip().str.upper()
    df["IsHoliday"] = values.eq("TRUE").fillna(False).astype(bool)
    return df


=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
# ==========================================================
# Convert Date Columns
# ==========================================================

def convert_dates(train_df, features_df):
    """
    Converts Date columns to datetime format.
    """

<<<<<<< HEAD
    train_df["Date"] = pd.to_datetime(train_df["Date"], errors="coerce")
    features_df["Date"] = pd.to_datetime(features_df["Date"], errors="coerce")

    if train_df["Date"].isna().any() or features_df["Date"].isna().any():
        print("Warning: invalid or missing dates were retained as empty values.")
=======
    train_df["Date"] = pd.to_datetime(train_df["Date"])
    features_df["Date"] = pd.to_datetime(features_df["Date"])
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353

    return train_df, features_df


# ==========================================================
# Handle Missing Values
# ==========================================================

def handle_missing_values(features_df):
    """
<<<<<<< HEAD
    Clean feature values before the merge.

    Feature-only rows are valid: for example, a newly opened store can
    publish operational features before it has sales records or store metadata.
    Missing numeric features are represented as 0 and a missing holiday flag as
    False, so they can be loaded consistently into PostgreSQL.
    """

    features_df = features_df.copy()

    for column in FEATURE_NUMERIC_COLUMNS:
        if column not in features_df.columns:
            features_df[column] = 0.0
        # Coercion turns malformed values (for example, FALSE in Fuel_Price)
        # into missing values instead of failing the entire pipeline.
        features_df[column] = pd.to_numeric(features_df[column], errors="coerce").fillna(0.0)

    features_df = normalise_is_holiday(features_df)
=======
    Replace missing values in MarkDown columns with 0.
    """

    markdown_columns = [
        "MarkDown1",
        "MarkDown2",
        "MarkDown3",
        "MarkDown4",
        "MarkDown5"
    ]

    features_df[markdown_columns] = features_df[markdown_columns].fillna(0)
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353

    return features_df


# ==========================================================
# Merge Datasets
# ==========================================================

def merge_datasets(train_df, stores_df, features_df):
    """
    Merge train, stores and features datasets.
<<<<<<< HEAD

    An outer merge preserves new feature records even if a matching sale has
    not occurred yet.  Such rows have empty Dept/Weekly_Sales values until
    sales data arrives, but are still available in Supabase.
=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    """

    merged_df = pd.merge(
        train_df,
<<<<<<< HEAD
        features_df,
        on=["Store", "Date", "IsHoliday"],
        how="outer"
    )

    merged_df = pd.merge(merged_df, stores_df, on="Store", how="left")

    # A feature can arrive before the store master-data entry.  Keep that row
    # and make the absent metadata explicit instead of discarding it.
    # `Type` is VARCHAR(5) in the Supabase schema, so keep the placeholder
    # compact enough to load without a schema error.
    merged_df["Type"] = merged_df["Type"].fillna("UNK")
    merged_df["Size"] = pd.to_numeric(merged_df["Size"], errors="coerce").fillna(0).astype(int)
=======
        stores_df,
        on="Store",
        how="left"
    )

    merged_df = pd.merge(
        merged_df,
        features_df,
        on=["Store", "Date", "IsHoliday"],
        how="left"
    )
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353

    return merged_df


# ==========================================================
# Remove Duplicates
# ==========================================================

def remove_duplicates(df):
    """
    Removes duplicate rows.
    """

    before = len(df)

    df = df.drop_duplicates()

    after = len(df)

    print(f"\nDuplicates Removed: {before - after}")

    return df


# ==========================================================
# Data Quality Report
# ==========================================================

def quality_report(df):
    """
    Prints a basic quality report.
    """

    print("\n" + "=" * 60)
    print("DATA QUALITY REPORT")
    print("=" * 60)

    print(f"Rows    : {df.shape[0]}")
    print(f"Columns : {df.shape[1]}")

    print("\nMissing Values")
    print(df.isnull().sum())

    print("\nDuplicate Rows")
    print(df.duplicated().sum())

    print("\nData Types")
    print(df.dtypes)

    print("\nDataFrame Info")
    df.info()

    print("\nUnique Store Types")
    print(df["Type"].unique())

    print("=" * 60)


# ==========================================================
# Main Transformation Function
# ==========================================================

def transform_data(train_df, stores_df, features_df):
    """
    Executes the complete transformation pipeline.
    """

    print("=" * 60)
    print("Starting Data Transformation...")
    print("=" * 60)

<<<<<<< HEAD
    # Normalize the shared merge key before converting dates.  A missing or
    # malformed feature flag should not prevent an otherwise valid new feature
    # row from being loaded.
    train_df = normalise_is_holiday(train_df.copy())
    features_df = normalise_is_holiday(features_df.copy())

=======
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    # Convert dates
    train_df, features_df = convert_dates(
        train_df,
        features_df
    )

    # Handle missing values
    features_df = handle_missing_values(features_df)

    # Merge datasets
    final_df = merge_datasets(
        train_df,
        stores_df,
        features_df
    )

    # Remove duplicates
    final_df = remove_duplicates(final_df)

    # Data quality report
    quality_report(final_df)

    print("\nData transformation completed successfully.")

    return final_df


# ==========================================================
# Test Module
# ==========================================================

if __name__ == "__main__":

    from etl.extract import extract_data

    train_df, stores_df, features_df = extract_data()

    final_df = transform_data(
        train_df,
        stores_df,
        features_df
    )

    print("\n" + "=" * 60)
    print("FINAL DATASET PREVIEW")
    print("=" * 60)

<<<<<<< HEAD
    print(final_df.head())
=======
    print(final_df.head())
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
