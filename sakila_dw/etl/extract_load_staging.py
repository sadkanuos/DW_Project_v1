"""
Full-refresh extraction: pull each source table (or flattened join)
from MySQL, truncate the matching Postgres staging table, and bulk
load the fresh rows using generators for memory efficiency.

All functions include full type hints.
"""

from typing import Any, Dict, Iterator, List, Optional, Set

import psycopg2.extensions
import pymysql.connections
from psycopg2.extras import execute_values

from etl.utils import get_mysql_connection, get_pg_connection, logger, retry, get_config


@retry()
def _extract_from_mysql_generator(
    mysql_conn: pymysql.connections.Connection,
    query: str,
    batch_size: int,
) -> Iterator[List[Dict[str, Any]]]:
    """
    Yield rows in batches from MySQL cursor.
    Uses server-side cursor for memory efficiency with large result sets.

    Args:
        mysql_conn: MySQL connection
        query: SQL query to execute
        batch_size: Number of rows per batch

    Yields:
        List of row dictionaries for each batch
    """
    with mysql_conn.cursor() as cur:
        cur.execute(query)
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            yield rows


def _coerce_value(col: str, value: Any, bool_columns: Set[str]) -> Any:
    """
    Coerce MySQL int booleans to Python bool.
    MySQL has no native boolean type -- PyMySQL returns these as ints (0/1).
    Postgres won't implicitly cast int -> boolean inside a batched INSERT.

    Args:
        col: Column name
        value: Value from MySQL
        bool_columns: Set of column names that should be boolean

    Returns:
        Coerced value (bool if in bool_columns, otherwise unchanged)
    """
    if value is not None and col in bool_columns:
        return bool(value)
    return value


def _load_staging_table(
    pg_conn: psycopg2.extensions.connection,
    table_name: str,
    columns: List[str],
    row_batch_generator: Iterator[List[Dict[str, Any]]],
    bool_columns: Optional[Set[str]] = None,
) -> int:
    """
    Stream rows from generator to PostgreSQL in batches.

    **REFACTORED**: Replaces nested loop approach with generator-based batching.
    - Memory usage: O(batch_size) instead of O(table_size)
    - No recursive loops - processes one batch at a time
    - Avoids building entire values list in memory

    Args:
        pg_conn: PostgreSQL connection
        table_name: Target staging table name (e.g., "staging.customer")
        columns: List of column names in order
        row_batch_generator: Generator yielding batches of row dicts
        bool_columns: Set of column names to coerce to boolean

    Returns:
        Total number of rows loaded
    """
    bool_columns = set(bool_columns or [])
    with pg_conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table_name};")

        total_rows = 0
        for batch in row_batch_generator:
            batch_values = [
                tuple(
                    bool(row[col])
                    if col in bool_columns and row[col] is not None
                    else row[col]
                    for col in columns
                )
                for row in batch
            ]

            if batch_values:  # Skip empty batches
                col_list = ", ".join(columns)
                execute_values(
                    cur,
                    f"INSERT INTO {table_name} ({col_list}) VALUES %s;",
                    batch_values,
                )
                total_rows += len(batch_values)

        pg_conn.commit()
        return total_rows


def load_all_staging_tables(
    mysql_conn: Optional[pymysql.connections.Connection] = None,
    pg_conn: Optional[psycopg2.extensions.connection] = None,
) -> int:
    """
    Extract every configured table from MySQL and reload it into the
    matching Postgres staging table using generators for memory efficiency.

    Returns total row count loaded.
    Opens/closes its own connections if none are passed in.

    Args:
        mysql_conn: Optional MySQL connection (created if None)
        pg_conn: Optional PostgreSQL connection (created if None)

    Returns:
        Total number of rows loaded across all staging tables
    """
    config = get_config()
    own_mysql = mysql_conn is None
    own_pg = pg_conn is None
    mysql_conn = mysql_conn or get_mysql_connection()
    pg_conn = pg_conn or get_pg_connection()

    # Load staging table config from YAML
    staging_config = config.staging_config

    total_rows = 0
    try:
        for table_name, table_def in staging_config.items():
            columns = table_def["columns"]
            bool_columns = set(table_def.get("bool_columns", []))
            batch_size = table_def.get("batch_size", config.batch.size)

            # Use generator to stream rows in batches
            row_generator = _extract_from_mysql_generator(
                mysql_conn, table_def["query"], batch_size
            )

            row_count = _load_staging_table(
                pg_conn, f"staging.{table_name}", columns, row_generator, bool_columns
            )
            logger.info(
                "Loaded staging.%s: %d rows (batch_size=%d)",
                table_name,
                row_count,
                batch_size,
            )
            total_rows += row_count
        return total_rows
    finally:
        if own_mysql:
            mysql_conn.close()
        if own_pg:
            pg_conn.close()
