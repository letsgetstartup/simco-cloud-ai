import os
import datetime
import pandas as pd
from google.cloud import firestore
from google.cloud import bigquery
from google.api_core.datetime_helpers import DatetimeWithNanoseconds

# Configuration
SOURCE_PROJECT_ID = os.environ.get("SOURCE_PROJECT_ID", os.environ.get("GCP_PROJECT"))
DEST_PROJECT_ID = os.environ.get("DEST_PROJECT_ID", os.environ.get("GCP_PROJECT"))
DATASET_ID = "simco_ai"
TABLE_ID = "events_fact"
STAGING_TABLE_ID = "events_fact_staging"
WATERMARK_DOC_REF = "admin/etl_state"

def run_etl():
    print(f"Starting ETL (Idempotent MERGE): {SOURCE_PROJECT_ID} (Firestore) -> {DEST_PROJECT_ID} (BigQuery)...")
    
    # Initialize clients
    db = firestore.Client(project=SOURCE_PROJECT_ID)
    bq = bigquery.Client(project=DEST_PROJECT_ID)
    
    # 1. Get Watermark and Apply Lookback
    watermark_ref = db.document(WATERMARK_DOC_REF)
    watermark_snapshot = watermark_ref.get()
    
    last_updated_at = None
    if watermark_snapshot.exists:
        last_updated_at = watermark_snapshot.get("last_updated_at_watermark")
        
    if not last_updated_at:
        print("No watermark found. Defaulting to 48 hours ago for initial load.")
        search_start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    else:
        print(f"Watermark found: {last_updated_at}")
        if isinstance(last_updated_at, str):
             last_updated_at = datetime.datetime.fromisoformat(last_updated_at)
        elif isinstance(last_updated_at, DatetimeWithNanoseconds):
             last_updated_at = datetime.datetime.fromtimestamp(last_updated_at.timestamp(), tz=datetime.timezone.utc)

        # Apply a 1-hour overlap safety margin
        search_start_time = last_updated_at - datetime.timedelta(hours=1)
        print(f"Search Start Time (updated_at >): {search_start_time}")

    # 2. Fetch events
    # We poll events from the last 7 days to check for updates
    docs = db.collection("events")\
             .where(filter=firestore.FieldFilter("start_ts", ">", datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)))\
             .stream()
    
    rows = []
    max_updated_at = last_updated_at if last_updated_at else search_start_time
    
    count = 0
    for doc in docs:
        doc_updated_at = doc.update_time
        if doc_updated_at <= search_start_time:
             continue # Skip already processed unmodified docs

        data = doc.to_dict()
        event_id = doc.id
        
        # Parse fields
        start_ts = data.get("start_ts")
        end_ts = data.get("end_ts")
        
        # Handle Firestore DatetimeWithNanoseconds
        if isinstance(start_ts, DatetimeWithNanoseconds):
            start_ts = start_ts.isoformat()
        if isinstance(end_ts, DatetimeWithNanoseconds):
            end_ts = end_ts.isoformat()
            
        row = {
            "event_id": event_id,
            "tenant_id": data.get("tenant_id", "unknown_tenant"),
            "site_id": data.get("site_id", "unknown_site"),
            "machine_id": data.get("machine_id"),
            "event_type": data.get("event_type", "UNKNOWN"),
            "reason_code": data.get("reason_code"),
            "reason_text": data.get("reason_text"),
            "start_ts": pd.Timestamp(start_ts) if start_ts else None,
            "end_ts": pd.Timestamp(end_ts) if end_ts else None,
            "duration_seconds": data.get("duration_seconds"),
            "ingested_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        # DQ Transform: Ensure duration is valid
        if row["duration_seconds"] is None and row["start_ts"] and row["end_ts"]:
             try:
                 row["duration_seconds"] = int((row["end_ts"] - row["start_ts"]).total_seconds())
             except:
                 pass
        
        if row["duration_seconds"] is not None:
             row["duration_seconds"] = float(row["duration_seconds"])

        rows.append(row)
        
        if doc_updated_at > max_updated_at:
             max_updated_at = doc_updated_at

        count += 1

    print(f"Fetched {count} events.")

    if not rows:
        print("No events found to process.")
        return

    # 3. Load to Staging Table
    df = pd.DataFrame(rows)
    
    # Enforce schema types for critical columns to avoid BQ mismatch
    df['event_id'] = df['event_id'].astype(str)
    # timestamps handled by pd.Timestamp
    
    table_ref = f"{DEST_PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    staging_ref = f"{DEST_PROJECT_ID}.{DATASET_ID}.{STAGING_TABLE_ID}"
    
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE", # Always overwrite staging
    )
    
    print(f"Loading {len(df)} rows to staging: {staging_ref}...")
    job = bq.load_table_from_dataframe(df, staging_ref, job_config=job_config)
    job.result()  # Wait for the job to complete.
    print("Staging load complete.")
    
    # 4. Execute MERGE
    print("Executing MERGE into target table...")
    merge_query = f"""
    MERGE `{table_ref}` T
    USING `{staging_ref}` S
    ON T.event_id = S.event_id
    WHEN MATCHED THEN
      UPDATE SET
        tenant_id = S.tenant_id,
        site_id = S.site_id,
        machine_id = S.machine_id,
        event_type = S.event_type,
        reason_code = S.reason_code,
        reason_text = S.reason_text,
        start_ts = S.start_ts,
        end_ts = S.end_ts,
        duration_seconds = S.duration_seconds,
        ingested_at = S.ingested_at
    WHEN NOT MATCHED THEN
      INSERT (event_id, tenant_id, site_id, machine_id, event_type, reason_code, reason_text, start_ts, end_ts, duration_seconds, ingested_at)
      VALUES (S.event_id, S.tenant_id, S.site_id, S.machine_id, S.event_type, S.reason_code, S.reason_text, S.start_ts, S.end_ts, S.duration_seconds, S.ingested_at)
    """
    
    query_job = bq.query(merge_query)
    bq.query(merge_query).result()
    print("MERGE complete.")
    
    # 5. Data Quality Checks (Task 4)
    print("Running Data Quality Checks...")
    dq_query = f"""
    SELECT 
      COUNT(*) as total_batch,
      COUNTIF(machine_id IS NULL) as missing_machine,
      COUNTIF(duration_seconds < 0) as negative_duration,
      COUNTIF(start_ts IS NULL) as missing_start
    FROM `{staging_ref}`
    """
    dq_results = list(bq.query(dq_query).result())[0]
    
    dq_report = {
        "batch_size": dq_results.total_batch,
        "missing_machine_id": dq_results.missing_machine,
        "negative_durations": dq_results.negative_duration,
        "missing_timestamps": dq_results.missing_start,
        "run_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    print(f"DQ Report: {dq_report}")
    
    if dq_results.negative_duration > 0 or dq_results.missing_machine > 0:
        print("WARNING: Data Quality anomalies detected. Review logs.")

    # 6. Update Watermark
    if max_updated_at:
        watermark_ref.set({"last_updated_at_watermark": max_updated_at}, merge=True)
        print(f"Watermark updated to {max_updated_at}.")

if __name__ == "__main__":
    run_etl()
