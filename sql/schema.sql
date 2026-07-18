<<<<<<< HEAD
CREATE TABLE IF NOT EXISTS clean_sales (
=======
DROP TABLE IF EXISTS clean_sales;

CREATE TABLE clean_sales (
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
    Store INTEGER,
    Dept INTEGER,
    Date DATE,
    Weekly_Sales DOUBLE PRECISION,
    IsHoliday BOOLEAN,

    Type VARCHAR(5),
    Size INTEGER,

    Temperature DOUBLE PRECISION,
    Fuel_Price DOUBLE PRECISION,

    MarkDown1 DOUBLE PRECISION,
    MarkDown2 DOUBLE PRECISION,
    MarkDown3 DOUBLE PRECISION,
    MarkDown4 DOUBLE PRECISION,
    MarkDown5 DOUBLE PRECISION,

    CPI DOUBLE PRECISION,
    Unemployment DOUBLE PRECISION
<<<<<<< HEAD
);
=======
);
>>>>>>> a30b0c523790c6320c2dec40042b160b97ca9353
