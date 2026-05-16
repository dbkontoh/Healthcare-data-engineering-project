# ================================================================
# src/validator.py — P01 Healthcare Module 05 (ETL)
# ================================================================
# CONTEXT:
#   Module 03 produced data/raw-data.csv from PostgreSQL. That file
#   intentionally contains data-quality issues (nulls, negative
#   charges, overpaid bills). Before we transform it, we want a
#   gatekeeper that confirms the *shape* of the input is what we
#   expect; afterwards, we want a second pass that confirms the
#   *content* is now safe to publish.
#
# THE ANALOGY:
#   Think of DataValidator as a hospital intake nurse.
#   validate_raw()   → triage on arrival (does this patient have
#                      a chart number? are key fields present?)
#   validate_clean() → discharge check (vitals stable? no errors
#                      in the chart? ready to release?)
#
# WHAT IT RETURNS:
#   A ValidationReport — a small, immutable-feeling object that
#   collects errors + warnings. The pipeline decides what to do
#   with them: log-and-continue (default) or abort (strict mode).
# ================================================================

import sys, pathlib
from dataclasses import dataclass, field
from typing import List

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from config import EXPECTED_COLUMNS, logger


# ===========================================================================
# UNDERSTAND: @dataclass ValidationReport — structured PASS/FAIL notebook
# ---------------------------------------------------------------------------
# Instead of returning (True, ["error1", "error2"]) tuples, we build one object:
#   report.errors   → list of strings that MUST be fixed (hard failures)
#   report.warnings → list of strings worth logging but not blocking (soft)
#   report.is_valid → computed property: True only when errors is empty
#
# field(default_factory=list) means "create a NEW empty list per instance."
# Without default_factory, all reports would accidentally share one list.
# ===========================================================================
@dataclass
class ValidationReport:
    """
    Collects the results of one validation pass.

    Attributes
    ──────────
    stage         str           'raw' or 'clean' — which check this is
    errors        list[str]     hard failures (block the pipeline if strict)
    warnings      list[str]     soft issues (log but continue)
    rows_checked  int           number of rows the validator saw
    """
    stage: str
    errors:   List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rows_checked: int = 0

    # -------------------------------------------------------------------
    # is_valid: True only when the errors list is empty (warnings ignored).
    # @property lets you write report.is_valid instead of report.is_valid().
    # -------------------------------------------------------------------
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    # -------------------------------------------------------------------
    # add_error / add_warning: append a message AND log it for the terminal.
    # -------------------------------------------------------------------
    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.error(f"[VALIDATE/{self.stage}] {msg}")

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning(f"[VALIDATE/{self.stage}] {msg}")

    def summary(self) -> str:
        ok = "PASS" if self.is_valid else "FAIL"
        return (
            f"[{ok}] {self.stage} | rows={self.rows_checked:,} "
            f"| errors={len(self.errors)} warnings={len(self.warnings)}"
        )


# ===========================================================================
# UNDERSTAND: DataValidator — two checkpoints in the ETL journey
# ---------------------------------------------------------------------------
# validate_raw  = "Is this CSV the right SHAPE before we clean?" (columns, keys)
# validate_clean = "Is this table SAFE to publish after cleaning?" (money, age)
# The ETL pipeline calls both; strict mode in config can abort on errors.
# ===========================================================================
class DataValidator:
    """
    Runs schema + business-rule checks on the healthcare dataframe.

    Two public methods:
        validate_raw(df)   → pre-transform schema / null-key checks
        validate_clean(df) → post-transform business-rule checks
    """

    # Business keys: without these IDs you cannot link rows to patients/bills
    KEY_COLUMNS = ("patient_id", "appointment_id", "bill_id")

    # =========================================================================
    # UNDERSTAND: validate_raw — gate BEFORE DataTransformer runs
    # -------------------------------------------------------------------------
    # Fails on: empty file, missing EXPECTED_COLUMNS, null patient/appointment/bill_id
    # Warns on: extra columns, columns >30% null (raw mess is expected)
    # =========================================================================
    def validate_raw(self, df: pd.DataFrame) -> ValidationReport:
        """
        Confirm the raw extract matches the Module 03 contract:
          - non-empty
          - all 30 expected columns present
          - no nulls in business key IDs
        Anything else (nulls in optional cols, etc.) is logged as a warning.
        """
        report = ValidationReport(stage="raw", rows_checked=len(df) if df is not None else 0)

        if df is None or df.empty:
            report.add_error("Raw dataframe is empty.")
            return report

        # -------------------------------------------------------------------
        # SCHEMA CHECK: every name in EXPECTED_COLUMNS must exist as a column.
        # List comprehension: [c for c in EXPECTED_COLUMNS if c not in df.columns]
        # reads as "every expected column c that is missing from the dataframe."
        # -------------------------------------------------------------------
        missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        if missing:
            report.add_error(f"Missing required columns: {missing}")

        extra = [c for c in df.columns if c not in EXPECTED_COLUMNS]
        if extra:
            report.add_warning(f"Unexpected extra columns (kept as-is): {extra}")

        # -------------------------------------------------------------------
        # KEY CHECK: patient_id, appointment_id, bill_id cannot be null.
        # .isna().sum() counts how many rows have NaN/None in that column.
        # -------------------------------------------------------------------
        for key in self.KEY_COLUMNS:
            if key in df.columns:
                n_nulls = df[key].isna().sum()
                if n_nulls:
                    report.add_error(f"Key column `{key}` has {n_nulls} null(s).")

        # -------------------------------------------------------------------
        # HIGH-NULL WARNING: raw data is allowed to be messy, but we flag
        # columns more than 30% null so humans know where ETL imputation matters.
        # -------------------------------------------------------------------
        null_pct = (df.isna().sum() / len(df) * 100).round(1)
        for col, pct in null_pct[null_pct > 30].items():
            report.add_warning(f"Column `{col}` is {pct}% null in raw data.")

        logger.info(report.summary())
        return report

    # =========================================================================
    # UNDERSTAND: validate_clean — gate AFTER all cleaning steps
    # -------------------------------------------------------------------------
    # Fails on: null keys, negative money, overpaid rows, impossible age
    # Warns on: categoricals still null (should be "Unknown" after transform)
    # =========================================================================
    def validate_clean(self, df: pd.DataFrame) -> ValidationReport:
        """
        Confirm the cleaned frame is safe for analytics:
          - no nulls in business keys
          - no negative money
          - no overpaid bills
          - all ages within 0..120
          - categorical columns no longer null (Unknown is fine)
        """
        report = ValidationReport(stage="clean", rows_checked=len(df) if df is not None else 0)

        if df is None or df.empty:
            report.add_error("Clean dataframe is empty after transform.")
            return report

        for key in self.KEY_COLUMNS:
            if key in df.columns and df[key].isna().any():
                report.add_error(f"Clean data still has nulls in `{key}`.")

        # -------------------------------------------------------------------
        # MONEY: (df[col] < 0).sum() counts rows where the column is negative.
        # After transform, charges and payments should be >= 0.
        # -------------------------------------------------------------------
        for col in ("amount_charged", "insurance_paid", "patient_paid"):
            if col in df.columns:
                negatives = (df[col] < 0).sum()
                if negatives:
                    report.add_error(f"`{col}` has {negatives} negative value(s).")

        # -------------------------------------------------------------------
        # OVERPAYMENT: insurance_paid + patient_paid must not exceed amount_charged.
        # We .round(2) because float math can make 995.60+424.47 slightly > 1420.07
        # even when the transformer already balanced the row to the cent.
        # -------------------------------------------------------------------
        money = {"amount_charged", "insurance_paid", "patient_paid"}
        if money.issubset(df.columns):
            total_paid = (df["insurance_paid"] + df["patient_paid"]).round(2)
            charged    = df["amount_charged"].round(2)
            overpaid   = (total_paid > charged).sum()
            if overpaid:
                report.add_error(f"{overpaid} row(s) still overpaid after transform.")

        if "age" in df.columns:
            bad_age = ((df["age"] < 0) | (df["age"] > 120)).sum()
            if bad_age:
                report.add_error(f"{bad_age} row(s) have implausible age.")

        for cat in ("gender", "city", "payment_method"):
            if cat in df.columns and df[cat].isna().any():
                report.add_warning(
                    f"`{cat}` still has {df[cat].isna().sum()} null(s) after cleaning."
                )

        logger.info(report.summary())
        return report

    def __str__(self) -> str:
        return "DataValidator(stages=['raw', 'clean'])"

    def __repr__(self) -> str:
        return "DataValidator()"
