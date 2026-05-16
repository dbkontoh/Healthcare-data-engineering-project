# ===========================================================================
# UNDERSTAND: data_extractor.py — Module 03 "pull data out of the hospital"
# ---------------------------------------------------------------------------
# Responsibility split (important for interviews):
#   SQLQueryRunner  → HOW to talk to Postgres (connection, timing, errors)
#   DataExtractor   → WHAT to pull (which .sql file) and WHERE to save (CSV)
#
# Input:  healthcare schema in Supabase (4 tables) OR synthetic fallback
# Output: data/raw-data.csv — one WIDE row per visit/bill with ~30 columns
#
# Why a wide CSV? Finance asked for "one file I can open in Excel that has
# patient + appointment + doctor + billing together." Normalized tables in
# Postgres are correct for operations; a flat extract is correct for handoff.
# ===========================================================================

import sys, pathlib

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import config
from config import INDUSTRY, DB_AVAILABLE, logger
from src.query_runner import SQLQueryRunner


class DataExtractor:
    """
    Runs the production extraction query and saves raw-data.csv.

    This class has one job: extract the data and save it.
    SQLQueryRunner handles connection and execution.
    DataExtractor handles the business logic of which query to run.

    The extraction query joins four tables from the healthcare schema:
        patients → appointments → doctors → billing

    Output columns (31 total):
        patient_id, patient_first_name, patient_last_name, date_of_birth,
        gender, blood_type, city, insurance_type, patient_email, patient_phone,
        appointment_id, appointment_date, appointment_time, appointment_status,
        visit_type, duration_mins, appointment_fee, notes,
        doctor_id, doctor_first_name, doctor_last_name, specialization,
        doctor_years_exp, bill_id, amount_charged, insurance_paid,
        patient_paid, payment_status, payment_method, bill_date
    """

    def __init__(self):
        # -------------------------------------------------------------------
        # Constructor: prepare empty state. No database call happens here yet.
        # self.runner is a SQLQueryRunner instance — reusable query executor.
        # self.raw_df will hold the pandas DataFrame after extract() succeeds.
        # self._status is a simple string flag for debugging (__str__).
        # -------------------------------------------------------------------
        self.industry  = INDUSTRY
        self.runner    = SQLQueryRunner()
        self.raw_df    = None    # populated by extract()
        self._status   = "ready"

    def extract(self) -> "DataExtractor":
        """
        Run 05_extract_raw_data.sql and load results into self.raw_df.

        The SQL file contains the full 4-table join across:
            healthcare.patients, healthcare.appointments,
            healthcare.doctors, healthcare.billing

        If the database is unavailable, generates synthetic healthcare data
        so the pipeline can still be demonstrated offline.
        """
        logger.info(f"[EXTRACT] Starting extraction — industry: {self.industry}")

        # -------------------------------------------------------------------
        # Branch 1: live database (DB_AVAILABLE set True in config.py at import)
        # run_file("extract_raw_data.sql") reads the ENTIRE sql file as one string
        # and sends it to Postgres. The file has many SELECTs; pd.read_sql returns
        # the result of the LAST statement in the file (Section 5 — production join).
        # -------------------------------------------------------------------
        if DB_AVAILABLE:
            self.raw_df = self.runner.run_file("extract_raw_data.sql")
        else:
            logger.warning("[EXTRACT] DB unavailable — generating synthetic healthcare raw data")
            self.raw_df = self._synthetic_raw_data()

        # -------------------------------------------------------------------
        # Safety net: empty DataFrame (query error, wrong file, no rows) → synthetic
        # so run.py Part 3 (ETL) still has something to clean for demos.
        # -------------------------------------------------------------------
        if self.raw_df is None or len(self.raw_df) == 0:
            logger.warning("[EXTRACT] Query returned 0 rows — using synthetic data")
            self.raw_df = self._synthetic_raw_data()

        self._status = "extracted"
        logger.info(
            f"[EXTRACT] {len(self.raw_df):,} rows × {self.raw_df.shape[1]} columns extracted"
        )
        return self

    def save(self) -> "DataExtractor":
        """
        Save self.raw_df to raw-data.csv.
        This file is the input to Module 05 ETL.
        """
        if self.raw_df is None or len(self.raw_df) == 0:
            logger.error("[EXTRACT] No data to save. Run extract() first.")
            return self

        # -------------------------------------------------------------------
        # Why `import config` and config.RAW_DATA_PATH instead of
        # from config import RAW_DATA_PATH?
        #   import config → always reads the CURRENT path from the config module.
        #   from config import RAW_DATA_PATH → copies the path value once at import;
        #   tests that reassign config.RAW_DATA_PATH would not affect save().
        #
        # to_csv(..., index=False): do not write the DataFrame's row index (0,1,2...)
        # as an extra "Unnamed: 0" column — a common pandas beginner mistake.
        # -------------------------------------------------------------------
        self.raw_df.to_csv(config.RAW_DATA_PATH, index=False, encoding="utf-8")
        file_size_kb = config.RAW_DATA_PATH.stat().st_size / 1024
        logger.info(
            f"[EXTRACT] Saved {len(self.raw_df):,} rows to "
            f"{config.RAW_DATA_PATH.name} ({file_size_kb:.1f} KB)"
        )
        self._status = "saved"
        return self

    def report(self) -> None:
        """Print a summary of the extraction results."""
        if self.raw_df is None:
            print("No data extracted. Run extract() first.")
            return

        print()
        print("=" * 60)
        print(f"  MODULE 03 — EXTRACTION COMPLETE | {self.industry.upper()}")
        print("=" * 60)
        print(f"  Rows extracted:    {len(self.raw_df):,}")
        print(f"  Columns:           {self.raw_df.shape[1]}")
        print(f"  Output file:       {config.RAW_DATA_PATH.name}")
        if config.RAW_DATA_PATH.exists():
            print(f"  File size:         {config.RAW_DATA_PATH.stat().st_size / 1024:.1f} KB")

        print()
        print("  DATA QUALITY ISSUES IN RAW DATA (intentional — Module 05 will fix):")

        # -------------------------------------------------------------------
        # isna() marks missing cells; .sum() counts True per column.
        # We only print columns that have at least one null — transparency for ETL.
        # -------------------------------------------------------------------
        nulls = self.raw_df.isna().sum()
        for col in nulls[nulls > 0].index:
            pct = round(nulls[col] / len(self.raw_df) * 100, 1)
            print(f"    NULL {col}: {nulls[col]:,} rows ({pct}%)")

        # -------------------------------------------------------------------
        # Business sanity checks on RAW data (not fixing here — just reporting).
        # Negative charges and overpayments are real-world data entry errors
        # the transformer will repair in Module 05.
        # -------------------------------------------------------------------
        if "amount_charged" in self.raw_df.columns:
            neg_charges = (self.raw_df["amount_charged"] < 0).sum()
            if neg_charges:
                print(f"    Negative amount_charged: {neg_charges} rows")

        if "insurance_paid" in self.raw_df.columns and "patient_paid" in self.raw_df.columns:
            if "amount_charged" in self.raw_df.columns:
                overpaid = (
                    (self.raw_df["insurance_paid"] + self.raw_df["patient_paid"])
                    > self.raw_df["amount_charged"]
                ).sum()
                if overpaid:
                    print(f"    Overpaid bills (insurance + patient > charged): {overpaid} rows")

        if "appointment_status" in self.raw_df.columns:
            status_counts = self.raw_df["appointment_status"].value_counts()
            print()
            print("  APPOINTMENT STATUS BREAKDOWN:")
            for status, count in status_counts.items():
                pct = round(count / len(self.raw_df) * 100, 1)
                print(f"    {status}: {count:,} ({pct}%)")

        if "payment_status" in self.raw_df.columns:
            pay_counts = self.raw_df["payment_status"].value_counts()
            print()
            print("  PAYMENT STATUS BREAKDOWN:")
            for status, count in pay_counts.items():
                pct = round(count / len(self.raw_df) * 100, 1)
                print(f"    {status}: {count:,} ({pct}%)")

        print()
        print("  NEXT STEP: Copy raw-data.csv to Module 05 and run:")
        print("    python module-05-data-engineering-and-etl/run.py")
        print("=" * 60)

    @staticmethod
    def _synthetic_raw_data(n: int = 300) -> pd.DataFrame:
        """
        Generate synthetic raw data matching the healthcare extraction query output.

        Mirrors the column structure of extract_raw_data.sql:
            patients + appointments + doctors + billing (4-table join)
        Intentionally includes nulls and edge cases for Module 05 ETL practice.
        """
        import random
        import datetime
        import numpy as np

        # Fixed seed → same "random" data every run (reproducible demos and tests)
        random.seed(42)
        np.random.seed(42)

        # Pools of realistic values — random.choice picks one per simulated row
        first_names     = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer",
                           "Michael", "Linda", "William", "Barbara", "Kwame", "Abena"]
        last_names      = ["Smith", "Johnson", "Williams", "Brown", "Jones",
                           "Garcia", "Miller", "Davis", "Mensah", "Asante"]
        cities          = ["Greensboro", "Charlotte", "Raleigh", "Durham",
                           "Fayetteville", "Wilmington", None]
        blood_types     = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
        genders         = ["Male", "Female", "Non-binary", None]
        insurance_types = ["Medicare", "Medicaid", "Blue Cross", "Aetna", "Cigna", "Self-Pay"]
        specializations = ["Cardiology", "Neurology", "Oncology", "Pediatrics",
                           "Orthopedics", "General Practice", "Dermatology"]
        visit_types     = ["In-Person", "Telehealth", "Follow-Up", "Emergency"]
        appt_statuses   = ["Completed", "Cancelled", "No-Show", "Scheduled"]
        payment_statuses= ["Paid", "Unpaid", "Partial"]
        payment_methods = ["Insurance", "Cash", "Credit Card", "Bank Transfer", None]

        rows = []
        # Loop builds n dictionaries — each dict is one wide CSV row
        for i in range(1, n + 1):
            p_first     = random.choice(first_names)
            p_last      = random.choice(last_names)
            dob_year    = random.randint(1940, 2005)
            dob         = f"{dob_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

            appt_year   = random.randint(2022, 2024)
            appt_month  = random.randint(1, 12)
            appt_day    = random.randint(1, 28)
            appt_date   = f"{appt_year}-{appt_month:02d}-{appt_day:02d}"
            appt_time   = f"{random.randint(8,17):02d}:{random.choice(['00','15','30','45'])}"
            appt_status = random.choice(appt_statuses)
            duration    = random.choice([15, 30, 45, 60, 90, None])
            fee         = round(random.uniform(50, 800), 2) if random.random() > 0.02 else None

            d_first     = random.choice(first_names)
            d_last      = random.choice(last_names)
            spec        = random.choice(specializations)
            years_exp   = random.choice([1, 3, 5, 8, 10, 15, 20, 25])

            charged     = round(random.uniform(100, 1500), 2) if random.random() > 0.01 else None
            ins_paid    = round(charged * random.uniform(0.0, 0.8), 2) if charged else 0.0
            pat_paid    = round(charged - ins_paid, 2) if charged else 0.0
            # Deliberately corrupt ~5% of rows for ETL practice
            if random.random() < 0.05:
                ins_paid = None
            if random.random() < 0.03:
                pat_paid = None
            pay_status  = random.choice(payment_statuses)
            pay_method  = random.choice(payment_methods)
            bill_date   = appt_date

            rows.append({
                "patient_id":          i,
                "patient_first_name":  p_first,
                "patient_last_name":   p_last,
                "date_of_birth":       dob,
                "gender":              random.choice(genders),
                "blood_type":          random.choice(blood_types),
                "city":                random.choice(cities),
                "insurance_type":      random.choice(insurance_types),
                "patient_email":       f"patient{i}@email.com" if random.random() > 0.05 else None,
                "patient_phone":       f"336-{random.randint(100,999)}-{random.randint(1000,9999)}"
                                       if random.random() > 0.05 else None,
                "appointment_id":      1000 + i,
                "appointment_date":    appt_date,
                "appointment_time":    appt_time,
                "appointment_status":  appt_status,
                "visit_type":          random.choice(visit_types),
                "duration_mins":       duration,
                "appointment_fee":     fee,
                "notes":               random.choice(["Routine checkup", "Follow-up required",
                                                      "Referred to specialist", None, None]),
                "doctor_id":           100 + (i % 20),
                "doctor_first_name":   d_first,
                "doctor_last_name":    d_last,
                "specialization":      spec,
                "doctor_years_exp":    years_exp,
                "bill_id":             2000 + i,
                "amount_charged":      charged,
                "insurance_paid":      ins_paid,
                "patient_paid":        pat_paid,
                "payment_status":      pay_status,
                "payment_method":      pay_method,
                "bill_date":           bill_date,
            })

        return pd.DataFrame(rows)

    def __str__(self):
        return f"DataExtractor(industry={self.industry!r}, status={self._status!r})"

    def __repr__(self):
        return f"DataExtractor(industry={self.industry!r})"
