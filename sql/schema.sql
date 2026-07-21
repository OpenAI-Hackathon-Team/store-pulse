CREATE TABLE IF NOT EXISTS clean_sales (
    Store INTEGER,
    Dept INTEGER,
    Date DATE,
    Weekly_Sales DOUBLE PRECISION,
    IsHoliday BOOLEAN,

    Type VARCHAR(5),
    Size INTEGER,
    City TEXT,

    Temperature DOUBLE PRECISION,
    Fuel_Price DOUBLE PRECISION,

    MarkDown1 DOUBLE PRECISION,
    MarkDown2 DOUBLE PRECISION,
    MarkDown3 DOUBLE PRECISION,
    MarkDown4 DOUBLE PRECISION,
    MarkDown5 DOUBLE PRECISION,

    CPI DOUBLE PRECISION,
    Unemployment DOUBLE PRECISION
);

-- `CREATE TABLE IF NOT EXISTS` does not add a column to tables created by an
-- older version of this schema. Migrate those tables without taking an
-- unnecessary table lock when the column already exists.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'clean_sales'
          AND column_name = 'city'
    ) THEN
        ALTER TABLE clean_sales ADD COLUMN City TEXT;
    END IF;
END $$;
