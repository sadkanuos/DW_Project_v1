-- ============================================================
-- 01_staging_ddl.sql
-- Staging tables: truncated and reloaded in full on every run.
-- Address/city/country and film/category are flattened at
-- extract time so staging is already close to mart shape.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.customer (
    customer_id   INT PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT,
    address       TEXT,
    district      TEXT,
    city          TEXT,
    country       TEXT,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    create_date   TIMESTAMP,
    last_update   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.film (
    film_id           INT PRIMARY KEY,
    title             TEXT NOT NULL,
    description       TEXT,
    release_year      INT,
    rental_rate       NUMERIC(5,2),
    rental_duration   INT,
    replacement_cost  NUMERIC(6,2),
    rating            TEXT,
    length            INT,
    primary_category  TEXT,
    last_update       TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.category (
    category_id   INT PRIMARY KEY,
    name          TEXT NOT NULL,
    last_update   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.film_category (
    film_id       INT NOT NULL,
    category_id   INT NOT NULL,
    last_update   TIMESTAMP,
    PRIMARY KEY (film_id, category_id)
);

CREATE TABLE IF NOT EXISTS staging.store (
    store_id            INT PRIMARY KEY,
    manager_staff_id    INT,
    address             TEXT,
    district            TEXT,
    city                TEXT,
    country             TEXT,
    last_update         TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.staff (
    staff_id      INT PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT,
    store_id      INT,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    last_update   TIMESTAMP
);

-- film_id / store_id are resolved via inventory at extract time
-- so the mart doesn't need to join through inventory at all.
CREATE TABLE IF NOT EXISTS staging.rental (
    rental_id     INT PRIMARY KEY,
    rental_date   TIMESTAMP NOT NULL,
    return_date   TIMESTAMP,
    inventory_id  INT,
    customer_id   INT NOT NULL,
    staff_id      INT NOT NULL,
    film_id       INT NOT NULL,
    store_id      INT NOT NULL,
    last_update   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staging.payment (
    payment_id    INT PRIMARY KEY,
    customer_id   INT NOT NULL,
    staff_id      INT NOT NULL,
    rental_id     INT,
    amount        NUMERIC(6,2) NOT NULL,
    payment_date  TIMESTAMP NOT NULL,
    last_update   TIMESTAMP
);
