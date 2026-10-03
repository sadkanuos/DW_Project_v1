"""
Post-load data quality checks. Each check returns (passed: bool,
details: str) and is recorded to etl.dq_results by the caller.

Checks are loaded from YAML configuration.
All functions include full type hints.
"""

from typing import Any, Dict, List, Optional

import psycopg2.extensions

from etl.utils import get_pg_connection, logger, record_dq_result, get_config


def run_all_checks(
    pg_conn: psycopg2.extensions.connection,
    batch_id: int,
) -> bool:
    """
    Run every check from configuration, record each to etl.dq_results, and
    return True iff all *critical* checks passed.


    Args:
        pg_conn: PostgreSQL connection
        batch_id: Current batch ID for audit logging

    Returns:
        True if all critical checks passed, False otherwise
    """
    config = get_config()
    all_critical_passed = True

    # Single iteration over checks from YAML config
    for check_def in config.dq_checks:
        check_name = check_def["name"]
        severity = check_def["severity"]
        sql = check_def["sql"]

        with pg_conn.cursor() as cur:
            cur.execute(sql)
            bad_rows = cur.fetchone()[0]

        passed = bad_rows == 0
        details = f"{bad_rows} offending row(s)" if not passed else "ok"

        record_dq_result(pg_conn, batch_id, check_name, passed, severity, details)
        logger.info(
            "DQ check '%s' [%s]: %s (%s)",
            check_name,
            severity,
            "PASS" if passed else "FAIL",
            details,
        )
        if not passed and severity == "critical":
            all_critical_passed = False

    return all_critical_passed


if __name__ == "__main__":
    conn = get_pg_connection()
    try:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO etl.batch (status) VALUES ('running') RETURNING batch_id;"
            )
            bid = c.fetchone()[0]
        conn.commit()
        ok = run_all_checks(conn, bid)
        print("All critical checks passed" if ok else "Some critical checks FAILED")
    finally:
        conn.close()
