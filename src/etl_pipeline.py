# ================================================================
# src/etl_pipeline.py — P01 Healthcare Module 05 (ETL)
# ================================================================
# CONTEXT:
#   Module 03 wrote data/raw-data.csv. Module 05 is responsible for
#   turning that messy extract into analytics-ready outputs in
#   data/processed/.
#
# THE ANALOGY:
#   Think of ETLPipeline as the hospital's medical records department.
#   It receives intake forms (raw-data.csv), runs them through
#   triage (validator), tidies them up (transformer), runs a final
#   discharge check (validator again), then files them in the
#   processed records room (data/processed/).
#
# FLOW:
#   extract → validate_raw → transform → validate_clean → load
#
# DESIGN:
#   Each stage is its own chainable method returning self, mirroring
#   the pattern used by DataExtractor in src/data_extractor.py.
#   The convenience method `run()` just composes them.
#
# OUTPUTS (in data/processed/):
#   clean-data.csv         flat clean dataset (one row per bill)
#   patients.csv           patient dimension
#   doctors.csv            doctor dimension
#   appointments.csv       appointment fact
#   billing.csv            billing fact
#   quality-report.txt     human-readable validation summary
# ================================================================

# ===========================================================================
# UNDERSTAND: Imports and path bootstrap (same pattern as other src/* files)
# ---------------------------------------------------------------------------
# Optional[pd.DataFrame] tells type checkers: raw_df may be None until extract().
# We walk up directories until config.py is found, then add project root to sys.path.
# ===========================================================================
import sys, pathlib
from typing import Optional

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from config import (
    RAW_DATA_PATH,
    CLEAN_DATA_PATH,
    PATIENTS_OUT_PATH,
    DOCTORS_OUT_PATH,
    APPOINTMENTS_OUT_PATH,
    BILLING_OUT_PATH,
    QUALITY_REPORT_PATH,
    ETL_STRICT,
    INDUSTRY,
    logger,
)
from src.validator   import DataValidator, ValidationReport
from src.transformer import DataTransformer


# ===========================================================================
# UNDERSTAND: Class ETLPipeline — orchestrator, not worker
# ---------------------------------------------------------------------------
# This class does NOT implement cleaning rules itself. It:
#   • Holds state (raw_df, clean_df, validation reports, paths)
#   • Calls DataValidator and DataTransformer in the correct order
#   • Writes CSV files to disk in load()
#
# Pattern name: "Orchestrator" or "Facade" — one simple API (run()) hiding
# multiple subsystems. DataExtractor uses the same pattern for extract/save.
# ===========================================================================
class ETLPipeline:
    """
    Orchestrates the full Module 05 ETL: extract → validate → transform
    → validate → load.

    Attributes
    ──────────
    raw_path       pathlib.Path   where to read raw-data.csv from
    clean_path     pathlib.Path   where to write clean-data.csv
    strict         bool           if True, abort on any validation error
    raw_df         DataFrame      populated by extract()
    clean_df       DataFrame      populated by transform()
    raw_report     ValidationReport  populated by validate_raw()
    clean_report   ValidationReport  populated by validate_clean()
    """

    def __init__(
        self,
        raw_path:   pathlib.Path = RAW_DATA_PATH,
        clean_path: pathlib.Path = CLEAN_DATA_PATH,
        strict:     bool = ETL_STRICT,
    ):
        # -------------------------------------------------------------------
        # Store paths: defaults come from config.py, but tests can override
        # by passing raw_path=tmp_path/"raw-data.csv" when constructing
        # ETLPipeline(...) so real data/ files are never touched in pytest.
        # -------------------------------------------------------------------
        self.raw_path   = raw_path
        self.clean_path = clean_path
        self.strict     = strict

        # validator is stateless — safe to create once per pipeline run
        self.validator   = DataValidator()
        # transformer is created later in transform(); type Optional until then
        self.transformer: Optional[DataTransformer] = None

        # DataFrames start as None — each stage fills them; calling stages
        # out of order raises RuntimeError with a clear message.
        self.raw_df:    Optional[pd.DataFrame] = None
        self.clean_df:  Optional[pd.DataFrame] = None
        self.raw_report:   Optional[ValidationReport] = None
        self.clean_report: Optional[ValidationReport] = None

        logger.info(
            f"ETLPipeline ready — industry: {INDUSTRY} | strict: {self.strict}"
        )

    # ------------------------------------------------------------------ #
    #  1. EXTRACT                                                          #
    # ------------------------------------------------------------------ #
    def extract(self) -> "ETLPipeline":
        """Load raw-data.csv (the Module 03 deliverable) into a DataFrame."""
        # -------------------------------------------------------------------
        # ETL "Extract" here means read from CSV, NOT from Postgres.
        # Module 03 already did the database pull; Module 05 trusts the file
        # on disk as its source of truth (decoupling: you can re-run ETL without
        # hitting the database again).
        # -------------------------------------------------------------------
        logger.info(f"[ETL/EXTRACT] Reading {self.raw_path.name}")
        if not self.raw_path.exists():
            raise FileNotFoundError(
                f"Raw data not found at {self.raw_path}. "
                f"Run `python run.py` (Module 03 stage) first."
            )
        # pd.read_csv: every column becomes a Series; all rows loaded into RAM.
        # For 300 rows this is instant; for 300 million you'd use chunks or Spark.
        self.raw_df = pd.read_csv(self.raw_path)
        logger.info(
            f"[ETL/EXTRACT] Loaded {len(self.raw_df):,} rows × "
            f"{self.raw_df.shape[1]} columns."
        )
        return self  # return self enables .extract().validate_raw().transform()...

    # ------------------------------------------------------------------ #
    #  2. VALIDATE RAW                                                     #
    # ------------------------------------------------------------------ #
    # =========================================================================
    # UNDERSTAND: validate_raw — triage before cleaning (schema + key IDs)
    # =========================================================================
    def validate_raw(self) -> "ETLPipeline":
        if self.raw_df is None:
            raise RuntimeError("Call extract() before validate_raw().")
        # validate_raw checks: not empty, 30 expected columns, no null keys
        self.raw_report = self.validator.validate_raw(self.raw_df)
        # _guard may raise if strict=True and errors exist
        self._guard(self.raw_report)
        return self

    # ------------------------------------------------------------------ #
    #  3. TRANSFORM                                                        #
    # ------------------------------------------------------------------ #
    # =========================================================================
    # UNDERSTAND: transform — delegate to DataTransformer.clean() on raw_df
    # =========================================================================
    def transform(self) -> "ETLPipeline":
        if self.raw_df is None:
            raise RuntimeError("Call extract() before transform().")
        # DataTransformer(raw_df) copies the table; .clean() runs 11 steps in order
        # and mutates self.df inside the transformer object.
        self.transformer = DataTransformer(self.raw_df).clean()
        # Point pipeline's clean_df at the same table the transformer finished
        self.clean_df    = self.transformer.df
        return self

    # ------------------------------------------------------------------ #
    #  4. VALIDATE CLEAN                                                   #
    # ------------------------------------------------------------------ #
    # =========================================================================
    # UNDERSTAND: validate_clean — discharge check (money rules, age, keys)
    # =========================================================================
    def validate_clean(self) -> "ETLPipeline":
        if self.clean_df is None:
            raise RuntimeError("Call transform() before validate_clean().")
        # Stricter rules now: no negative money, no overpayments, plausible age
        self.clean_report = self.validator.validate_clean(self.clean_df)
        self._guard(self.clean_report)
        return self

    # ------------------------------------------------------------------ #
    #  5. LOAD                                                             #
    # ------------------------------------------------------------------ #
    def load(self) -> "ETLPipeline":
        """Write the flat clean file, the 4 dim/fact tables, and a report."""
        if self.clean_df is None or self.transformer is None:
            raise RuntimeError("Call transform() before load().")

        # --- Output 1: full wide clean table (one row per bill/visit) ---
        # index=False: do not write pandas row numbers as an extra CSV column
        self.clean_df.to_csv(self.clean_path, index=False, encoding="utf-8")
        logger.info(
            f"[ETL/LOAD] Wrote {len(self.clean_df):,} rows → "
            f"{self.clean_path.name} "
            f"({self.clean_path.stat().st_size/1024:.1f} KB)"
        )

        # --- Outputs 2–5: star-schema style split for BI tools ---
        # split_into_dimensions() returns a dict: name → DataFrame
        # patients/doctors are deduplicated; appointments/billing keep all rows
        dims = self.transformer.split_into_dimensions()
        out_paths = {
            "patients":     PATIENTS_OUT_PATH,
            "doctors":      DOCTORS_OUT_PATH,
            "appointments": APPOINTMENTS_OUT_PATH,
            "billing":      BILLING_OUT_PATH,
        }
        for name, df in dims.items():
            out = out_paths[name]
            df.to_csv(out, index=False, encoding="utf-8")
            logger.info(f"[ETL/LOAD] Wrote {len(df):,} rows → {out.name}")

        self._write_quality_report()
        return self

    # ------------------------------------------------------------------ #
    #  CONVENIENCE — run the full pipeline                                 #
    # ------------------------------------------------------------------ #
    # =========================================================================
    # UNDERSTAND: run() — one call runs extract→validate_raw→transform→
    # validate_clean→load in order. Each step returns self for chaining.
    # =========================================================================
    def run(self) -> "ETLPipeline":
        # Parentheses allow implicit line continuation — same as chaining on one line
        return (self.extract()
                    .validate_raw()
                    .transform()
                    .validate_clean()
                    .load())

    def report(self) -> None:
        """Print a terminal summary of the ETL run."""
        if self.clean_df is None:
            print("No clean data — run() the pipeline first.")
            return

        print()
        print("=" * 60)
        print(f"  MODULE 05 — ETL COMPLETE | {INDUSTRY.upper()}")
        print("=" * 60)
        print(f"  Raw rows in:    {len(self.raw_df):,}")
        print(f"  Clean rows out: {len(self.clean_df):,}")
        print(f"  Columns:        {self.clean_df.shape[1]}")
        print(f"  Output folder:  data/processed/")

        print()
        print("  Files written:")
        # glob("*") lists every file in processed/ — .gitkeep, CSVs, txt report
        for p in sorted(self.clean_path.parent.glob("*")):
            print(f"    • {p.name}  ({p.stat().st_size/1024:.1f} KB)")

        if self.clean_report is not None:
            print()
            print(f"  Validation: {self.clean_report.summary()}")
        print("=" * 60)

    # ------------------------------------------------------------------ #
    #  INTERNAL HELPERS                                                    #
    # ------------------------------------------------------------------ #
    def _guard(self, report: ValidationReport) -> None:
        """Abort the pipeline if strict mode is on and validation failed."""
        # report.is_valid is True only when errors list is empty
        # Warnings alone do not fail the pipeline
        if not report.is_valid and self.strict:
            raise ValueError(
                f"Strict mode: {report.stage} validation failed with "
                f"{len(report.errors)} error(s). First: {report.errors[0]}"
            )

    def _write_quality_report(self) -> None:
        # Build a text file auditors can read without opening Python
        lines = [
            "=" * 60,
            "  P01 HEALTHCARE — MODULE 05 ETL QUALITY REPORT",
            "=" * 60,
            "",
            f"Raw input:    {self.raw_path.name}  ({len(self.raw_df):,} rows)",
            f"Clean output: {self.clean_path.name} ({len(self.clean_df):,} rows)",
            "",
            "── RAW VALIDATION ──",
            self.raw_report.summary() if self.raw_report else "(skipped)",
        ]
        if self.raw_report:
            for e in self.raw_report.errors:   lines.append(f"  ERROR:   {e}")
            for w in self.raw_report.warnings: lines.append(f"  WARNING: {w}")

        lines += [
            "",
            "── CLEAN VALIDATION ──",
            self.clean_report.summary() if self.clean_report else "(skipped)",
        ]
        if self.clean_report:
            for e in self.clean_report.errors:   lines.append(f"  ERROR:   {e}")
            for w in self.clean_report.warnings: lines.append(f"  WARNING: {w}")

        lines += [
            "",
            "── CLEAN OUTPUT SCHEMA ──",
            f"Columns ({self.clean_df.shape[1]}): {list(self.clean_df.columns)}",
            "",
            "── NULL COUNTS IN CLEAN DATA ──",
        ]
        nulls = self.clean_df.isna().sum()
        any_nulls = (nulls > 0).any()
        if any_nulls:
            for col, n in nulls[nulls > 0].items():
                lines.append(f"  {col}: {n}")
        else:
            lines.append("  (none — clean!)")

        # Path.write_text is pathlib's way to save a string to a file
        QUALITY_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[ETL/LOAD] Wrote {QUALITY_REPORT_PATH.name}")

    def __str__(self) -> str:
        return (
            f"ETLPipeline("
            f"raw={self.raw_path.name}, "
            f"clean={self.clean_path.name}, "
            f"strict={self.strict})"
        )

    def __repr__(self) -> str:
        return f"ETLPipeline(strict={self.strict})"
