"""
One-shot loader: push the processed CSVs to BigQuery so Looker Studio
(and the existing views) have data to render.

What it does:
  1. Drops the 2 existing VIEWS (district_risk_scores, state_summary)
     so we can replace them with TABLES loaded from the processed CSVs.
  2. Loads backend/data/processed/district_risk_scores.csv -> table
  3. Loads backend/data/processed/state_summary.csv          -> table
  4. Prints row counts + a sample so you can confirm in the console.

Re-runnable: each load uses WRITE_TRUNCATE so it overwrites.
"""
import os
from pathlib import Path
from google.cloud import bigquery

PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "promptwars-mumbai-499305")
DATASET    = os.environ.get("BQ_DATASET", "breathesafe")
BASE       = Path(__file__).parent
PROC       = BASE / "backend" / "data" / "processed"

DISTRICTS_CSV = PROC / "district_risk_scores.csv"
STATES_CSV    = PROC / "state_summary.csv"

VIEW_NAMES = {"district_risk_scores", "state_summary"}

client = bigquery.Client(project=PROJECT_ID)

# 1) Drop the existing views (they reference empty source tables, so they're empty)
for view in VIEW_NAMES:
    ref = f"{PROJECT_ID}.{DATASET}.{view}"
    try:
        client.delete_table(ref)
        print(f"  dropped view  {ref}")
    except Exception as e:
        print(f"  skip drop     {ref} ({type(e).__name__}: {e})")

# 2) + 3) Load CSVs as tables with autodetected schema
def load_csv(csv_path: Path, table_name: str):
    table_ref = f"{PROJECT_ID}.{DATASET}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        autodetect=True,
        skip_leading_rows=1,  # header
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with open(csv_path, "rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)
    job.result()  # wait
    table = client.get_table(table_ref)
    print(f"  loaded {csv_path.name:35s} -> {table_ref}  ({table.num_rows} rows)")

print("\nLoading processed CSVs to BigQuery...")
load_csv(DISTRICTS_CSV, "district_risk_scores")
load_csv(STATES_CSV,    "state_summary")

# 4) Verify
print("\nVerifying row counts:")
for t in ("district_risk_scores", "state_summary"):
    table = client.get_table(f"{PROJECT_ID}.{DATASET}.{t}")
    print(f"  {t}: {table.num_rows} rows")

print("\nSample (top 3 by awareness_gap from state_summary):")
q = f"""
SELECT state_name, district_count, high_risk_districts,
       awareness_desert_count, avg_risk_score, avg_awareness_gap
FROM `{PROJECT_ID}.{DATASET}.state_summary`
ORDER BY avg_awareness_gap DESC
LIMIT 3
"""
for row in client.query(q).result():
    print(" ", dict(row))

print("\nDone. Reconnect Looker Studio to:")
print(f"   BigQuery project : {PROJECT_ID}")
print(f"   Dataset          : {DATASET}")
print(f"   View/Table       : state_summary  (31 rows)  ← best for Looker")
print(f"   View/Table       : district_risk_scores  (365 rows)")
