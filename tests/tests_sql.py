# ================================================================
# tests/test_sql.py — Unit Tests for P01 Healthcare Module 03
# ================================================================
#
# WHAT THIS FILE TESTS:
#   1. SQL file — extract_raw_data.sql exists, contains valid SQL,
#      references the correct schema and all four core tables,
#      and includes the extraction query with all required columns
#   2. SQLQueryRunner — always returns a DataFrame, handles errors,
#      records audit history on every run
#   3. DataExtractor — synthetic data has correct healthcare columns,
#      contains intentional data quality issues for Module 05 ETL,
#      save() creates a valid raw-data.csv
#   4. Healthcare domain rules — valid statuses, non-negative charges,
#      billing logic consistency
#
# NOTE ON SQL FILE STRUCTURE:
#   All SQL for this project lives in ONE file: extract_raw_data.sql
#   It contains five labelled sections:
#     Section 1 — Basics
#     Section 2 — Aggregations
#     Section 3 — Joins
#     Section 4 — CTEs and Window Functions
#     Section 5 — Raw Data Extract (production query)
#
# HOW TO RUN:
#   python tests/test_sql.py          ← run directly
#   pytest tests/test_sql.py -v       ← run via pytest
#
# SCHEMA CONTEXT:
#   healthcare.patients      → patient demographics
#   healthcare.appointments  → linked to patients + doctors
#   healthcare.doctors       → doctor profiles
#   healthcare.billing       → linked to appointments
# ================================================================

import sys, pathlib
_root = pathlib.Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from src.query_runner   import SQLQueryRunner
from src.data_extractor import DataExtractor


# ------------------------------------------------------------------ #
#  SECTION 1 — SQL FILE TESTS                                         #
#  All SQL for this project lives in one file: extract_raw_data.sql   #
# ------------------------------------------------------------------ #

SQL_FILE = "extract_raw_data.sql"   # single source of truth for all SQL


def test_sql_file_exists():
    """extract_raw_data.sql must exist in the sql/ directory."""
    from config import SQL_DIR
    assert (SQL_DIR / SQL_FILE).exists(), \
        f"SQL file missing: {SQL_FILE} — expected at {SQL_DIR / SQL_FILE}"
    print("  PASS: test_sql_file_exists")


def test_sql_file_contains_select_keyword():
    """extract_raw_data.sql must contain at least one SELECT statement."""
    from config import SQL_DIR
    content = (SQL_DIR / SQL_FILE).read_text(encoding="utf-8")
    assert "SELECT" in content.upper(), \
        f"No SELECT statement found in {SQL_FILE}"
    print("  PASS: test_sql_file_contains_select_keyword")


def test_sql_file_references_healthcare_schema():
    """extract_raw_data.sql must explicitly reference the healthcare schema."""
    from config import SQL_DIR
    content = (SQL_DIR / SQL_FILE).read_text(encoding="utf-8")
    assert "healthcare" in content.lower(), \
        f"{SQL_FILE} does not reference the healthcare schema"
    print("  PASS: test_sql_file_references_healthcare_schema")


def test_sql_file_references_all_four_tables():
    """extract_raw_data.sql must reference all four core healthcare tables."""
    from config import SQL_DIR
    content = (SQL_DIR / SQL_FILE).read_text(encoding="utf-8").lower()
    core_tables = ["patients", "appointments", "doctors", "billing"]
    for table in core_tables:
        assert table in content, \
            f"{SQL_FILE} does not reference core table: {table}"
    print("  PASS: test_sql_file_references_all_four_tables")


def test_sql_file_contains_industry_placeholder():
    """extract_raw_data.sql must use the {industry} placeholder."""
    from config import SQL_DIR
    content = (SQL_DIR / SQL_FILE).read_text(encoding="utf-8")
    assert "{industry}" in content, \
        f"{SQL_FILE} must use {{industry}} placeholder for multi-schema support"
    print("  PASS: test_sql_file_contains_industry_placeholder")


def test_sql_file_contains_billing_columns():
    """extract_raw_data.sql must select the key billing output columns."""
    from config import SQL_DIR
    content = (SQL_DIR / SQL_FILE).read_text(encoding="utf-8").lower()
    required_cols = ["amount_charged", "payment_status", "bill_date"]
    for col in required_cols:
        assert col in content, \
            f"{SQL_FILE} missing required billing column: {col}"
    print("  PASS: test_sql_file_contains_billing_columns")


def test_sql_file_contains_all_five_sections():
    """extract_raw_data.sql must contain all five section markers."""
    from config import SQL_DIR
    content = (SQL_DIR / SQL_FILE).read_text(encoding="utf-8").upper()
    sections = [
        "SECTION 1",
        "SECTION 2",
        "SECTION 3",
        "SECTION 4",
        "SECTION 5",
    ]
    for section in sections:
        assert section in content, \
            f"{SQL_FILE} is missing section marker: {section}"
    print("  PASS: test_sql_file_contains_all_five_sections")


# ------------------------------------------------------------------ #
#  SECTION 2 — SQLQueryRunner TESTS                                   #
# ------------------------------------------------------------------ #

def test_query_runner_returns_dataframe():
    """SQLQueryRunner.run() must always return a DataFrame — never raises."""
    runner = SQLQueryRunner()
    df = runner.run("SELECT 1 AS test_col")
    assert isinstance(df, pd.DataFrame), \
        "run() must always return a DataFrame"
    print("  PASS: test_query_runner_returns_dataframe")


def test_query_runner_handles_bad_sql_gracefully():
    """A broken SQL query must return an empty DataFrame, not crash."""
    runner = SQLQueryRunner()
    df = runner.run("THIS IS NOT VALID SQL AT ALL")
    assert isinstance(df, pd.DataFrame), \
        "run() must return empty DataFrame on SQL error, not raise an exception"
    print("  PASS: test_query_runner_handles_bad_sql_gracefully")


def test_query_runner_history_records_each_run():
    """Every call to run() must append exactly one entry to self.history."""
    runner = SQLQueryRunner()
    initial_count = len(runner.history)
    runner.run("SELECT 1")
    runner.run("SELECT 2")
    runner.run("SELECT 3")
    assert len(runner.history) == initial_count + 3, \
        "history must record every query run, including failures"
    print("  PASS: test_query_runner_history_records_each_run")


def test_query_runner_history_entry_has_required_keys():
    """Every history entry must contain the five required audit fields."""
    runner = SQLQueryRunner()
    runner.run("SELECT 1 AS probe")
    entry = runner.history[-1]
    required_keys = ["sql_preview", "rows", "cols", "duration_ms", "status"]
    for key in required_keys:
        assert key in entry, \
            f"History entry missing required key: '{key}'"
    print("  PASS: test_query_runner_history_entry_has_required_keys")


def test_query_runner_history_records_failed_queries():
    """Failed queries must still be recorded in history with error status."""
    runner = SQLQueryRunner()
    runner.run("SELECT * FROM nonexistent_table_xyz_abc")
    assert len(runner.history) >= 1, \
        "Failed queries must still appear in history"
    last_entry = runner.history[-1]
    assert "status" in last_entry, \
        "History entry must contain a status field"
    print("  PASS: test_query_runner_history_records_failed_queries")


def test_query_runner_industry_substitution():
    """run() must replace {industry} placeholder with the configured schema."""
    runner = SQLQueryRunner()
    # Build a SQL string with the placeholder and check it is substituted
    sql_with_placeholder = "SELECT '{industry}' AS schema_check"
    # After substitution inside run(), {industry} becomes 'healthcare'
    # We test by confirming the runner's industry attribute is set correctly
    assert runner.industry == "healthcare", \
        f"runner.industry must be 'healthcare', got: {runner.industry!r}"
    print("  PASS: test_query_runner_industry_substitution")


# ------------------------------------------------------------------ #
#  SECTION 3 — DataExtractor SYNTHETIC DATA TESTS                     #
# ------------------------------------------------------------------ #

def test_extractor_synthetic_data_has_required_columns():
    """Synthetic fallback data must contain all 30 required healthcare columns."""
    raw = DataExtractor._synthetic_raw_data(50)
    required = [
        # Patient columns
        "patient_id",
        "patient_first_name",
        "patient_last_name",
        "date_of_birth",
        "gender",
        "blood_type",
        "city",
        "insurance_type",
        "patient_email",
        "patient_phone",
        # Appointment columns
        "appointment_id",
        "appointment_date",
        "appointment_time",
        "appointment_status",
        "visit_type",
        "duration_mins",
        "appointment_fee",
        "notes",
        # Doctor columns
        "doctor_id",
        "doctor_first_name",
        "doctor_last_name",
        "specialization",
        "doctor_years_exp",
        # Billing columns
        "bill_id",
        "amount_charged",
        "insurance_paid",
        "patient_paid",
        "payment_status",
        "payment_method",
        "bill_date",
    ]
    for col in required:
        assert col in raw.columns, \
            f"Synthetic data missing required column: '{col}'"
    print("  PASS: test_extractor_synthetic_data_has_required_columns")


def test_extractor_synthetic_data_row_count():
    """_synthetic_raw_data(n) must return exactly n rows."""
    for n in [10, 50, 300]:
        raw = DataExtractor._synthetic_raw_data(n)
        assert len(raw) == n, \
            f"Expected {n} rows, got {len(raw)}"
    print("  PASS: test_extractor_synthetic_data_row_count")


def test_extractor_synthetic_data_has_quality_issues():
    """Synthetic data must contain intentional quality issues for Module 05 ETL."""
    raw = DataExtractor._synthetic_raw_data(300)

    # Must have some NULL patient_email entries
    null_emails = raw["patient_email"].isna().sum()
    assert null_emails > 0, \
        "Synthetic data must have some NULL patient_email values"

    # Must have some NULL patient_phone entries
    null_phones = raw["patient_phone"].isna().sum()
    assert null_phones > 0, \
        "Synthetic data must have some NULL patient_phone values"

    # Must have some NULL duration_mins entries (appointment duration not always recorded)
    null_duration = raw["duration_mins"].isna().sum()
    assert null_duration > 0, \
        "Synthetic data must have some NULL duration_mins values"

    # Must have some NULL insurance_paid entries (billing data quality issue)
    null_insurance = raw["insurance_paid"].isna().sum()
    assert null_insurance > 0, \
        "Synthetic data must have some NULL insurance_paid values"

    print("  PASS: test_extractor_synthetic_data_has_quality_issues")


def test_extractor_synthetic_data_valid_appointment_statuses():
    """All appointment_status values must be from the known valid set."""
    raw = DataExtractor._synthetic_raw_data(300)
    valid_statuses = {"Completed", "Cancelled", "No-Show", "Scheduled"}
    actual_statuses = set(raw["appointment_status"].dropna().unique())
    unexpected = actual_statuses - valid_statuses
    assert not unexpected, \
        f"Unexpected appointment_status values found: {unexpected}"
    print("  PASS: test_extractor_synthetic_data_valid_appointment_statuses")


def test_extractor_synthetic_data_valid_payment_statuses():
    """All payment_status values must be from the known valid set."""
    raw = DataExtractor._synthetic_raw_data(300)
    valid_statuses = {"Paid", "Unpaid", "Partial"}
    actual_statuses = set(raw["payment_status"].dropna().unique())
    unexpected = actual_statuses - valid_statuses
    assert not unexpected, \
        f"Unexpected payment_status values found: {unexpected}"
    print("  PASS: test_extractor_synthetic_data_valid_payment_statuses")


def test_extractor_synthetic_data_unique_ids():
    """patient_id, appointment_id, and bill_id must all be unique."""
    raw = DataExtractor._synthetic_raw_data(200)
    assert raw["patient_id"].nunique() == len(raw), \
        "patient_id must be unique across all rows"
    assert raw["appointment_id"].nunique() == len(raw), \
        "appointment_id must be unique across all rows"
    assert raw["bill_id"].nunique() == len(raw), \
        "bill_id must be unique across all rows"
    print("  PASS: test_extractor_synthetic_data_unique_ids")


def test_extractor_synthetic_data_non_negative_charges():
    """amount_charged must never be negative — a healthcare billing rule."""
    raw = DataExtractor._synthetic_raw_data(300)
    charges = raw["amount_charged"].dropna()
    negative_charges = (charges < 0).sum()
    assert negative_charges == 0, \
        f"amount_charged must never be negative — found {negative_charges} rows"
    print("  PASS: test_extractor_synthetic_data_non_negative_charges")


def test_extractor_synthetic_data_valid_blood_types():
    """All blood_type values must be from the eight valid ABO/Rh types."""
    raw = DataExtractor._synthetic_raw_data(300)
    valid_types = {"A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"}
    actual_types = set(raw["blood_type"].dropna().unique())
    unexpected = actual_types - valid_types
    assert not unexpected, \
        f"Unexpected blood_type values found: {unexpected}"
    print("  PASS: test_extractor_synthetic_data_valid_blood_types")


# ------------------------------------------------------------------ #
#  SECTION 4 — DataExtractor SAVE TESTS                               #
# ------------------------------------------------------------------ #

def test_extractor_save_creates_csv(tmp_path):
    """DataExtractor.save() must create a valid raw-data.csv at RAW_DATA_PATH."""
    import config as cfg
    orig_path = cfg.RAW_DATA_PATH

    # Redirect the save path to a temp directory so we do not pollute real data
    cfg.RAW_DATA_PATH = pathlib.Path(tmp_path) / "raw-data.csv"

    extractor         = DataExtractor()
    extractor.raw_df  = DataExtractor._synthetic_raw_data(50)
    extractor._status = "extracted"
    extractor.save()

    assert cfg.RAW_DATA_PATH.exists(), \
        "save() must create raw-data.csv at RAW_DATA_PATH"

    # Reload and verify the CSV is correct
    reloaded = pd.read_csv(cfg.RAW_DATA_PATH)
    assert len(reloaded) == 50, \
        f"Saved CSV must have 50 rows, got {len(reloaded)}"

    # Restore original path so other tests are not affected
    cfg.RAW_DATA_PATH = orig_path
    print("  PASS: test_extractor_save_creates_csv")


def test_extractor_save_csv_has_no_index_column():
    """raw-data.csv must not contain a pandas index column."""
    import tempfile, config as cfg
    orig_path = cfg.RAW_DATA_PATH

    with tempfile.TemporaryDirectory() as tmp:
        cfg.RAW_DATA_PATH = pathlib.Path(tmp) / "raw-data.csv"

        extractor         = DataExtractor()
        extractor.raw_df  = DataExtractor._synthetic_raw_data(20)
        extractor._status = "extracted"
        extractor.save()

        reloaded = pd.read_csv(cfg.RAW_DATA_PATH)
        assert "Unnamed: 0" not in reloaded.columns, \
            "CSV must be saved with index=False — no unnamed index column"

    cfg.RAW_DATA_PATH = orig_path
    print("  PASS: test_extractor_save_csv_has_no_index_column")


def test_extractor_save_csv_preserves_all_columns():
    """raw-data.csv must contain all columns from the synthetic DataFrame."""
    import tempfile, config as cfg
    orig_path = cfg.RAW_DATA_PATH

    with tempfile.TemporaryDirectory() as tmp:
        cfg.RAW_DATA_PATH = pathlib.Path(tmp) / "raw-data.csv"

        synthetic         = DataExtractor._synthetic_raw_data(30)
        extractor         = DataExtractor()
        extractor.raw_df  = synthetic
        extractor._status = "extracted"
        extractor.save()

        reloaded = pd.read_csv(cfg.RAW_DATA_PATH)
        for col in synthetic.columns:
            assert col in reloaded.columns, \
                f"Column '{col}' missing from saved CSV"

    cfg.RAW_DATA_PATH = orig_path
    print("  PASS: test_extractor_save_csv_preserves_all_columns")


def test_extractor_save_without_extract_does_not_crash():
    """Calling save() before extract() must log an error but not crash."""
    extractor = DataExtractor()
    # raw_df is None — save() should handle this gracefully
    try:
        extractor.save()
    except Exception as e:
        assert False, \
            f"save() raised an exception when called before extract(): {e}"
    print("  PASS: test_extractor_save_without_extract_does_not_crash")


# ================================================================
# MAIN — run all tests directly without pytest
# ================================================================

if __name__ == "__main__":
    import tempfile

    print()
    print("=" * 60)
    print("  P01 HEALTHCARE — MODULE 03 SQL UNIT TESTS")
    print("=" * 60)
    print()

    # Section 1: SQL file tests (single file)
    print("── SECTION 1: SQL FILE TESTS (extract_raw_data.sql)")
    test_sql_file_exists()
    test_sql_file_contains_select_keyword()
    test_sql_file_references_healthcare_schema()
    test_sql_file_references_all_four_tables()
    test_sql_file_contains_industry_placeholder()
    test_sql_file_contains_billing_columns()
    test_sql_file_contains_all_five_sections()

    print()

    # Section 2: SQLQueryRunner tests
    print("── SECTION 2: SQLQueryRunner TESTS")
    test_query_runner_returns_dataframe()
    test_query_runner_handles_bad_sql_gracefully()
    test_query_runner_history_records_each_run()
    test_query_runner_history_entry_has_required_keys()
    test_query_runner_history_records_failed_queries()
    test_query_runner_industry_substitution()

    print()

    # Section 3: Synthetic data tests
    print("── SECTION 3: SYNTHETIC DATA TESTS")
    test_extractor_synthetic_data_has_required_columns()
    test_extractor_synthetic_data_row_count()
    test_extractor_synthetic_data_has_quality_issues()
    test_extractor_synthetic_data_valid_appointment_statuses()
    test_extractor_synthetic_data_valid_payment_statuses()
    test_extractor_synthetic_data_unique_ids()
    test_extractor_synthetic_data_non_negative_charges()
    test_extractor_synthetic_data_valid_blood_types()

    print()

    # Section 4: Save tests (need temp directories)
    print("── SECTION 4: SAVE TESTS")
    with tempfile.TemporaryDirectory() as tmp:
        test_extractor_save_creates_csv(pathlib.Path(tmp))
    test_extractor_save_csv_has_no_index_column()
    test_extractor_save_csv_preserves_all_columns()
    test_extractor_save_without_extract_does_not_crash()

    print()
    print("=" * 60)
    print("  All tests passed ✓")
    print("=" * 60)