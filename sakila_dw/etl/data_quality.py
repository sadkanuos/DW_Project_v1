"""
Post-load data quality checks. Each check returns (passed: bool,
details: str) and is recorded to etl.dq_results by the caller.

`run_all_checks` returns True only if every *critical* check passes;
warning-severity checks are logged but don't fail the batch.
"""

from etl.utils import get_pg_connection, logger, record_dq_result

# (check_name, severity, SQL that returns a single count of BAD rows)
CHECKS = [
    (
        "fact_rental_orphan_customer", "critical",
        """
        SELECT COUNT(*) FROM mart.fact_rental fr
        LEFT JOIN mart.dim_customer dc ON dc.customer_sk = fr.customer_sk
        WHERE dc.customer_sk IS NULL;
        """,
    ),
    (
        "fact_rental_orphan_film", "critical",
        """
        SELECT COUNT(*) FROM mart.fact_rental fr
        LEFT JOIN mart.dim_film df ON df.film_sk = fr.film_sk
        WHERE df.film_sk IS NULL;
        """,
    ),
    (
        "fact_payment_orphan_customer", "critical",
        """
        SELECT COUNT(*) FROM mart.fact_payment fp
        LEFT JOIN mart.dim_customer dc ON dc.customer_sk = fp.customer_sk
        WHERE dc.customer_sk IS NULL;
        """,
    ),
    (
        "bridge_film_category_orphan_film", "critical",
        """
        SELECT COUNT(*) FROM mart.bridge_film_category bfc
        LEFT JOIN mart.dim_film df ON df.film_sk = bfc.film_sk
        WHERE df.film_sk IS NULL;
        """,
    ),
    (
        "dim_customer_null_email", "warning",
        "SELECT COUNT(*) FROM mart.dim_customer WHERE email IS NULL;",
    ),
    (
        "fact_payment_nonpositive_amount", "warning",
        "SELECT COUNT(*) FROM mart.fact_payment WHERE amount <= 0;",
    ),
    (
        "mart_row_counts_nonzero", "critical",
        """
        SELECT
            CASE WHEN
                (SELECT COUNT(*) FROM mart.dim_customer) > 0 AND
                (SELECT COUNT(*) FROM mart.dim_film) > 0 AND
                (SELECT COUNT(*) FROM mart.fact_rental) > 0 AND
                (SELECT COUNT(*) FROM mart.fact_payment) > 0
            THEN 0 ELSE 1 END;
        """,
    ),
]


def run_all_checks(pg_conn, batch_id):
    """
    Run every check in CHECKS, record each to etl.dq_results, and
    return True iff all *critical* checks passed.
    """
    all_critical_passed = True
    for check_name, severity, sql in CHECKS:
        with pg_conn.cursor() as cur:
            cur.execute(sql)
            bad_rows = cur.fetchone()[0]
        passed = bad_rows == 0
        details = f"{bad_rows} offending row(s)" if not passed else "ok"
        record_dq_result(pg_conn, batch_id, check_name, passed, severity, details)
        logger.info(
            "DQ check '%s' [%s]: %s (%s)",
            check_name, severity, "PASS" if passed else "FAIL", details,
        )
        if not passed and severity == "critical":
            all_critical_passed = False
    return all_critical_passed


if __name__ == "__main__":
    conn = get_pg_connection()
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO etl.batch (status) VALUES ('running') RETURNING batch_id;")
            bid = c.fetchone()[0]
        conn.commit()
        ok = run_all_checks(conn, bid)
        print("All critical checks passed" if ok else "Some critical checks FAILED")
    finally:
        conn.close()
