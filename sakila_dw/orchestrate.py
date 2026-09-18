"""
Entry point: runs one full pipeline batch end-to-end.

    python orchestrate.py

Exit codes (useful for cron/systemd monitoring):
    0 - success
    1 - pipeline failure (an extract/transform/load step raised)
    2 - pipeline succeeded, but a critical data quality check failed
"""

import sys

from etl import data_quality, extract_load_staging, transform_load_mart
from etl.utils import finish_batch, get_pg_connection, logger, run_step, start_batch


def main():
    pg_conn = get_pg_connection()
    batch_id = start_batch(pg_conn)

    try:
        run_step(
            pg_conn, batch_id, "extract_load_staging",
            extract_load_staging.load_all_staging_tables,
            pg_conn=pg_conn,
        )
        run_step(
            pg_conn, batch_id, "transform_load_mart_dims",
            transform_load_mart.load_all_dims,
            pg_conn=pg_conn,
        )
        run_step(
            pg_conn, batch_id, "transform_load_mart_facts",
            transform_load_mart.load_all_facts,
            pg_conn=pg_conn,
        )
    except Exception as exc:
        finish_batch(pg_conn, batch_id, "failed")
        pg_conn.close()
        logger.error(
            "Pipeline failed -- see etl.load_log for the failing step. "
            "Underlying error: %s", exc, exc_info=True,
        )
        sys.exit(1)

    dq_passed = data_quality.run_all_checks(pg_conn, batch_id)

    if dq_passed:
        finish_batch(pg_conn, batch_id, "success")
        pg_conn.close()
        logger.info("Pipeline completed successfully (batch %s).", batch_id)
        sys.exit(0)
    else:
        finish_batch(pg_conn, batch_id, "failed")
        pg_conn.close()
        logger.error(
            "Pipeline loaded data but a critical DQ check failed "
            "(batch %s) -- see etl.dq_results.", batch_id,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
