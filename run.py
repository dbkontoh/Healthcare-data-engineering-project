# ================================================================
# run.py — P01 Healthcare | Modules 03 + 05 Entry Point
# ================================================================
# python run.py
#
# WHAT HAPPENS:
#   PART 1: Demo SQL concepts live in the terminal
#             basics → aggregation → joins → window functions
#   PART 2: Module 03 — Run the full extraction query
#             (extract_raw_data.sql), join all four healthcare
#             tables, and save data/raw-data.csv
#   PART 3: Module 05 — ETL pipeline reads raw-data.csv,
#             validates → transforms → validates → loads
#             into data/processed/  (clean-data.csv +
#             patients/doctors/appointments/billing CSVs +
#             quality-report.txt)
# ================================================================

# ===========================================================================
# UNDERSTAND: Why we manipulate sys.path before importing project modules
# ---------------------------------------------------------------------------
# Python finds imports by searching folders listed in sys.path.
# By default, that includes the folder containing run.py — good.
# We explicitly insert _root (project root) at position 0 so imports like
#   from config import INDUSTRY
#   from src.etl_pipeline import ETLPipeline
# always resolve to THIS repo, even if you launch Python from a different cwd.
#
# pathlib.Path(__file__).resolve().parent  → absolute path to folder holding run.py
# ===========================================================================
import sys, pathlib
_root = pathlib.Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# ===========================================================================
# UNDERSTAND: The four imports that power the entire end-to-end story
# ---------------------------------------------------------------------------
# INDUSTRY, DB_AVAILABLE, logger  → from config (settings + "is DB up?")
# SQLQueryRunner                    → runs SQL, returns pandas tables (Part 1 demos)
# DataExtractor                     → Postgres/synthetic → raw-data.csv (Part 2)
# ETLPipeline                       → raw-data.csv → data/processed/* (Part 3)
#
# None of these lines RUN extraction yet — they only load class definitions.
# ===========================================================================
from config import INDUSTRY, DB_AVAILABLE, logger
from src.query_runner   import SQLQueryRunner
from src.data_extractor import DataExtractor
from src.etl_pipeline   import ETLPipeline


def main() -> None:
    # -----------------------------------------------------------------------
    # Banner: confirms which industry schema we target and whether Postgres
    # responded at config import time. If DB Available is False, Part 2 still
    # runs but uses synthetic data inside DataExtractor.
    # -----------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("  P01 HEALTHCARE — MODULES 03 + 05")
    logger.info(f"  Industry:     {INDUSTRY}")
    logger.info(f"  DB Available: {DB_AVAILABLE}")
    logger.info("=" * 60)

    # ===================================================================
    # PART 1 — SQL demonstrations (learning / proof of SQL skills)
    # ===================================================================
    # UNDERSTAND:
    # SQLQueryRunner() creates an object with an empty history list and industry='healthcare'.
    # Each demo_* method:
    #   1. Builds one or more SQL strings (often with f"{self.industry}.patients")
    #   2. Calls self.run(sql) → pd.read_sql against Supabase
    #   3. Prints the resulting DataFrame in the terminal
    #
    # These map to Sections 1–4 of sql/extract_raw_data.sql but run smaller
    # curated queries so you see output quickly without scrolling a 400-line file.
    # If DB is down, run() returns empty DataFrames and demos print nothing useful.
    # ===================================================================
    runner = SQLQueryRunner()

    print("\n── DEMO 1: Basic SELECT, DISTINCT, and Row Counts")
    runner.demo_basics()

    print("\n── DEMO 2: Aggregations — Revenue, Appointments, Patient Cities")
    runner.demo_aggregation()

    print("\n── DEMO 3: JOINs — Patients, Doctors, Billing")
    runner.demo_joins()

    print("\n── DEMO 4: CTEs and Window Functions — Rankings and Trends")
    runner.demo_window_functions()

    # ===================================================================
    # PART 2 — Production extraction (Module 03 deliverable)
    # ===================================================================
    # UNDERSTAND: Method chaining on DataExtractor
    # -------------------------------------------------------------------
    # DataExtractor()           → new object, raw_df=None, status='ready'
    # .extract()                → fills self.raw_df from SQL file OR synthetic
    # .save()                   → writes self.raw_df to config.RAW_DATA_PATH (CSV)
    # .report()                 → prints human-readable quality summary to terminal
    #
    # Each of those methods returns `self`, so Python lets you chain with dots
    # instead of:
    #   ex = DataExtractor()
    #   ex.extract()
    #   ex.save()
    #   ex.report()
    #
    # Output artifact: data/raw-data.csv (~300 rows × 30 columns) — intentionally
    # contains nulls, negative charges, and overpaid bills for the ETL to fix.
    # ===================================================================
    logger.info("\n[MODULE 03] Starting production extraction...")
    DataExtractor().extract().save().report()

    # ===================================================================
    # PART 3 — ETL pipeline (Module 05 deliverable)
    # ===================================================================
    # UNDERSTAND:
    # ETLPipeline().run() executes five internal steps in order:
    #   extract()        → pd.read_csv(raw-data.csv) into memory
    #   validate_raw()   → schema + key checks (DataValidator)
    #   transform()      → cleaning + derived columns (DataTransformer)
    #   validate_clean() → business rules on cleaned money/age
    #   load()           → write clean-data.csv + 4 dimension/fact CSVs + report
    #
    # .report() after .run() prints file sizes and final validation PASS/FAIL.
    # ===================================================================
    logger.info("\n[MODULE 05] Starting ETL pipeline...")
    ETLPipeline().run().report()


# ===========================================================================
# UNDERSTAND: if __name__ == "__main__"
# ---------------------------------------------------------------------------
# When you run `python run.py`, Python sets __name__ to "__main__" and main() runs.
# When another file does `import run`, __name__ is "run" and main() does NOT auto-run.
# This prevents accidentally re-running the whole hospital pipeline on import.
# ===========================================================================
if __name__ == "__main__":
    main()
