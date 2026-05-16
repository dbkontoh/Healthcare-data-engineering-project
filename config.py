# The purpose of this file is to verify that I have a connection to the database
# and that I can access the learner schema.
# I should be able to run this file without any errors.
# In case of an error, please check the .env file and make sure that your DB_URL is correct.

# ===========================================================================
# UNDERSTAND: What is config.py and why does every other file import it?
# ---------------------------------------------------------------------------
# Think of config.py as the project's control panel — not the factory floor.
# When data_extractor.py needs to know WHERE to save raw-data.csv, it does not
# hard-code "C:\P01-healthcare-sql\data\raw-data.csv" inside that file. It
# imports RAW_DATA_PATH from here. That way:
#   • You change a path once, and extraction + ETL + tests all stay in sync.
#   • Tests can temporarily point paths at a temp folder without editing five files.
#   • A recruiter reading the repo sees "configuration separated from logic."
#
# This file runs as soon as ANY other module does `import config` or
# `from config import ...`. That means the database connection test at the
# bottom executes once at startup — before run.py even prints its banner.
# ===========================================================================

# ===========================================================================
# UNDERSTAND: Domain constants — who is this project for?
# ===========================================================================
# INDUSTRY is used by SQLQueryRunner when it builds SQL strings inside Python
# (demo_basics, demo_joins, etc.). Those demos use f"... {self.industry}.patients"
# which becomes healthcare.patients at runtime.
#
# Your file sql/extract_raw_data.sql uses healthcare. directly — that is correct
# for DBeaver and Postgres. INDUSTRY in config does NOT rename the database schema;
# it only labels the project and powers dynamic SQL written in Python code.
# ---------------------------------------------------------------------------
INDUSTRY       = "healthcare"   # change to your industry
LEARNER_SCHEMA = "learner_43"   # DO NOT CHANGE

# ---------------------------------------------------------------------------
# Imports — each library's job in this pipeline
# ---------------------------------------------------------------------------
# os          → read DB_URL and ETL_STRICT from the environment (.env file).
# pathlib     → build file paths that work on Windows AND Mac (uses / not \).
# ssl         → encrypt traffic to cloud Postgres (Supabase requires this).
# sqlalchemy  → speak to PostgreSQL from Python (connection pool + run SQL).
# dotenv      → load key=value pairs from .env into os.environ before we read them.
# logging     → structured log lines with timestamps (better than print for ops).
# ---------------------------------------------------------------------------
import os, logging, pathlib, ssl
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# load_dotenv() looks for a file named .env next to this project and loads secrets.
# Example line in .env: DB_URL=postgresql+pg8000://user:password@host:5432/db
# NEVER commit .env to GitHub — it contains credentials.
load_dotenv()

# ===========================================================================
# UNDERSTAND: Path constants — the "addresses" of every file the pipeline touches
# ---------------------------------------------------------------------------
# pathlib.Path(__file__)  →  path to THIS file (config.py)
# .resolve().parent       →  absolute path to the project ROOT folder
# _root / "data" / "x"    →  join folders safely (better than string concatenation)
#
# RAW_DATA_PATH     = output of Module 03 (messy joined extract from Postgres)
# PROCESSED_DIR/*   = outputs of Module 05 (clean + split tables for analytics)
# ===========================================================================
_root        = pathlib.Path(__file__).resolve().parent
SQL_DIR      = _root / "sql"           # where .sql files live
DATA_DIR     = _root / "data"
RAW_DATA_PATH= DATA_DIR / "raw-data.csv"   # Module 03 extraction output

PROCESSED_DIR        = DATA_DIR / "processed"
CLEAN_DATA_PATH      = PROCESSED_DIR / "clean-data.csv"
PATIENTS_OUT_PATH    = PROCESSED_DIR / "patients.csv"
DOCTORS_OUT_PATH     = PROCESSED_DIR / "doctors.csv"
APPOINTMENTS_OUT_PATH= PROCESSED_DIR / "appointments.csv"
BILLING_OUT_PATH     = PROCESSED_DIR / "billing.csv"
QUALITY_REPORT_PATH  = PROCESSED_DIR / "quality-report.txt"

# Create data/processed/ on disk if it does not exist yet.
# parents=True  → create parent folders too (data/ then data/processed/)
# exist_ok=True → do not crash if the folder is already there
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ===========================================================================
# UNDERSTAND: ETL behavior flags (read from .env, default if missing)
# ---------------------------------------------------------------------------
# ETL_STRICT=false (default): validation errors are logged but pipeline continues.
# ETL_STRICT=true:           any validation error raises an exception and stops.
#
# ETL_DROP_INVALID is reserved for future use / documentation; the transformer
# already drops rows with null patient_id, appointment_id, or bill_id.
# os.getenv("KEY", "default") returns the env value or "default" if unset.
# .lower() == "true" turns the STRING "true" into Python boolean True.
# ===========================================================================
ETL_STRICT       = os.getenv("ETL_STRICT", "false").lower() == "true"
ETL_DROP_INVALID = os.getenv("ETL_DROP_INVALID", "true").lower() == "true"

# ===========================================================================
# UNDERSTAND: EXPECTED_COLUMNS — the "data contract" between Module 03 and 05
# ---------------------------------------------------------------------------
# When extract_raw_data.sql runs, it must produce a CSV with EXACTLY these 30
# column names (order can differ; names must match). DataValidator.validate_raw()
# compares the loaded DataFrame to this list:
#   • Missing column  → hard ERROR (pipeline knows input is wrong shape)
#   • Extra column    → WARNING only (kept in the data)
#
# Why a contract? In real analytics engineering, upstream (SQL extract) and
# downstream (ETL) are often built by different people/weeks. A named list
# in config prevents silent breakage when someone adds a column in SQL but
# forgets to update the cleaner.
# ===========================================================================
# Column contract from Module 03 — extract_raw_data.sql → raw-data.csv.
# Module 05 validator asserts the raw input matches this exact shape.
EXPECTED_COLUMNS = [
    "patient_id", "patient_first_name", "patient_last_name", "date_of_birth",
    "gender", "blood_type", "city", "insurance_type", "patient_email", "patient_phone",
    "appointment_id", "appointment_date", "appointment_time", "appointment_status",
    "visit_type", "duration_mins", "appointment_fee", "notes",
    "doctor_id", "doctor_first_name", "doctor_last_name", "specialization",
    "doctor_years_exp", "bill_id", "amount_charged", "insurance_paid",
    "patient_paid", "payment_status", "payment_method", "bill_date",
]

# ===========================================================================
# UNDERSTAND: Logging setup — one logger the whole project shares
# ---------------------------------------------------------------------------
# basicConfig runs once: every logger.info() / warning() / error() in src/*
# will print like: 2026-05-14 13:00:00 [INFO] darko — message
# This helps you trace extract → validate → transform → load in the terminal.
# ===========================================================================
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("darko")

# ===========================================================================
# UNDERSTAND: Database engine — the persistent connection to Supabase/Postgres
# ---------------------------------------------------------------------------
# Cloud Postgres (Supabase) typically requires SSL. For local learning we relax
# certificate verification below. In production you would use proper CA certs.
#
# create_engine(DB_URL) does NOT connect immediately — it prepares a pool.
# pool_pre_ping=True: before each use, send a tiny "are you alive?" ping so
# stale connections (laptop slept, VPN dropped) do not cause cryptic errors.
#
# DB_URL format: postgresql+pg8000://USER:PASSWORD@HOST:PORT/DATABASE
#   postgresql  → dialect (Postgres)
#   pg8000      → Python driver library (see requirements.txt)
# ===========================================================================
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode    = ssl.CERT_NONE

engine = create_engine(
    os.getenv("DB_URL"),
    connect_args={"ssl_context": ssl_context},
    pool_pre_ping=True
)

# ===========================================================================
# UNDERSTAND: DB_AVAILABLE — fail gracefully when the hospital DB is unreachable
# ---------------------------------------------------------------------------
# We attempt ONE simple query at import time: SELECT 1
#   Success → DB_AVAILABLE = True  → DataExtractor runs real SQL from Postgres
#   Failure → DB_AVAILABLE = False → DataExtractor builds synthetic fake rows
#
# Why? So you can demo the ETL on a flight without Wi‑Fi: extraction still
# produces raw-data.csv, and the ETL stage still runs. The flag is also printed
# in run.py so you immediately see whether numbers came from Supabase or/faker.
# ===========================================================================
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    DB_AVAILABLE = True
    logger.info("Database connection verified — DB_AVAILABLE: True")
except Exception as e:
    DB_AVAILABLE = False
    logger.warning(f"Database unreachable — DB_AVAILABLE: False | {e}")
