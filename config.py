# The purpose of this file is to verify that I have a connection to the database
# and that I can access the learner schema.
# I should be able to run this file without any errors.
# In case of an error, please check the .env file and make sure that your DB_URL is correct.

INDUSTRY       = "healthcare"   # change to your industry
LEARNER_SCHEMA = "learner_43"   # DO NOT CHANGE

import os, logging, pathlib, ssl
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────
_root        = pathlib.Path(__file__).resolve().parent
SQL_DIR      = _root / "sql"           # where .sql files live
RAW_DATA_PATH= _root / "data" / "raw-data.csv"  # extraction output

# ── Logger ───────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("darko")

# ── Database connection ───────────────────────────────────────────────
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode    = ssl.CERT_NONE

engine = create_engine(
    os.getenv("DB_URL"),
    connect_args={"ssl_context": ssl_context},
    pool_pre_ping=True
)

# ── DB_AVAILABLE — test the connection once at startup ────────────────
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    DB_AVAILABLE = True
    logger.info("Database connection verified — DB_AVAILABLE: True")
except Exception as e:
    DB_AVAILABLE = False
    logger.warning(f"Database unreachable — DB_AVAILABLE: False | {e}")