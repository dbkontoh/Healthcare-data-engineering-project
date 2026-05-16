# ================================================================
# tests/test_pipeline.py — Unit + Integration Tests for Module 05
# ================================================================
# WHAT THIS FILE TESTS:
#   1. DataValidator   — catches missing columns, null keys, negative
#                        money, overpayments.
#   2. DataTransformer — strips whitespace, title-cases names, lowers
#                        emails, parses dates, clips negative money,
#                        caps overpayments, imputes categoricals,
#                        derives age / age_group / total_paid /
#                        balance / is_paid_in_full, splits into 4
#                        dimension/fact tables.
#   3. ETLPipeline     — end-to-end run on a tiny synthetic frame
#                        writes all expected outputs.
#
# HOW TO RUN:
#   pytest tests/test_pipeline.py -v
#
# NOTE:
#   This file complements tests/tests_sql.py (Module 03 tests).
#   Together they cover the whole project: SQL extract → ETL.
# ================================================================

# ===========================================================================
# UNDERSTAND: tests/test_pipeline.py — prove the ETL code is correct
# ---------------------------------------------------------------------------
# pytest automatically finds functions named test_* and runs them.
# If any assert fails, that test is marked FAILED and you see the line number.
#
# We use TINY fake DataFrames (2 rows) instead of the real 300-row CSV so tests
# run in milliseconds and never depend on Supabase being online.
#
# Fixtures (raw_df, validator) build shared setup once per test function.
# ===========================================================================

import sys, pathlib
_root = pathlib.Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import pytest

from config import EXPECTED_COLUMNS
from src.validator   import DataValidator
from src.transformer import DataTransformer
from src.etl_pipeline import ETLPipeline


# ------------------------------------------------------------------ #
#  FIXTURES                                                            #
# ------------------------------------------------------------------ #
# ---------------------------------------------------------------------------
# FIXTURE raw_df: two handcrafted rows — one clean, one deliberately broken
# (negative charge, overpayment, null gender/city) to stress the transformer.
# ---------------------------------------------------------------------------
@pytest.fixture
def raw_df() -> pd.DataFrame:
    """A tiny but realistic raw frame with every issue we want to test."""
    return pd.DataFrame([
        {  # Row 0: clean reference row.
            "patient_id": 1, "patient_first_name": " mary ", "patient_last_name": "smith",
            "date_of_birth": "1990-05-12", "gender": "Female", "blood_type": "O+",
            "city": "Greensboro", "insurance_type": "Aetna",
            "patient_email": "MARY@email.com", "patient_phone": "336-111-1111",
            "appointment_id": 1001, "appointment_date": "2024-01-15",
            "appointment_time": "09:00", "appointment_status": "Completed",
            "visit_type": "In-Person", "duration_mins": 30, "appointment_fee": 200.0,
            "notes": "Routine",
            "doctor_id": 101, "doctor_first_name": "john", "doctor_last_name": "doe",
            "specialization": "Cardiology", "doctor_years_exp": 10,
            "bill_id": 2001, "amount_charged": 500.0, "insurance_paid": 300.0,
            "patient_paid": 200.0, "payment_status": "Paid",
            "payment_method": "Insurance", "bill_date": "2024-01-15",
        },
        {  # Row 1: nulls + negative charge + overpayment.
            "patient_id": 2, "patient_first_name": "bob", "patient_last_name": "jones",
            "date_of_birth": "1985-08-20", "gender": None, "blood_type": "A+",
            "city": None, "insurance_type": "Medicare",
            "patient_email": None, "patient_phone": "336-222-2222",
            "appointment_id": 1002, "appointment_date": "2024-02-10",
            "appointment_time": "10:30", "appointment_status": "Completed",
            "visit_type": "Telehealth", "duration_mins": None, "appointment_fee": 150.0,
            "notes": None,
            "doctor_id": 102, "doctor_first_name": "jane", "doctor_last_name": "doe",
            "specialization": "Neurology", "doctor_years_exp": 5,
            "bill_id": 2002, "amount_charged": -100.0,        # negative
            "insurance_paid": 80.0, "patient_paid": 80.0,      # overpaid
            "payment_status": "Paid", "payment_method": None, "bill_date": "2024-02-10",
        },
    ])


@pytest.fixture
def validator() -> DataValidator:
    return DataValidator()


# ------------------------------------------------------------------ #
#  VALIDATOR TESTS                                                     #
# ------------------------------------------------------------------ #
# ---------------------------------------------------------------------------
# TestDataValidator: does validate_raw / validate_clean catch bad data?
# ---------------------------------------------------------------------------
class TestDataValidator:
    def test_raw_passes_on_good_schema(self, raw_df, validator):
        report = validator.validate_raw(raw_df)
        assert report.is_valid, f"Unexpected errors: {report.errors}"

    def test_raw_fails_on_missing_columns(self, raw_df, validator):
        bad = raw_df.drop(columns=["bill_id"])
        report = validator.validate_raw(bad)
        assert not report.is_valid
        assert any("Missing required columns" in e for e in report.errors)

    def test_raw_fails_on_null_key(self, raw_df, validator):
        bad = raw_df.copy()
        bad.loc[0, "patient_id"] = None
        report = validator.validate_raw(bad)
        assert not report.is_valid

    def test_clean_catches_negative_money(self, validator):
        bad = pd.DataFrame([{
            "patient_id": 1, "appointment_id": 1, "bill_id": 1,
            "amount_charged": -50.0, "insurance_paid": 0, "patient_paid": 0,
        }])
        report = validator.validate_clean(bad)
        assert not report.is_valid
        assert any("negative" in e for e in report.errors)

    def test_clean_catches_overpayment(self, validator):
        bad = pd.DataFrame([{
            "patient_id": 1, "appointment_id": 1, "bill_id": 1,
            "amount_charged": 100.0, "insurance_paid": 80.0, "patient_paid": 50.0,
        }])
        report = validator.validate_clean(bad)
        assert not report.is_valid
        assert any("overpaid" in e for e in report.errors)


# ------------------------------------------------------------------ #
#  TRANSFORMER TESTS                                                   #
# ------------------------------------------------------------------ #
# ---------------------------------------------------------------------------
# TestDataTransformer: after .clean(), are names fixed, money sane, columns derived?
# ---------------------------------------------------------------------------
class TestDataTransformer:
    def test_clean_returns_self_for_chaining(self, raw_df):
        t = DataTransformer(raw_df)
        assert t.clean() is t

    def test_negative_money_clipped_to_zero(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        assert (clean["amount_charged"] >= 0).all()

    def test_overpayments_capped(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        overpaid = (
            (clean["insurance_paid"] + clean["patient_paid"])
            > clean["amount_charged"]
        )
        assert not overpaid.any()

    def test_categorical_nulls_filled(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        for col in ("gender", "city", "payment_method"):
            assert clean[col].isna().sum() == 0
            assert (clean[col] == "Unknown").any()

    def test_text_standardized(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        assert clean.loc[0, "patient_first_name"] == "Mary"      # was " mary "
        assert clean.loc[0, "patient_last_name"]  == "Smith"     # was "smith"
        assert clean.loc[0, "patient_email"]      == "mary@email.com"  # was MARY@

    def test_dates_parsed(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        assert pd.api.types.is_datetime64_any_dtype(clean["date_of_birth"])
        assert pd.api.types.is_datetime64_any_dtype(clean["appointment_date"])
        assert pd.api.types.is_datetime64_any_dtype(clean["bill_date"])

    def test_age_derived_and_plausible(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        assert "age" in clean.columns
        assert ((clean["age"] >= 0) & (clean["age"] <= 120)).all()

    def test_totals_and_balance_derived(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        for col in ("total_paid", "balance", "is_paid_in_full"):
            assert col in clean.columns
        expected = (clean["insurance_paid"] + clean["patient_paid"]).round(2)
        pd.testing.assert_series_equal(
            clean["total_paid"], expected, check_names=False,
        )

    def test_age_group_assigned(self, raw_df):
        clean = DataTransformer(raw_df).clean().df
        assert "age_group" in clean.columns
        assert clean["age_group"].isin(
            ["0-17", "18-34", "35-54", "55-74", "75+", "Unknown"]
        ).all()

    def test_split_into_dimensions_returns_four_tables(self, raw_df):
        t = DataTransformer(raw_df).clean()
        dims = t.split_into_dimensions()
        assert set(dims) == {"patients", "doctors", "appointments", "billing"}
        assert dims["patients"]["patient_id"].is_unique
        assert dims["doctors"]["doctor_id"].is_unique


# ------------------------------------------------------------------ #
#  END-TO-END PIPELINE TESTS                                           #
# ------------------------------------------------------------------ #
# ---------------------------------------------------------------------------
# TestETLPipeline: run the REAL ETLPipeline class end-to-end on fake data.
# tmp_path = pytest gives a disposable folder; monkeypatch redirects output CSV paths
# so we never overwrite your real data/processed/ files during testing.
# ---------------------------------------------------------------------------
class TestETLPipeline:
    def test_full_run_writes_all_outputs(self, raw_df, tmp_path, monkeypatch):
        """Pipeline should produce 5 CSVs + a quality report."""
        raw_path   = tmp_path / "raw-data.csv"
        clean_path = tmp_path / "clean-data.csv"
        raw_df.to_csv(raw_path, index=False)

        # Redirect all processed outputs to tmp_path
        import config
        import src.etl_pipeline as ep
        for name in ("PATIENTS_OUT_PATH", "DOCTORS_OUT_PATH",
                     "APPOINTMENTS_OUT_PATH", "BILLING_OUT_PATH",
                     "QUALITY_REPORT_PATH"):
            file_name = getattr(config, name).name
            monkeypatch.setattr(ep, name, tmp_path / file_name)

        pipeline = ETLPipeline(raw_path=raw_path, clean_path=clean_path).run()

        assert clean_path.exists()
        for name in ("patients.csv", "doctors.csv",
                     "appointments.csv", "billing.csv",
                     "quality-report.txt"):
            assert (tmp_path / name).exists(), f"Missing output: {name}"

        assert pipeline.clean_report.is_valid

    def test_pipeline_raises_on_missing_raw_file(self, tmp_path):
        pipeline = ETLPipeline(raw_path=tmp_path / "does-not-exist.csv")
        with pytest.raises(FileNotFoundError):
            pipeline.extract()


# ------------------------------------------------------------------ #
#  CONTRACT SANITY                                                     #
# ------------------------------------------------------------------ #
# ---------------------------------------------------------------------------
# Contract test: if someone changes extract SQL columns, this reminds them to
# update EXPECTED_COLUMNS in config.py and the transformer together.
# ---------------------------------------------------------------------------
def test_expected_columns_contract():
    """The 30-column contract must stay in sync with Module 03's SQL."""
    assert len(EXPECTED_COLUMNS) == 30
    assert "patient_id" in EXPECTED_COLUMNS
    assert "bill_id" in EXPECTED_COLUMNS
