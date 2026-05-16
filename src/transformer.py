# ================================================================
# src/transformer.py — P01 Healthcare Module 05 (ETL)
# ================================================================
# CONTEXT:
#   raw-data.csv (from Module 03) is intentionally messy. The
#   transformer turns it into a clean, analytics-ready dataset.
#
# THE ANALOGY:
#   Think of DataTransformer as a medical-records clerk.
#   You hand them a stack of intake forms (the raw DataFrame).
#   They:
#     - tidy handwriting (strip whitespace, title-case names)
#     - convert dates from text to real dates
#     - fix obvious entry errors (negative dollar amounts)
#     - scale down overpaid bills proportionally
#     - fill missing categorical fields with 'Unknown'
#     - drop forms missing a chart number (key IDs)
#     - compute new fields the analytics team needs
#         (age, age_group, total_paid, balance, is_paid_in_full)
#
# DESIGN:
#   Every cleaning rule is its own _step_* method returning `self`,
#   so they can be chained, tested in isolation, and run in any
#   order during debugging. `clean()` is just the canonical order.
#
# USAGE:
#     t = DataTransformer(raw_df).clean()
#     clean_df = t.df
#     dim_tables = t.split_into_dimensions()
# ================================================================

# ===========================================================================
# UNDERSTAND: Path bootstrap — find project root so `from config import logger` works
# ===========================================================================
import sys, pathlib, datetime as dt

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import numpy as np
import pandas as pd
from config import logger


# ===========================================================================
# UNDERSTAND: DataTransformer class — holds one DataFrame and mutates it step by step
# ---------------------------------------------------------------------------
# self.df         = working copy of the hospital data (starts raw, ends clean)
# self.steps_run  = audit list of which _step_* methods executed (for logging)
# MONEY_COLS / DATE_COLS = column groups reused across several steps
# ===========================================================================
class DataTransformer:
    """
    Stateful cleaner for the joined healthcare raw extract.

    Attributes
    ──────────
    df          pd.DataFrame   the working frame (mutated by _step_* methods)
    steps_run   list[str]      ordered log of which steps fired
    """

    MONEY_COLS = ("amount_charged", "insurance_paid", "patient_paid")
    DATE_COLS  = ("date_of_birth", "appointment_date", "bill_date")

    def __init__(self, raw_df: pd.DataFrame):
        # =========================================================================
        # UNDERSTAND: Constructor receives the RAW wide table from ETL extract().
        # We copy it because every _step_* method will modify columns in place.
        # Without .copy(), we'd accidentally mutate the pipeline's raw_df too.
        # =========================================================================
        self.df = raw_df.copy()
        self.steps_run: list[str] = []
        logger.info(f"DataTransformer ready — {len(self.df):,} rows in.")

    def clean(self) -> "DataTransformer":
        """Run every cleaning step in the canonical order."""
        # =========================================================================
        # UNDERSTAND: clean() runs 11 steps in deliberate order.
        # You cannot derive age before dates are parsed. You cannot compute balance
        # before overpayments are fixed. Each method returns self so calls chain.
        # After this block, self.df is the cleaned table; self.steps_run logs what ran.
        # =========================================================================
        (self._step_strip_whitespace()
             ._step_standardize_text()
             ._step_parse_dates()
             ._step_coerce_numerics()
             ._step_fix_negative_money()
             ._step_cap_overpayments()
             ._step_impute_categoricals()
             ._step_drop_missing_keys()
             ._step_derive_age()
             ._step_derive_totals()
             ._step_derive_age_group())

        logger.info(
            f"[TRANSFORM] Done — {len(self.df):,} rows out. "
            f"Steps: {', '.join(self.steps_run)}"
        )
        return self

    def _step_strip_whitespace(self) -> "DataTransformer":
        # -------------------------------------------------------------------
        # Text columns only (object dtype). astype("string") then .str.strip()
        # turns " mary " → "mary" so title-casing works predictably next step.
        # -------------------------------------------------------------------
        for col in self.df.select_dtypes(include="object").columns:
            self.df[col] = self.df[col].astype("string").str.strip()
        self.steps_run.append("strip_whitespace")
        return self

    # =========================================================================
    # UNDERSTAND: _step_standardize_text — human-readable names and emails
    # -------------------------------------------------------------------------
    # .str.title() on names: "mary" → "Mary" (each word capitalized)
    # .str.lower() on email: emails are case-insensitive per internet standards
    # =========================================================================
    def _step_standardize_text(self) -> "DataTransformer":
        # Names → Title Case
        for col in ("patient_first_name", "patient_last_name",
                    "doctor_first_name",  "doctor_last_name"):
            if col in self.df.columns:
                self.df[col] = self.df[col].str.title()

        # Email → lowercase (emails are case-insensitive by internet standard)
        if "patient_email" in self.df.columns:
            self.df["patient_email"] = self.df["patient_email"].str.lower()

        self.steps_run.append("standardize_text")
        return self

    def _step_parse_dates(self) -> "DataTransformer":
        # -------------------------------------------------------------------
        # pd.to_datetime converts "2024-01-15" strings to datetime64 dtype.
        # errors="coerce" turns unparseable garbage into NaT (Not a Time) instead
        # of crashing the whole pipeline.
        # -------------------------------------------------------------------
        for col in self.DATE_COLS:
            if col in self.df.columns:
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce")
        self.steps_run.append("parse_dates")
        return self

    def _step_coerce_numerics(self) -> "DataTransformer":
        # -------------------------------------------------------------------
        # IDs and money may arrive as strings from CSV. pd.to_numeric forces
        # real numbers so comparisons like amount_charged < 0 work correctly.
        # -------------------------------------------------------------------
        numeric_cols = (
            "patient_id", "appointment_id", "bill_id", "doctor_id",
            "duration_mins", "appointment_fee", "doctor_years_exp",
            *self.MONEY_COLS,
        )
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")
        self.steps_run.append("coerce_numerics")
        return self

    # =========================================================================
    # UNDERSTAND: _step_fix_negative_money
    # -------------------------------------------------------------------------
    # Hospital bills should never be negative in analytics. .clip(lower=0) replaces
    # any value < 0 with 0 across the whole column in one vectorized operation.
    # =========================================================================
    def _step_fix_negative_money(self) -> "DataTransformer":
        """Negative billing values = data entry errors → clip to 0."""
        # .clip(lower=0): any value below zero becomes zero (vectorized on whole column)
        for col in self.MONEY_COLS:
            if col in self.df.columns:
                bad = (self.df[col] < 0).sum()
                if bad:
                    logger.warning(f"[TRANSFORM] Clipping {bad} negative `{col}` → 0.")
                self.df[col] = self.df[col].clip(lower=0)
        self.steps_run.append("fix_negative_money")
        return self

    def _step_cap_overpayments(self) -> "DataTransformer":
        """
        Reconcile billing math:
          - If amount_charged is missing or 0 but payments exist, zero
            the payments (a $0 bill can't have been paid).
          - If insurance_paid + patient_paid > amount_charged, scale
            both payments down proportionally so the totals balance.
        """
        cols = {"amount_charged", "insurance_paid", "patient_paid"}
        if not cols.issubset(self.df.columns):
            return self

        for c in ("insurance_paid", "patient_paid"):
            self.df[c] = self.df[c].fillna(0)

        self.df["amount_charged"] = self.df["amount_charged"].fillna(0)

        charged    = self.df["amount_charged"]
        total_paid = self.df["insurance_paid"] + self.df["patient_paid"]

        # -------------------------------------------------------------------
        # CASE A: Bill says $0 charged but someone paid money → zero payments.
        # Happens when negative charge was clipped to 0 in previous step.
        # zero_charged_mask is a Series of True/False per row.
        # .loc[mask, [cols]] updates ONLY rows where mask is True.
        # -------------------------------------------------------------------
        zero_charged_mask = (charged == 0) & (total_paid > 0)
        n_zero = zero_charged_mask.sum()
        if n_zero:
            logger.warning(
                f"[TRANSFORM] Zeroing payments on {n_zero} bills with no charge."
            )
            self.df.loc[zero_charged_mask, ["insurance_paid", "patient_paid"]] = 0.0

        total_paid    = self.df["insurance_paid"] + self.df["patient_paid"]
        overpaid_mask = (total_paid > charged) & (charged > 0)
        n_overpaid    = overpaid_mask.sum()
        if n_overpaid:
            logger.warning(f"[TRANSFORM] Scaling down {n_overpaid} overpaid bills.")
            # ratio = what fraction of the overpayment to keep (e.g. charged/paid)
            ratio = charged / total_paid.replace(0, np.nan)
            self.df.loc[overpaid_mask, "insurance_paid"] = (
                self.df.loc[overpaid_mask, "insurance_paid"] * ratio.loc[overpaid_mask]
            ).round(2)
            self.df.loc[overpaid_mask, "patient_paid"] = (
                self.df.loc[overpaid_mask, "patient_paid"] * ratio.loc[overpaid_mask]
            ).round(2)
            # Set patient_paid = charged - insurance_paid to fix float dust
            self.df.loc[overpaid_mask, "patient_paid"] = (
                charged.loc[overpaid_mask]
                - self.df.loc[overpaid_mask, "insurance_paid"]
            ).round(2).clip(lower=0)

        self.steps_run.append("cap_overpayments")
        return self

    # =========================================================================
    # UNDERSTAND: _step_impute_categoricals
    # -------------------------------------------------------------------------
    # gender, city, payment_method, etc. are categories (finite set of labels).
    # Analytics tools break on NULL categories; we use "Unknown" as a bucket.
    # .replace("", "Unknown") catches empty strings after strip().
    # =========================================================================
    def _step_impute_categoricals(self) -> "DataTransformer":
        """Fill blanks in low-cardinality categorical columns with 'Unknown'."""
        for col in ("gender", "city", "payment_method",
                    "insurance_type", "blood_type", "visit_type"):
            if col in self.df.columns:
                self.df[col] = self.df[col].fillna("Unknown").replace("", "Unknown")
        self.steps_run.append("impute_categoricals")
        return self

    # =========================================================================
    # UNDERSTAND: _step_drop_missing_keys
    # -------------------------------------------------------------------------
    # If patient_id OR appointment_id OR bill_id is null, the row cannot join
    # to other tables — safer to remove than invent fake IDs.
    # reset_index(drop=True) renumbers rows 0..n-1 after deletions.
    # =========================================================================
    def _step_drop_missing_keys(self) -> "DataTransformer":
        """Rows missing any business key are unusable downstream — drop them."""
        keys = [c for c in ("patient_id", "appointment_id", "bill_id")
                if c in self.df.columns]
        before = len(self.df)
        if keys:
            self.df = self.df.dropna(subset=keys).reset_index(drop=True)
        dropped = before - len(self.df)
        if dropped:
            logger.warning(f"[TRANSFORM] Dropped {dropped} rows with missing key IDs.")
        self.steps_run.append("drop_missing_keys")
        return self

    # =========================================================================
    # UNDERSTAND: _step_derive_age
    # -------------------------------------------------------------------------
    # Computes age in whole years from date_of_birth vs today's date.
    # Ages <0 or >120 set to pd.NA — humanly impossible, flagged in validate_clean.
    # =========================================================================
    def _step_derive_age(self) -> "DataTransformer":
        if "date_of_birth" not in self.df.columns:
            return self
        today = pd.Timestamp(dt.date.today())
        # Subtract dates → Timedelta; .dt.days / 365.25 ≈ years old
        years = (today - self.df["date_of_birth"]).dt.days / 365.25
        self.df["age"] = years.astype("Int64", errors="ignore")
        self.df.loc[(self.df["age"] < 0) | (self.df["age"] > 120), "age"] = pd.NA
        self.steps_run.append("derive_age")
        return self

    # =========================================================================
    # UNDERSTAND: _step_derive_totals — billing analytics columns
    # -------------------------------------------------------------------------
    # total_paid = insurance_paid + patient_paid (what hospital collected)
    # balance = amount_charged - total_paid (still owed; 0 or negative = paid off)
    # is_paid_in_full = True when balance <= 0
    # =========================================================================
    def _step_derive_totals(self) -> "DataTransformer":
        if {"insurance_paid", "patient_paid"}.issubset(self.df.columns):
            self.df["total_paid"] = (
                self.df["insurance_paid"].fillna(0)
                + self.df["patient_paid"].fillna(0)
            ).round(2)

        if {"amount_charged", "total_paid"}.issubset(self.df.columns):
            self.df["balance"] = (
                self.df["amount_charged"].fillna(0) - self.df["total_paid"]
            ).round(2)
            # True where nothing left to pay (balance <= 0)
            self.df["is_paid_in_full"] = self.df["balance"] <= 0

        self.steps_run.append("derive_totals")
        return self

    def _step_derive_age_group(self) -> "DataTransformer":
        if "age" not in self.df.columns:
            return self
        bins   = [0, 17, 34, 54, 74, 120]
        labels = ["0-17", "18-34", "35-54", "55-74", "75+"]
        # pd.cut buckets continuous age into categorical bands for dashboards
        self.df["age_group"] = (
            pd.cut(self.df["age"].astype("float"),
                   bins=bins, labels=labels, include_lowest=True)
              .astype("string")
              .fillna("Unknown")
        )
        self.steps_run.append("derive_age_group")
        return self

    # =========================================================================
    # UNDERSTAND: split_into_dimensions — one wide table → four CSV-ready tables
    # -------------------------------------------------------------------------
    # Mimics a star schema: patients & doctors are dimensions (deduplicated);
    # appointments & billing are facts (one row per event). Returned dict keys
    # match filenames ETLPipeline.load() writes (patients.csv, etc.).
    # =========================================================================
    def split_into_dimensions(self) -> dict[str, pd.DataFrame]:
        """
        Break the flat cleaned frame into 4 tables that mirror the
        original healthcare schema: patients, doctors, appointments, billing.
        Patient and doctor tables are deduplicated on their key.
        """
        df = self.df

        # drop_duplicates(subset="patient_id") → one row per patient in dimension file
        patients = (
            df[[
                "patient_id", "patient_first_name", "patient_last_name",
                "date_of_birth", "age", "age_group", "gender", "blood_type",
                "city", "insurance_type", "patient_email", "patient_phone",
            ]]
            .drop_duplicates(subset="patient_id")
            .reset_index(drop=True)
        )

        doctors = (
            df[[
                "doctor_id", "doctor_first_name", "doctor_last_name",
                "specialization", "doctor_years_exp",
            ]]
            .drop_duplicates(subset="doctor_id")
            .reset_index(drop=True)
        )

        appointments = df[[
            "appointment_id", "patient_id", "doctor_id",
            "appointment_date", "appointment_time", "appointment_status",
            "visit_type", "duration_mins", "appointment_fee", "notes",
        ]].reset_index(drop=True)

        billing = df[[
            "bill_id", "appointment_id", "patient_id",
            "amount_charged", "insurance_paid", "patient_paid",
            "total_paid", "balance", "is_paid_in_full",
            "payment_status", "payment_method", "bill_date",
        ]].reset_index(drop=True)

        return {
            "patients":     patients,
            "doctors":      doctors,
            "appointments": appointments,
            "billing":      billing,
        }

    def __str__(self) -> str:
        return f"DataTransformer(rows={len(self.df):,}, steps_run={len(self.steps_run)})"

    def __repr__(self) -> str:
        return f"DataTransformer(rows={len(self.df)})"
