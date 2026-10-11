"""
Transform staging tables into the mart star schema.
All configurations for dimensions and bridge tables are loaded from YAML.
All functions include full type hints.
"""

import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extensions
from psycopg2.extras import execute_values

from etl.utils import get_pg_connection, logger, get_config


def _upsert_dim(
    pg_conn: psycopg2.extensions.connection,
    dim_name: str,
    dim_config: Dict[str, Any],
) -> int:
    """
    Generic dimension upsert function using YAML config.

    All dimensions use INSERT ... ON CONFLICT DO UPDATE pattern.
    Surrogate keys equal natural keys.

    Args:
        pg_conn: PostgreSQL connection
        dim_name: Name of the dimension table (e.g., 'dim_customer')
        dim_config: Configuration dict from YAML with keys:
            - source_table: Source staging table
            - select_columns: Columns to select
            - pk_column: Primary key column
            - update_set: ON CONFLICT update set clause

    Returns:
        Number of rows in the dimension after upsert
    """
    with pg_conn.cursor() as cur:
        source_table = dim_config["source_table"]
        select_columns = dim_config["select_columns"]
        pk_column = dim_config["pk_column"]
        update_set = dim_config["update_set"]

        cur.execute(f"""
            INSERT INTO mart.{dim_name} ({select_columns})
            SELECT {select_columns} FROM {source_table}
            ON CONFLICT ({pk_column}) DO UPDATE SET {update_set};
        """)
        cur.execute(f"SELECT COUNT(*) FROM mart.{dim_name};")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def _load_bridge(
    pg_conn: psycopg2.extensions.connection,
    bridge_name: str,
    bridge_config: Dict[str, Any],
) -> int:
    """
    Generic bridge table loader using YAML config.

    Args:
        pg_conn: PostgreSQL connection
        bridge_name: Name of the bridge table (e.g., 'bridge_film_category')
        bridge_config: Configuration dict from YAML with keys:
            - source_table: Source staging table
            - select_columns: Columns to select from source
            - target_columns: Columns in target bridge table
            - truncate: Whether to truncate before loading

    Returns:
        Number of rows loaded into bridge table
    """
    with pg_conn.cursor() as cur:
        if bridge_config.get("truncate", True):
            cur.execute(f"TRUNCATE TABLE mart.{bridge_name};")

        source_table = bridge_config["source_table"]
        select_columns = bridge_config["select_columns"]
        target_columns = bridge_config["target_columns"]

        cur.execute(f"""
            INSERT INTO mart.{bridge_name} ({target_columns})
            SELECT {select_columns} FROM {source_table};
        """)
        cur.execute(f"SELECT COUNT(*) FROM mart.{bridge_name};")
        count = cur.fetchone()[0]
    pg_conn.commit()
    return count


def generate_date_rows(
    start_date: datetime.date, end_date: datetime.date
) -> List[Tuple[Any, ...]]:
    """
    Return a list of dim_date row tuples covering [start_date, end_date] inclusive.
    Pure function -- exercised directly in unit tests.

    Args:
        start_date: First date to include
        end_date: Last date to include

    Returns:
        List of tuples, each representing a row in dim_date
    """
    rows: List[Tuple[Any, ...]] = []
    current = start_date
    one_day = datetime.timedelta(days=1)
    while current <= end_date:
        date_key = int(current.strftime("%Y%m%d"))
        rows.append(
            (
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
            )
        )
        current += one_day
    return rows


def _load_dim_date(pg_conn: psycopg2.extensions.connection) -> int:
    """
    Load dim_date table by generating rows from min/max dates in staging.
    This is a special case - generated in Python, not from staging tables.

    Args:
        pg_conn: PostgreSQL connection

    Returns:
        Number of rows loaded into dim_date
    """
    config = get_config()
    mart_config = config.mart_config
    dim_date_config = mart_config.get("dim_date", {})

    start_date_query = dim_date_config.get(
        "start_date_query",
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
    """,
    )

    with pg_conn.cursor() as cur:
        cur.execute(start_date_query)
        min_date, max_date = cur.fetchone()
        if min_date is None or max_date is None:
            return 0

        rows = generate_date_rows(min_date, max_date)
        cur.execute("TRUNCATE TABLE mart.dim_date CASCADE;")

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


def _load_fact_rental(pg_conn: psycopg2.extensions.connection) -> int:
    """Load fact_rental table from staging with surrogate key resolution."""
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


def _load_fact_payment(pg_conn: psycopg2.extensions.connection) -> int:
    """Load fact_payment table from staging with surrogate key resolution."""
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


def load_all_dims(pg_conn: Optional[psycopg2.extensions.connection] = None) -> int:
    """
    Load all dimensions and bridge tables using config from YAML.

    Args:
        pg_conn: Optional PostgreSQL connection (created if None)

    Returns:
        Total number of rows loaded across all dimensions
    """
    config = get_config()
    own_pg = pg_conn is None
    pg_conn = pg_conn or get_pg_connection()

    try:
        counts: Dict[str, int] = {}
        mart_config = config.mart_config

        # Load dimensions
        for dim_name, dim_config in mart_config.get("dimensions", {}).items():
            count = _upsert_dim(pg_conn, dim_name, dim_config)
            counts[dim_name] = count
            logger.info("Loaded %s: %d rows", dim_name, count)

        # Load bridge tables
        for bridge_name, bridge_config in mart_config.get("bridge_tables", {}).items():
            count = _load_bridge(pg_conn, bridge_name, bridge_config)
            counts[bridge_name] = count
            logger.info("Loaded %s: %d rows", bridge_name, count)

        # Load date dimension (special case - generated in Python)
        count = _load_dim_date(pg_conn)
        counts["dim_date"] = count
        logger.info("Loaded dim_date: %d rows", count)

        return sum(counts.values())
    finally:
        if own_pg:
            pg_conn.close()


def load_all_facts(pg_conn: Optional[psycopg2.extensions.connection] = None) -> int:
    """
    Load all fact tables.

    Args:
        pg_conn: Optional PostgreSQL connection (created if None)

    Returns:
        Total number of rows loaded across all fact tables
    """
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
