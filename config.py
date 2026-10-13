"""
Central config for the FMCG ML project.

Set USE_BIGQUERY = True once you have `gcloud auth application-default login`
(or a service account key) configured and the consumption_fmcg views built
via the Dataform project. Until then, USE_BIGQUERY = False makes every module
recompute the equivalent tables locally from data/raw/*.csv — so you can
develop and demo this project without any GCP credentials.
"""
import os

# ---- BigQuery ----
USE_BIGQUERY = False
BQ_PROJECT = "project-1-474502"
BQ_CONSUMPTION_DATASET = "consumption_fmcg"
BQ_MART_DATASET = "mart_fmcg"

# ---- Local fallback ----
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---- Analysis constants (mirrors includes/constants.js in the Dataform project) ----
SNAPSHOT_DATE = "2025-09-30"
SERVICE_LEVEL_Z = 1.65  # 95% service level
ABC_CUTOFFS = {"A": 0.75, "B": 0.93}
DEMAND_ROLLING_WINDOW_DAYS = 90
