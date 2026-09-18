-- ============================================================
-- 02_mart_ddl.sql
-- Star schema: dimensions (overwrite, one row per natural key),
-- a bridge table for film<->category, and two fact tables.
-- Surrogate keys equal the natural key throughout, since each
-- dimension holds at most one row per natural key.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS mart;

-- ---------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mart.dim_customer (
    customer_sk   INT PRIMARY KEY,      -- = staging.customer.customer_id
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT,
    address       TEXT,
    district      TEXT,
    city          TEXT,
    country       TEXT,
    active        BOOLEAN NOT NULL,
    create_date   TIMESTAMP,
    loaded_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mart.dim_film (
    film_sk           INT PRIMARY KEY,  -- = staging.film.film_id
    title             TEXT NOT NULL,
    description       TEXT,
    release_year      INT,
    rental_rate       NUMERIC(5,2),
    rental_duration   INT,
    replacement_cost  NUMERIC(6,2),
    rating            TEXT,
    length            INT,
    primary_category  TEXT,
    loaded_at         TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mart.dim_store (
    store_sk           INT PRIMARY KEY,  -- = staging.store.store_id
    manager_staff_sk   INT,
    address            TEXT,
    district           TEXT,
    city               TEXT,
    country            TEXT,
    loaded_at          TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mart.dim_staff (
    staff_sk      INT PRIMARY KEY,  -- = staging.staff.staff_id
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT,
    store_sk      INT,
    active        BOOLEAN NOT NULL,
    loaded_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mart.dim_category (
    category_id   INT PRIMARY KEY,
    name          TEXT NOT NULL,
    loaded_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mart.dim_date (
    date_key      INT PRIMARY KEY,      -- YYYYMMDD
    full_date     DATE NOT NULL UNIQUE,
    year          INT NOT NULL,
    quarter       INT NOT NULL,
    month         INT NOT NULL,
    month_name    TEXT NOT NULL,
    day           INT NOT NULL,
    day_name      TEXT NOT NULL,
    week_of_year  INT NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

-- ---------------------------------------------------------------
-- Bridge: many-to-many film <-> category
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mart.bridge_film_category (
    film_sk       INT NOT NULL REFERENCES mart.dim_film(film_sk),
    category_id   INT NOT NULL REFERENCES mart.dim_category(category_id),
    PRIMARY KEY (film_sk, category_id)
);

-- ---------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS mart.fact_rental (
    rental_sk         BIGSERIAL PRIMARY KEY,
    rental_id         INT NOT NULL UNIQUE,   -- natural key, for idempotent reload
    rental_date_key   INT NOT NULL REFERENCES mart.dim_date(date_key),
    customer_sk       INT NOT NULL REFERENCES mart.dim_customer(customer_sk),
    film_sk           INT NOT NULL REFERENCES mart.dim_film(film_sk),
    store_sk          INT NOT NULL REFERENCES mart.dim_store(store_sk),
    staff_sk          INT NOT NULL REFERENCES mart.dim_staff(staff_sk),
    rental_date       TIMESTAMP NOT NULL,
    return_date       TIMESTAMP,
    rental_duration_days NUMERIC(5,2)
    -- If this table grows large, partition by rental_date_key
    -- (e.g. RANGE partitioning by year) — Sakila-scale data
    -- doesn't need it, but a real live rental business would.
);

CREATE INDEX IF NOT EXISTS ix_fact_rental_customer ON mart.fact_rental(customer_sk);
CREATE INDEX IF NOT EXISTS ix_fact_rental_film ON mart.fact_rental(film_sk);
CREATE INDEX IF NOT EXISTS ix_fact_rental_date ON mart.fact_rental(rental_date_key);

CREATE TABLE IF NOT EXISTS mart.fact_payment (
    payment_sk        BIGSERIAL PRIMARY KEY,
    payment_id        INT NOT NULL UNIQUE,   -- natural key, for idempotent reload
    payment_date_key  INT NOT NULL REFERENCES mart.dim_date(date_key),
    customer_sk       INT NOT NULL REFERENCES mart.dim_customer(customer_sk),
    staff_sk          INT NOT NULL REFERENCES mart.dim_staff(staff_sk),
    rental_id         INT,
    amount            NUMERIC(6,2) NOT NULL,
    payment_date      TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_fact_payment_customer ON mart.fact_payment(customer_sk);
CREATE INDEX IF NOT EXISTS ix_fact_payment_date ON mart.fact_payment(payment_date_key);
