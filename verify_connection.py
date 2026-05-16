# ===========================================================================
# UNDERSTAND: verify_connection.py — minimal "can I reach the database?" script
# ---------------------------------------------------------------------------
# Before running the full pipeline, analysts often run a 10-line smoke test.
# This file does exactly one thing:
#   1. Load DB_URL from .env
#   2. Open a SQLAlchemy engine to Supabase/Postgres
#   3. Run SELECT COUNT(*) FROM healthcare.patients
#   4. Print the result and "Connected!"
#
# If this fails, fix .env / VPN / credentials before debugging run.py.
# ===========================================================================

import os
import ssl
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# ===========================================================================
# UNDERSTAND: SSL block — encrypted tunnel to Supabase
# ---------------------------------------------------------------------------
# Cloud databases require TLS. These two lines disable strict certificate
# hostname checks for local learning environments (not production best practice).
# ===========================================================================
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ===========================================================================
# UNDERSTAND: create_engine — factory for database connections (from config.py)
# ===========================================================================
engine = create_engine(
    os.getenv("DB_URL"),
    connect_args={"ssl_context": ssl_context},
    pool_pre_ping=True
)

# ===========================================================================
# UNDERSTAND: pd.read_sql — run one query, get back a small table with patient count
# ===========================================================================
# healthcare.patients means: schema "healthcare", table "patients" (not a Python variable).
df = pd.read_sql("SELECT COUNT(*) AS patients FROM healthcare.patients", engine)
print(df)
print("Connected!")
