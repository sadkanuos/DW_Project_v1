"""Audit helpers for etl.batch / etl.load_log / etl.dq_results."""

import logging
from typing import Any, Callable, Optional

import psycopg2
import psycopg2.extensions

from etl.utils.logging import logger


def start_batch(pg_conn: psycopg2.extensions.connection) -> int:
    """Insert a new etl.batch row and return its batch_id."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO etl.batch (status) VALUES ('running') RETURNING batch_id;"
        )
        batch_id = cur.fetchone()[0]
    pg_conn.commit()
    logger.info("Started batch %s", batch_id)
    return batch_id


def finish_batch(
    pg_conn: psycopg2.extensions.connection, batch_id: int, status: str
) -> None:
    """Update etl.batch row with final status."""
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


def start_step(
    pg_conn: psycopg2.extensions.connection, batch_id: int, step_name: str
) -> int:
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


def finish_step(
    pg_conn: psycopg2.extensions.connection,
    log_id: int,
    status: str,
    row_count: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update etl.load_log row with final status."""
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


def run_step(
    audit_conn: psycopg2.extensions.connection,
    batch_id: int,
    step_name: str,
    func: Callable[..., int],
    *args: Any,
    **kwargs: Any,
) -> int:
    """
    Run `func(*args, **kwargs)` as an audited step: logs start/finish
    to etl.load_log, records the row count `func` returns, and
    re-raises any exception after logging it as a failure.

    `audit_conn` is the connection used for the etl.load_log writes
    themselves; it's kept out of `func`'s kwargs (which may need
    their own `pg_conn`, `mysql_conn`, etc.) to avoid a name clash.

    Args:
        audit_conn: Connection for audit logging
        batch_id: Current batch ID
        step_name: Name of the step being executed
        func: Function to execute (must return int row count)
        *args: Arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Row count returned by func

    Raises:
        Exception: Re-raises any exception from func after logging
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


def record_dq_result(
    pg_conn: psycopg2.extensions.connection,
    batch_id: int,
    check_name: str,
    passed: bool,
    severity: str = "critical",
    details: Optional[str] = None,
) -> None:
    """Record a data quality check result to etl.dq_results."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl.dq_results (batch_id, check_name, status, severity, details)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (batch_id, check_name, "pass" if passed else "fail", severity, details),
        )
    pg_conn.commit()
