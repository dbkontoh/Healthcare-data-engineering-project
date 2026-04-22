# ================================================================
# run.py — P01 Healthcare SQL | Module 03 Entry Point
# ================================================================
# python run.py
#
# WHAT HAPPENS:
#   1. Demo SQL concepts live in the terminal:
#        basics → aggregation → joins → window functions
#   2. Run the full extraction query (extract_raw_data.sql)
#      joining healthcare.patients + appointments + doctors + billing
#   3. Save raw-data.csv to data/  ← deliverable for Module 05 ETL
# ================================================================

import sys, pathlib
_root = pathlib.Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import INDUSTRY, DB_AVAILABLE, logger
from src.query_runner   import SQLQueryRunner
from src.data_extractor import DataExtractor


def main() -> None:
    logger.info("=" * 60)
    logger.info("  MODULE 03 — SQL AND POSTGRESQL")
    logger.info(f"  Project:      P01 Healthcare SQL")
    logger.info(f"  Industry:     {INDUSTRY}")
    logger.info(f"  DB Available: {DB_AVAILABLE}")
    logger.info("=" * 60)

    # ── PART 1: SQL Demonstrations ──────────────────────────────────
    # Runs SQL concepts live against the healthcare schema.
    # Maps to Sections 1–4 of extract_raw_data.sql.
    runner = SQLQueryRunner()

    print("\n── DEMO 1: Basic SELECT, DISTINCT, and Row Counts")
    runner.demo_basics()

    print("\n── DEMO 2: Aggregations — Revenue, Appointments, Patient Cities")
    runner.demo_aggregation()

    print("\n── DEMO 3: JOINs — Patients, Doctors, Billing")
    runner.demo_joins()

    print("\n── DEMO 4: CTEs and Window Functions — Rankings and Trends")
    runner.demo_window_functions()

    # ── PART 2: Production Extraction ──────────────────────────────
    # The REAL deliverable — runs Section 5 of extract_raw_data.sql,
    # joins all four healthcare tables, and saves raw-data.csv.
    logger.info("\n[EXTRACT] Starting production extraction...")
    DataExtractor().extract().save().report()


if __name__ == "__main__":
    main()