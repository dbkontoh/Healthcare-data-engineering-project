"""src package — P01 Healthcare project (Modules 03 + 05).

Submodules are imported directly (e.g. `from src.etl_pipeline import ETLPipeline`)
rather than re-exported here. That keeps the ETL importable even when the
PostgreSQL driver used by Module 03 isn't installed.
"""

# ===========================================================================
# UNDERSTAND: src/__init__.py — makes src/ a Python package
# ---------------------------------------------------------------------------
# Import style used in this project:
#   from src.etl_pipeline import ETLPipeline
#   from src.data_extractor import DataExtractor
#
# We do NOT re-export all classes here on purpose. If we did `from .query_runner
# import SQLQueryRunner` at package import time, Python would load query_runner,
# which imports config, which tries to create_engine — requiring pg8000 even
# when you only wanted to test the ETL with an existing CSV.
# ===========================================================================
