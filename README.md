# Healthcare Analytics Pipeline

End-to-end data pipeline for hospital operations analytics: extract joined patient, appointment, and billing data from PostgreSQL, validate and clean it, and publish analytics-ready datasets for reporting and downstream BI.

**Context:** Built for **MedCore Analytics** (client: **St. Aurelius General Hospital**). Operational data lives in a `healthcare` schema on Supabase/PostgreSQL; Finance and analytics need a reliable flat extract plus cleaned dimension and fact tables.

---

## Overview

This repository implements a two-stage analytics workflow:

1. **SQL extraction** — Query the `healthcare` schema (patients, appointments, doctors, billing), demonstrate core SQL patterns, and produce a unified raw export (`data/raw-data.csv`).
2. **ETL processing** — Load the export, run validation gates, apply healthcare-specific cleaning rules, derive billing and demographic fields, and load star-schema-style outputs into `data/processed/`.

The pipeline is designed for repeatability: configurable paths, structured logging, automated tests, and a single entry point (`run.py`) for full runs.

---

## Architecture

```
PostgreSQL (healthcare schema)
        │
        ▼
   SQL extraction          sql/extract_raw_data.sql
        │                  src/data_extractor.py
        ▼
   data/raw-data.csv       joined flat extract (~30 columns)
        │
        ▼
   ETL pipeline            src/etl_pipeline.py
        │                  ├─ src/validator.py   (pre/post checks)
        │                  └─ src/transformer.py (clean + derive)
        ▼
   data/processed/
        ├─ clean-data.csv      full cleaned dataset
        ├─ patients.csv        patient dimension
        ├─ doctors.csv         doctor dimension
        ├─ appointments.csv    appointment records
        ├─ billing.csv         billing + payment metrics
        └─ quality-report.txt  validation summary
```

---

## Features

### Data extraction
- Four-table join across `healthcare.patients`, `appointments`, `doctors`, and `billing`
- Schema-qualified SQL suitable for DBeaver and production Postgres (`healthcare.table_name`)
- SQL coverage: filtering, aggregation, multi-table joins, CTEs, and window functions
- Offline fallback with synthetic data when the database is unavailable

### ETL and data quality
- **Pre-transform validation** — schema contract, required columns, non-null business keys
- **Cleaning** — whitespace normalization, title-case names, date parsing, numeric coercion
- **Billing logic** — clip negative charges, reconcile overpayments, zero payments on $0 bills
- **Imputation** — categorical nulls → `Unknown` where appropriate
- **Derived fields** — `age`, `age_group`, `total_paid`, `balance`, `is_paid_in_full`
- **Post-transform validation** — no negative amounts, no overpaid rows (cent-rounded), plausible ages
- **Dimensional outputs** — deduplicated patient/doctor tables plus appointment and billing facts

---

## Tech stack

| Layer        | Tools                          |
| ------------ | ------------------------------ |
| Database     | PostgreSQL (Supabase)          |
| Extraction   | SQL, SQLAlchemy, pandas        |
| ETL          | Python 3, pandas, numpy        |
| Config       | python-dotenv                  |
| Testing      | pytest                         |

---

## Project structure

```
P01-healthcare-sql/
├── config.py                 paths, DB connection, ETL settings
├── run.py                    pipeline entry point
├── requirements.txt
├── sql/
│   └── extract_raw_data.sql  extraction + analytical SQL
├── src/
│   ├── data_extractor.py     Postgres → raw-data.csv
│   ├── query_runner.py       SQL execution + demos
│   ├── validator.py          raw/clean validation
│   ├── transformer.py        cleaning + derived columns
│   └── etl_pipeline.py       orchestration (extract → load)
├── data/
│   ├── raw-data.csv          extraction output (gitignored)
│   └── processed/            ETL outputs (gitignored)
├── tests/
│   ├── tests_sql.py          extraction + SQL contract tests
│   └── test_pipeline.py      ETL unit + integration tests
└── verify_connection.py      quick DB connectivity check
```

---

## Getting started

### Prerequisites
- Python 3.11+
- Access to a PostgreSQL database with the `healthcare` schema (or use synthetic fallback)

### Setup

```bash
git clone <your-repo-url>
cd P01-healthcare-sql

python -m venv gt-p1sql-env
# Windows
gt-p1sql-env\Scripts\activate
# macOS/Linux
source gt-p1sql-env/bin/activate

pip install -r requirements.txt
```

### Environment

Copy `.env.example` to `.env` and set your connection string:

```env
DB_URL=postgresql+pg8000://user:password@host:port/database
```

Optional ETL settings:

```env
ETL_STRICT=false          # abort pipeline on validation errors if true
ETL_DROP_INVALID=true     # drop rows with missing key IDs
```

Verify connectivity:

```bash
python verify_connection.py
```

### Run the full pipeline

```bash
python run.py
```

This runs SQL demonstrations, production extraction to `data/raw-data.csv`, then the ETL stage into `data/processed/`.

ETL only (when `raw-data.csv` already exists):

```bash
python -c "from src.etl_pipeline import ETLPipeline; ETLPipeline().run().report()"
```

---

## Data outputs

| File | Description |
| ---- | ----------- |
| `data/raw-data.csv` | Flat join of patients, appointments, doctors, billing |
| `data/processed/clean-data.csv` | Cleaned flat dataset with derived columns |
| `data/processed/patients.csv` | Patient dimension (deduplicated) |
| `data/processed/doctors.csv` | Doctor dimension (deduplicated) |
| `data/processed/appointments.csv` | Appointment fact table |
| `data/processed/billing.csv` | Billing fact with payment totals and balance |
| `data/processed/quality-report.txt` | Validation summary from the latest ETL run |

CSV outputs under `data/` are gitignored; regenerate them with `python run.py`.

---

## Testing

```bash
pytest tests/ -v
```

| Suite | Focus |
| ----- | ----- |
| `tests/tests_sql.py` | SQL file contract, query runner behavior, extractor save logic, synthetic data rules |
| `tests/test_pipeline.py` | Validator, transformer steps, end-to-end ETL with temporary paths |

Tests use temporary directories for file I/O so local data files are not overwritten during test runs.

---

## Design notes

- **SQL style:** Tables are referenced as `healthcare.patients` (and similar) so scripts run directly in DBeaver/Postgres without template placeholders.
- **Python config:** `INDUSTRY = "healthcare"` in `config.py` drives dynamic SQL in `query_runner` demos; the on-disk SQL file uses the real schema name.
- **Validation:** Raw data is expected to be imperfect; the pipeline documents and fixes known issues (nulls, negative charges, overpayments) rather than silently passing bad data through.

---

## License

See [LICENSE](LICENSE).
