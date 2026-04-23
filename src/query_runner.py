# ================================================================
# src/query_runner.py
# ================================================================
# CONTEXT:
#   We wrote SQL in .sql files targeting the healthcare schema.
#   Now we need to EXECUTE those queries from Python and get back
#   pandas DataFrames we can work with in the rest of the pipeline.
#
# THE ANALOGY:
#   Think of SQLQueryRunner as a robust hospital lab system.
#   You hand it a test request (a SQL query string).
#   It sends that request to the PostgreSQL database.
#   The database sends back rows of data (the results).
#   SQLQueryRunner catches those rows and packages them as a
#   pandas DataFrame — ready for analysis or saving to CSV.
#
# KEY pandas FUNCTION: pd.read_sql()
#   pd.read_sql(sql_string, engine) executes SQL and returns a DataFrame.
#   This is what powers every Python + database workflow.
#
# WHY A CLASS AND NOT JUST pd.read_sql() DIRECTLY?
#   The class adds:
#     - Error handling    (what if the query fails?)
#     - Logging           (track what ran and when)
#     - Timing            (how long did each query take?)
#     - Audit history     (record of every query run in this session)
#     - Query file loading (reads from .sql files, not inline strings)
#   These extras make it production-grade rather than just a script.
#
# HEALTHCARE SCHEMA STRUCTURE:
#   healthcare.patients      — patient demographics and insurance
#   healthcare.appointments  — appointment records linked to patients + doctors
#   healthcare.doctors       — doctor profiles and specializations
#   healthcare.billing       — billing records linked to appointments
# ================================================================

import sys, pathlib, time

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from config import engine, DB_AVAILABLE, SQL_DIR, INDUSTRY, logger


class SQLQueryRunner:
    """
    Executes SQL queries against the Supabase PostgreSQL database.
    Returns results as pandas DataFrames.

    All queries target the 'healthcare' schema which contains:
        patients, appointments, doctors, billing

    Attributes
    ──────────
    industry   str           the configured industry schema ('healthcare')
    history    list[dict]    audit log of every query run this session
    """

    def __init__(self):
        self.industry = INDUSTRY          # 'healthcare' — set in config.py
        self.history  = []                # audit log: grows with every run() call
        logger.info(f"SQLQueryRunner ready — db_available: {DB_AVAILABLE}")

    # ------------------------------------------------------------------ #
    #  CORE METHODS                                                        #
    # ------------------------------------------------------------------ #

    def run(self, sql: str, params: dict = None) -> pd.DataFrame:
        """
        Execute a SQL query string and return results as a DataFrame.

        Args:
            sql     the SQL query string to execute
            params  optional dict for parameterised queries
                    e.g. params={"status": "Completed"}
                    used as WHERE status = :status in the SQL

        Returns:
            pd.DataFrame with query results.
            Returns an empty DataFrame if query fails — never raises.
        """
        if not DB_AVAILABLE or engine is None:
            logger.warning("[SQL] Database not available. Returning empty DataFrame.")
            return pd.DataFrame()

        # Replace {industry} placeholder with the actual schema name.
        # This makes SQL reusable: WHERE {industry}.patients → WHERE healthcare.patients
        sql = sql.replace("{industry}", self.industry)

        start_time = time.time()   # record start for performance logging

        try:
            # pd.read_sql() executes the SQL and returns a pandas DataFrame.
            # params → passed as bind parameters to prevent SQL injection.
            df = pd.read_sql(sql, engine, params=params)

            duration_ms = round((time.time() - start_time) * 1000, 1)

            # Record this run in the session audit log
            self.history.append({
                "sql_preview": sql[:80].strip(),   # first 80 chars for readability
                "rows":        len(df),
                "cols":        len(df.columns),
                "duration_ms": duration_ms,
                "status":      "success",
            })

            logger.info(
                f"[SQL] Query complete — "
                f"{len(df):,} rows × {len(df.columns)} cols | "
                f"{duration_ms}ms"
            )

            return df

        except Exception as e:
            self.history.append({
                "sql_preview": sql[:80].strip(),
                "rows":        0,
                "cols":        0,
                "duration_ms": round((time.time() - start_time) * 1000, 1),
                "status":      f"error: {str(e)[:100]}",
            })
            logger.error(f"[SQL] Query failed: {e}")
            return pd.DataFrame()   # safe empty return — callers check len(df) == 0

    def run_file(self, filename: str) -> pd.DataFrame:
        """
        Load a .sql file from the sql/ directory and execute it.

        Args:
            filename   name of the SQL file
                       e.g. "05_extract_raw_data.sql"

        Returns:
            pd.DataFrame with results of the query in the file.
        """
        sql_path = SQL_DIR / filename

        if not sql_path.exists():
            logger.error(f"[SQL] File not found: {sql_path}")
            return pd.DataFrame()

        logger.info(f"[SQL] Loading: {filename}")

        # Read the entire .sql file as a Python string
        sql_text = sql_path.read_text(encoding="utf-8")

        # Delegate execution to run() — all logging, timing, and
        # error handling is already handled there
        return self.run(sql_text)

    # ------------------------------------------------------------------ #
    #  DEMO METHODS — live teaching queries for the healthcare schema      #
    # ------------------------------------------------------------------ #

    def demo_basics(self) -> None:
        """
        Run selected demonstration queries showcasing basic SQL concepts
        against the healthcare schema.

        Covers: SELECT, DISTINCT, WHERE, LIMIT, ORDER BY, UNION ALL.
        Maps to Section 1 of healthcare_queries.sql.
        """
        demos = [
            (
                "Distinct appointment statuses",
                f"""SELECT DISTINCT status
                    FROM {self.industry}.appointments
                    ORDER BY status"""
            ),
            (
                "Distinct payment statuses in billing",
                f"""SELECT DISTINCT payment_status
                    FROM {self.industry}.billing
                    ORDER BY payment_status"""
            ),
            (
                "Row counts across all four tables",
                f"""SELECT 'patients'     AS table_name, COUNT(*) AS row_count
                    FROM {self.industry}.patients
                    UNION ALL
                    SELECT 'appointments',               COUNT(*)
                    FROM {self.industry}.appointments
                    UNION ALL
                    SELECT 'doctors',                    COUNT(*)
                    FROM {self.industry}.doctors
                    UNION ALL
                    SELECT 'billing',                    COUNT(*)
                    FROM {self.industry}.billing"""
            ),
            (
                "Most recent 10 appointments",
                f"""SELECT
                        appointment_id,
                        patient_id,
                        doctor_id,
                        appointment_date,
                        status,
                        visit_type,
                        fee
                    FROM {self.industry}.appointments
                    ORDER BY appointment_date DESC
                    LIMIT 10"""
            ),
        ]

        for title, sql in demos:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    def demo_aggregation(self) -> None:
        """
        Run demonstration aggregation queries against the healthcare schema.

        Covers: COUNT, SUM, AVG, GROUP BY, ORDER BY, DATE_TRUNC.
        Maps to Section 2 of healthcare_queries.sql.
        """
        demos = [
            (
                "Total billing summary (revenue overview)",
                f"""SELECT
                        COUNT(*)                      AS total_bills,
                        ROUND(SUM(amount_charged)::NUMERIC, 2)   AS total_charged,
                        ROUND(SUM(insurance_paid)::NUMERIC, 2)   AS total_insurance_paid,
                        ROUND(SUM(patient_paid)::NUMERIC, 2)     AS total_patient_paid
                    FROM {self.industry}.billing"""
            ),
            (
                "Revenue breakdown by payment status",
                f"""SELECT
                        payment_status,
                        COUNT(*)                              AS num_bills,
                        ROUND(SUM(amount_charged)::NUMERIC, 2) AS total_charged,
                        ROUND(SUM(patient_paid)::NUMERIC, 2)   AS total_collected
                    FROM {self.industry}.billing
                    GROUP BY payment_status
                    ORDER BY total_charged DESC"""
            ),
            (
                "Appointment volume by visit type",
                f"""SELECT
                        visit_type,
                        COUNT(*)                            AS total_visits,
                        ROUND(AVG(duration_mins)::NUMERIC, 1) AS avg_duration_mins,
                        ROUND(AVG(fee)::NUMERIC, 2)           AS avg_fee
                    FROM {self.industry}.appointments
                    GROUP BY visit_type
                    ORDER BY total_visits DESC"""
            ),
            (
                "Patient distribution by city",
                f"""SELECT
                        city,
                        COUNT(*) AS num_patients
                    FROM {self.industry}.patients
                    GROUP BY city
                    ORDER BY num_patients DESC
                    LIMIT 10"""
            ),
        ]

        for title, sql in demos:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    def demo_joins(self) -> None:
        """
        Run demonstration join queries against the healthcare schema.

        Covers: INNER JOIN across patients, appointments, doctors, billing.
        Maps to Section 3 of healthcare_queries.sql.
        """
        demos = [
            (
                "Top 10 doctors by total revenue generated",
                f"""SELECT
                        d.first_name || ' ' || d.last_name  AS doctor_name,
                        d.specialization,
                        COUNT(b.bill_id)                     AS total_bills,
                        ROUND(SUM(b.amount_charged)::NUMERIC, 2) AS total_revenue
                    FROM {self.industry}.doctors d
                    JOIN {self.industry}.appointments a
                        ON d.doctor_id = a.doctor_id
                    JOIN {self.industry}.billing b
                        ON a.appointment_id = b.appointment_id
                    GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization
                    ORDER BY total_revenue DESC
                    LIMIT 10"""
            ),
            (
                "Patients with outstanding unpaid balances",
                f"""SELECT
                        p.first_name || ' ' || p.last_name  AS patient_name,
                        p.city,
                        p.insurance_type,
                        COUNT(b.bill_id)                     AS unpaid_bills,
                        ROUND(SUM(b.amount_charged)::NUMERIC, 2) AS total_owed
                    FROM {self.industry}.patients p
                    JOIN {self.industry}.billing b
                        ON p.patient_id = b.patient_id
                    WHERE b.payment_status = 'Unpaid'
                    GROUP BY p.patient_id, p.first_name, p.last_name,
                             p.city, p.insurance_type
                    ORDER BY total_owed DESC
                    LIMIT 10"""
            ),
            (
                "Full 4-table join — sample of 10 rows",
                f"""SELECT
                        p.first_name                 AS patient_first,
                        p.last_name                  AS patient_last,
                        a.appointment_date,
                        a.status                     AS appt_status,
                        a.visit_type,
                        d.first_name || ' ' || d.last_name AS doctor_name,
                        d.specialization,
                        b.amount_charged,
                        b.payment_status
                    FROM {self.industry}.patients p
                    JOIN {self.industry}.appointments a
                        ON p.patient_id = a.patient_id
                    JOIN {self.industry}.doctors d
                        ON a.doctor_id = d.doctor_id
                    JOIN {self.industry}.billing b
                        ON a.appointment_id = b.appointment_id
                    ORDER BY a.appointment_date DESC
                    LIMIT 10"""
            ),
        ]

        for title, sql in demos:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    def demo_window_functions(self) -> None:
        """
        Run demonstration CTE and window function queries.

        Covers: RANK() OVER, SUM() OVER, LAG(), PARTITION BY, CTEs.
        Maps to Section 4 of healthcare_queries.sql.
        """
        demos = [
            (
                "Top 10 patients ranked by total spend",
                f"""SELECT
                        p.first_name || ' ' || p.last_name      AS patient_name,
                        p.city,
                        ROUND(SUM(b.amount_charged)::NUMERIC, 2) AS total_charged,
                        RANK() OVER (
                            ORDER BY SUM(b.amount_charged) DESC
                        )                                         AS spend_rank
                    FROM {self.industry}.patients p
                    JOIN {self.industry}.billing b
                        ON p.patient_id = b.patient_id
                    GROUP BY p.patient_id, p.first_name, p.last_name, p.city
                    ORDER BY spend_rank
                    LIMIT 10"""
            ),
            (
                "Doctors ranked by revenue within each specialization",
                f"""SELECT
                        d.first_name || ' ' || d.last_name        AS doctor_name,
                        d.specialization,
                        ROUND(SUM(b.amount_charged)::NUMERIC, 2)   AS total_revenue,
                        RANK() OVER (
                            PARTITION BY d.specialization
                            ORDER BY SUM(b.amount_charged) DESC
                        )                                           AS rank_in_spec
                    FROM {self.industry}.doctors d
                    JOIN {self.industry}.appointments a
                        ON d.doctor_id = a.doctor_id
                    JOIN {self.industry}.billing b
                        ON a.appointment_id = b.appointment_id
                    GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization
                    ORDER BY d.specialization, rank_in_spec
                    LIMIT 15"""
            ),
            (
                "Month-over-month revenue growth (CTE + LAG)",
                f"""WITH monthly_revenue AS (
                        SELECT
                            DATE_TRUNC('month', bill_date)           AS month,
                            ROUND(SUM(amount_charged)::NUMERIC, 2)   AS revenue
                        FROM {self.industry}.billing
                        GROUP BY DATE_TRUNC('month', bill_date)
                    )
                    SELECT
                        month,
                        revenue,
                        LAG(revenue) OVER (ORDER BY month)           AS prev_month,
                        ROUND(
                            (revenue - LAG(revenue) OVER (ORDER BY month))
                            / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) * 100,
                        2)                                           AS pct_growth
                    FROM monthly_revenue
                    ORDER BY month"""
            ),
        ]

        for title, sql in demos:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    # ------------------------------------------------------------------ #
    #  DUNDER METHODS                                                      #
    # ------------------------------------------------------------------ #

    def __str__(self) -> str:
        return (
            f"SQLQueryRunner("
            f"industry={self.industry!r}, "
            f"queries_run={len(self.history)})"
        )

    def __repr__(self) -> str:
        return f"SQLQueryRunner(industry={self.industry!r})"