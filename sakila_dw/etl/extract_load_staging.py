"""
Full-refresh extraction: pull each source table (or flattened join)
from MySQL, truncate the matching Postgres staging table, and bulk
load the fresh rows. Every run reloads everything -- there's no
watermark or delta logic, since Sakila's source doesn't change
between runs and the dataset is small enough that a full reload is
cheap.
"""

from psycopg2.extras import execute_values

from etl.utils import get_mysql_connection, get_pg_connection, logger, retry

# ---------------------------------------------------------------
# Table config: staging table name -> (MySQL extract query, columns)
#
# `columns` must match the staging table's column order exactly
# (excluding any DB-generated columns) and is also asserted against
# in tests/test_transform_logic.py to catch drift between the query
# and the DDL.
# ---------------------------------------------------------------

TABLE_CONFIG = {
    "staging.customer": {
        "columns": [
            "customer_id", "first_name", "last_name", "email",
            "address", "district", "city", "country",
            "active", "create_date", "last_update",
        ],
        # MySQL has no native boolean type -- PyMySQL returns these
        # as plain Python ints (0/1). Postgres won't implicitly cast
        # int -> boolean inside a batched INSERT, so these columns
        # are coerced to real bools before loading.
        "bool_columns": ["active"],
        "query": """
            SELECT
                c.customer_id, c.first_name, c.last_name, c.email,
                a.address, a.district, ci.city, co.country,
                c.active, c.create_date, c.last_update
            FROM customer c
            JOIN address a ON a.address_id = c.address_id
            JOIN city ci ON ci.city_id = a.city_id
            JOIN country co ON co.country_id = ci.country_id;
        """,
    },
    "staging.film": {
        "columns": [
            "film_id", "title", "description", "release_year",
            "rental_rate", "rental_duration", "replacement_cost",
            "rating", "length", "primary_category", "last_update",
        ],
        "query": """
            SELECT
                f.film_id, f.title, f.description, f.release_year,
                f.rental_rate, f.rental_duration, f.replacement_cost,
                f.rating, f.length,
                (SELECT cat.name
                 FROM film_category fc2
                 JOIN category cat ON cat.category_id = fc2.category_id
                 WHERE fc2.film_id = f.film_id
                 ORDER BY fc2.category_id
                 LIMIT 1) AS primary_category,
                f.last_update
            FROM film f;
        """,
    },
    "staging.category": {
        "columns": ["category_id", "name", "last_update"],
        "query": "SELECT category_id, name, last_update FROM category;",
    },
    "staging.film_category": {
        "columns": ["film_id", "category_id", "last_update"],
        "query": "SELECT film_id, category_id, last_update FROM film_category;",
    },
    "staging.store": {
        "columns": [
            "store_id", "manager_staff_id", "address",
            "district", "city", "country", "last_update",
        ],
        "query": """
            SELECT
                s.store_id, s.manager_staff_id,
                a.address, a.district, ci.city, co.country,
                s.last_update
            FROM store s
            JOIN address a ON a.address_id = s.address_id
            JOIN city ci ON ci.city_id = a.city_id
            JOIN country co ON co.country_id = ci.country_id;
        """,
    },
    "staging.staff": {
        "columns": [
            "staff_id", "first_name", "last_name", "email",
            "store_id", "active", "last_update",
        ],
        "bool_columns": ["active"],
        "query": """
            SELECT staff_id, first_name, last_name, email,
                   store_id, active, last_update
            FROM staff;
        """,
    },
    "staging.rental": {
        "columns": [
            "rental_id", "rental_date", "return_date", "inventory_id",
            "customer_id", "staff_id", "film_id", "store_id", "last_update",
        ],
        "query": """
            SELECT
                r.rental_id, r.rental_date, r.return_date, r.inventory_id,
                r.customer_id, r.staff_id, i.film_id, i.store_id, r.last_update
            FROM rental r
            JOIN inventory i ON i.inventory_id = r.inventory_id;
        """,
    },
    "staging.payment": {
        "columns": [
            "payment_id", "customer_id", "staff_id", "rental_id",
            "amount", "payment_date", "last_update",
        ],
        "query": """
            SELECT payment_id, customer_id, staff_id, rental_id,
                   amount, payment_date, last_update
            FROM payment;
        """,
    },
}


@retry(max_attempts=3, backoff_seconds=2)
def _extract_from_mysql(mysql_conn, query):
    with mysql_conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def _coerce_value(col, value, bool_columns):
    if value is not None and col in bool_columns:
        return bool(value)
    return value


def _load_staging_table(pg_conn, table_name, columns, rows, bool_columns=None):
    bool_columns = set(bool_columns or [])
    with pg_conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table_name};")
        if rows:
            values = [
                tuple(_coerce_value(col, row[col], bool_columns) for col in columns)
                for row in rows
            ]
            col_list = ", ".join(columns)
            execute_values(
                cur,
                f"INSERT INTO {table_name} ({col_list}) VALUES %s;",
                values,
            )
    pg_conn.commit()
    return len(rows)


def load_all_staging_tables(mysql_conn=None, pg_conn=None):
    """
    Extract every configured table from MySQL and reload it into the
    matching Postgres staging table. Returns total row count loaded.
    Opens/closes its own connections if none are passed in.
    """
    own_mysql = mysql_conn is None
    own_pg = pg_conn is None
    mysql_conn = mysql_conn or get_mysql_connection()
    pg_conn = pg_conn or get_pg_connection()

    total_rows = 0
    try:
        for table_name, config in TABLE_CONFIG.items():
            rows = _extract_from_mysql(mysql_conn, config["query"])
            row_count = _load_staging_table(
                pg_conn, table_name, config["columns"], rows,
                bool_columns=config.get("bool_columns"),
            )
            logger.info("Loaded %s: %d rows", table_name, row_count)
            total_rows += row_count
        return total_rows
    finally:
        if own_mysql:
            mysql_conn.close()
        if own_pg:
            pg_conn.close()


if __name__ == "__main__":
    load_all_staging_tables()
