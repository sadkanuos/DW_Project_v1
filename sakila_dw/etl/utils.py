"""
Shared utilities: database connections, logging setup, a retry
decorator for transient failures, and helpers for writing to the
etl.batch / etl.load_log / etl.dq_results audit tables.
"""

import functools
import logging
import os
import time

import psycopg2
import pymysql
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sakila_dw")


# ---------------------------------------------------------------
# Connections
# ---------------------------------------------------------------

def get_mysql_connection():
    """Open a connection to the Sakila source database."""
    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_pg_connection():
    """Open a connection to the Postgres warehouse database."""
    return psycopg2.connect(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", 5432)),
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        dbname=os.environ["PG_DB"],
    )


# ---------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------

def retry(max_attempts=3, backoff_seconds=2, exceptions=(Exception,)):
    """
    Retry a function on transient failures with linear backoff.

    Retries up to `max_attempts` times total, sleeping
    `backoff_seconds * attempt_number` between attempts. Re-raises
    the last exception if all attempts are exhausted.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_attempts, exc,
                        )
                        raise
                    wait = backoff_seconds * attempt
                    logger.warning(
                        "%s failed (attempt %d/%d): %s -- retrying in %ds",
                        func.__name__, attempt, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
            raise last_exc  # pragma: no cover - unreachable safeguard

        return wrapper

    return decorator


# ---------------------------------------------------------------
# Audit helpers (etl.batch / etl.load_log / etl.dq_results)
# ---------------------------------------------------------------

def start_batch(pg_conn):
    """Insert a new etl.batch row and return its batch_id."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO etl.batch (status) VALUES ('running') RETURNING batch_id;"
        )
        batch_id = cur.fetchone()[0]
    pg_conn.commit()
    logger.info("Started batch %s", batch_id)
    return batch_id


def finish_batch(pg_conn, batch_id, status):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl.batch
            SET status = %s, finished_at = now()
            WHERE batch_id = %s;
            """,
            (status, batch_id),
        )
    pg_conn.commit()
    logger.info("Finished batch %s: %s", batch_id, status)


def start_step(pg_conn, batch_id, step_name):
    """Insert a 'running' etl.load_log row and return its log_id."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl.load_log (batch_id, step_name, status)
            VALUES (%s, %s, 'running')
            RETURNING log_id;
            """,
            (batch_id, step_name),
        )
        log_id = cur.fetchone()[0]
    pg_conn.commit()
    return log_id


def finish_step(pg_conn, log_id, status, row_count=None, error_message=None):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl.load_log
            SET status = %s, row_count = %s, finished_at = now(), error_message = %s
            WHERE log_id = %s;
            """,
            (status, row_count, error_message, log_id),
        )
    pg_conn.commit()


def run_step(audit_conn, batch_id, step_name, func, *args, **kwargs):
    """
    Run `func(*args, **kwargs)` as an audited step: logs start/finish
    to etl.load_log, records the row count `func` returns, and
    re-raises any exception after logging it as a failure.

    `audit_conn` is the connection used for the etl.load_log writes
    themselves; it's kept out of `func`'s kwargs (which may need
    their own `pg_conn`, `mysql_conn`, etc.) to avoid a name clash.
    """
    log_id = start_step(audit_conn, batch_id, step_name)
    logger.info("Step '%s' starting", step_name)
    try:
        row_count = func(*args, **kwargs)
        finish_step(audit_conn, log_id, "success", row_count=row_count)
        logger.info("Step '%s' succeeded (%s rows)", step_name, row_count)
        return row_count
    except Exception as exc:
        finish_step(audit_conn, log_id, "failed", error_message=str(exc))
        logger.error("Step '%s' failed: %s", step_name, exc)
        raise


def record_dq_result(pg_conn, batch_id, check_name, passed, severity="critical", details=None):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl.dq_results (batch_id, check_name, status, severity, details)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (batch_id, check_name, "pass" if passed else "fail", severity, details),
        )
    pg_conn.commit()
