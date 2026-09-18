"""
Transform staging tables into the mart star schema.

All dimensions are overwrite (one row per natural key, upserted via
INSERT ... ON CONFLICT DO UPDATE). Facts are loaded from staging with
surrogate keys resolved by straightforward joins (trivial here since
surrogate keys equal natural keys, but written as real joins so the
pattern generalizes if that ever changes) and de-duplicated on their
natural key so reruns don't create duplicate fact rows.
"""

import datetime

from etl.utils import get_pg_connection, logger


def _upsert_dim_customer(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mart.dim_customer (
                customer_sk, first_name, last_name, email,
                address, district, city, country, active, create_date
            )
            SELECT
                customer_id, first_name, last_name, email,
                address, district, city, country, active, create_date
            FROM staging.customer
            ON CONFLICT (customer_sk) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name  = EXCLUDED.last_name,
                email      = EXCLUDED.email,
                address    = EXCLUDED.address,
                district   = EXCLUDED.district,
                city       = EXCLUDED.city,
                country    = EXCLUDED.country,
                active     = EXCLUDED.active,
                create_date = EXCLUDED.create_date,
                loaded_at  = now();
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.dim_customer;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _upsert_dim_film(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mart.dim_film (
                film_sk, title, description, release_year, rental_rate,
                rental_duration, replacement_cost, rating, length, primary_category
            )
            SELECT
                film_id, title, description, release_year, rental_rate,
                rental_duration, replacement_cost, rating, length, primary_category
            FROM staging.film
            ON CONFLICT (film_sk) DO UPDATE SET
                title             = EXCLUDED.title,
                description       = EXCLUDED.description,
                release_year      = EXCLUDED.release_year,
                rental_rate       = EXCLUDED.rental_rate,
                rental_duration   = EXCLUDED.rental_duration,
                replacement_cost  = EXCLUDED.replacement_cost,
                rating            = EXCLUDED.rating,
                length            = EXCLUDED.length,
                primary_category  = EXCLUDED.primary_category,
                loaded_at         = now();
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.dim_film;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _upsert_dim_category(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mart.dim_category (category_id, name)
            SELECT category_id, name FROM staging.category
            ON CONFLICT (category_id) DO UPDATE SET
                name = EXCLUDED.name,
                loaded_at = now();
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.dim_category;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _upsert_dim_store(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mart.dim_store (
                store_sk, manager_staff_sk, address, district, city, country
            )
            SELECT store_id, manager_staff_id, address, district, city, country
            FROM staging.store
            ON CONFLICT (store_sk) DO UPDATE SET
                manager_staff_sk = EXCLUDED.manager_staff_sk,
                address   = EXCLUDED.address,
                district  = EXCLUDED.district,
                city      = EXCLUDED.city,
                country   = EXCLUDED.country,
                loaded_at = now();
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.dim_store;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _upsert_dim_staff(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mart.dim_staff (
                staff_sk, first_name, last_name, email, store_sk, active
            )
            SELECT staff_id, first_name, last_name, email, store_id, active
            FROM staging.staff
            ON CONFLICT (staff_sk) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name  = EXCLUDED.last_name,
                email      = EXCLUDED.email,
                store_sk   = EXCLUDED.store_sk,
                active     = EXCLUDED.active,
                loaded_at  = now();
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.dim_staff;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _load_bridge_film_category(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE mart.bridge_film_category;")
        cur.execute(
            """
            INSERT INTO mart.bridge_film_category (film_sk, category_id)
            SELECT film_id, category_id FROM staging.film_category;
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.bridge_film_category;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


# ---------------------------------------------------------------
# dim_date: generated in Python, not sourced from staging.
# ---------------------------------------------------------------

def generate_date_rows(start_date, end_date):
    """
    Return a list of dim_date row tuples covering [start_date, end_date]
    inclusive. Pure function -- exercised directly in unit tests.
    """
    rows = []
    current = start_date
    one_day = datetime.timedelta(days=1)
    while current <= end_date:
        date_key = int(current.strftime("%Y%m%d"))
        rows.append((
            date_key,
            current,
            current.year,
            (current.month - 1) // 3 + 1,
            current.month,
            current.strftime("%B"),
            current.day,
            current.strftime("%A"),
            int(current.strftime("%W")),
            current.weekday() >= 5,
        ))
        current += one_day
    return rows


def _load_dim_date(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                LEAST(MIN(rental_date)::date, MIN(payment_date)::date),
                GREATEST(
                    COALESCE(MAX(rental_date)::date, MAX(payment_date)::date),
                    COALESCE(MAX(return_date)::date, MAX(payment_date)::date)
                )
            FROM (
                SELECT rental_date, return_date, NULL::timestamp AS payment_date FROM staging.rental
                UNION ALL
                SELECT NULL, NULL, payment_date FROM staging.payment
            ) all_dates;
            """
        )
        min_date, max_date = cur.fetchone()
        if min_date is None or max_date is None:
            return 0

        rows = generate_date_rows(min_date, max_date)
        cur.execute("TRUNCATE TABLE mart.dim_date CASCADE;")
        from psycopg2.extras import execute_values
        execute_values(
            cur,
            """
            INSERT INTO mart.dim_date (
                date_key, full_date, year, quarter, month, month_name,
                day, day_name, week_of_year, is_weekend
            ) VALUES %s;
            """,
            rows,
        )
    pg_conn.commit()
    return len(rows)


# ---------------------------------------------------------------
# Facts
# ---------------------------------------------------------------

def _load_fact_rental(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE mart.fact_rental;")
        cur.execute(
            """
            INSERT INTO mart.fact_rental (
                rental_id, rental_date_key, customer_sk, film_sk,
                store_sk, staff_sk, rental_date, return_date,
                rental_duration_days
            )
            SELECT
                r.rental_id,
                CAST(TO_CHAR(r.rental_date, 'YYYYMMDD') AS INT) AS rental_date_key,
                dc.customer_sk,
                df.film_sk,
                ds.store_sk,
                dst.staff_sk,
                r.rental_date,
                r.return_date,
                EXTRACT(EPOCH FROM (r.return_date - r.rental_date)) / 86400.0
            FROM staging.rental r
            JOIN mart.dim_customer dc ON dc.customer_sk = r.customer_id
            JOIN mart.dim_film df ON df.film_sk = r.film_id
            JOIN mart.dim_store ds ON ds.store_sk = r.store_id
            JOIN mart.dim_staff dst ON dst.staff_sk = r.staff_id
            JOIN mart.dim_date dd ON dd.date_key = CAST(TO_CHAR(r.rental_date, 'YYYYMMDD') AS INT);
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.fact_rental;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _load_fact_payment(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE mart.fact_payment;")
        cur.execute(
            """
            INSERT INTO mart.fact_payment (
                payment_id, payment_date_key, customer_sk, staff_sk,
                rental_id, amount, payment_date
            )
            SELECT
                p.payment_id,
                CAST(TO_CHAR(p.payment_date, 'YYYYMMDD') AS INT) AS payment_date_key,
                dc.customer_sk,
                dst.staff_sk,
                p.rental_id,
                p.amount,
                p.payment_date
            FROM staging.payment p
            JOIN mart.dim_customer dc ON dc.customer_sk = p.customer_id
            JOIN mart.dim_staff dst ON dst.staff_sk = p.staff_id
            JOIN mart.dim_date dd ON dd.date_key = CAST(TO_CHAR(p.payment_date, 'YYYYMMDD') AS INT);
            """
        )
        cur.execute("SELECT COUNT(*) FROM mart.fact_payment;")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


# ---------------------------------------------------------------
# Orchestration entry point for this module
# ---------------------------------------------------------------

def load_all_dims(pg_conn=None):
    own_pg = pg_conn is None
    pg_conn = pg_conn or get_pg_connection()
    try:
        counts = {
            "dim_customer": _upsert_dim_customer(pg_conn),
            "dim_film": _upsert_dim_film(pg_conn),
            "dim_category": _upsert_dim_category(pg_conn),
            "dim_store": _upsert_dim_store(pg_conn),
            "dim_staff": _upsert_dim_staff(pg_conn),
            "bridge_film_category": _load_bridge_film_category(pg_conn),
            "dim_date": _load_dim_date(pg_conn),
        }
        for name, count in counts.items():
            logger.info("Loaded %s: %d rows", name, count)
        return sum(counts.values())
    finally:
        if own_pg:
            pg_conn.close()


def load_all_facts(pg_conn=None):
    own_pg = pg_conn is None
    pg_conn = pg_conn or get_pg_connection()
    try:
        counts = {
            "fact_rental": _load_fact_rental(pg_conn),
            "fact_payment": _load_fact_payment(pg_conn),
        }
        for name, count in counts.items():
            logger.info("Loaded %s: %d rows", name, count)
        return sum(counts.values())
    finally:
        if own_pg:
            pg_conn.close()


if __name__ == "__main__":
    load_all_dims()
    load_all_facts()
