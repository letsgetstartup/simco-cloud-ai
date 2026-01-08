import os
import datetime
from google.cloud import bigquery

PROJECT_ID = os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT"))
DATASET_ID = "simco_ai"
SOURCE_TABLE = "events_fact"
ROLLUP_TABLE = "events_daily_rollup"

def run_rollup():
    print(f"Starting Rollup Job: {SOURCE_TABLE} -> {ROLLUP_TABLE}...")
    client = bigquery.Client(project=PROJECT_ID)
    
    # We aggregate uptime and downtime by day, tenant, and site
    rollup_query = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET_ID}.{ROLLUP_TABLE}`
    AS
    SELECT
      DATE(start_ts) as event_date,
      tenant_id,
      site_id,
      machine_id,
      event_type,
      reason_code,
      COUNT(*) as event_count,
      SUM(duration_seconds) as total_duration_seconds
    FROM `{PROJECT_ID}.{DATASET_ID}.{SOURCE_TABLE}`
    GROUP BY 1, 2, 3, 4, 5, 6
    """
    
    try:
        client.query(rollup_query).result()
        print(f"Rollup complete: {ROLLUP_TABLE} updated.")
    except Exception as e:
        print(f"Rollup failed: {e}")

if __name__ == "__main__":
    run_rollup()
