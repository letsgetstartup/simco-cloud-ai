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
    
    last_ingested_at = None
    if watermark_snapshot.exists:
        last_ingested_at = watermark_snapshot.get("last_event_timestamp")
        
    if not last_ingested_at:
        print("No watermark found. Defaulting to 48 hours ago for initial load.")
        search_start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    else:
        # LOOKBACK WINDOW: Go back 24 hours from the last watermark to catch updates/late arrivals
        print(f"Watermark found: {last_ingested_at}")
        
        if isinstance(last_ingested_at, str):
             last_ingested_at = datetime.datetime.fromisoformat(last_ingested_at)
        elif isinstance(last_ingested_at, DatetimeWithNanoseconds):
             last_ingested_at = datetime.datetime.fromtimestamp(last_ingested_at.timestamp(), tz=datetime.timezone.utc)

        search_start_time = last_ingested_at - datetime.timedelta(hours=24)
        print(f"Applying 24h lookback. Search Start Time: {search_start_time}")

    # 2. Fetch events
    docs = db.collection("events")\
             .where(filter=firestore.FieldFilter("start_ts", ">", search_start_time))\
             .order_by("start_ts")\
             .stream()
    
    rows = []
    max_ts = None
    
    count = 0
    for doc in docs:
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
        
        # Transformation: Calculate duration if missing (Best effort)
        if row["duration_seconds"] is None and row["start_ts"] and row["end_ts"]:
             try:
                 row["duration_seconds"] = int((row["end_ts"] - row["start_ts"]).total_seconds())
             except:
                 pass
        
        # Explicitly cast to float/int to match BQ schema types if needed, handled by pandas-gbq roughly
        # Ensure duration_seconds is numeric nullable
        if row["duration_seconds"] is not None:
             row["duration_seconds"] = float(row["duration_seconds"])

        rows.append(row)
        
        # Update Max TS for watermark (using the actual event timestamp)
        current_ts_obj = data.get("start_ts")
        if current_ts_obj:
             # Normalize for comparison
             if isinstance(current_ts_obj, DatetimeWithNanoseconds):
                  current_ts_obj = datetime.datetime.fromtimestamp(current_ts_obj.timestamp(), tz=datetime.timezone.utc)
             elif isinstance(current_ts_obj, str):
                  current_ts_obj = datetime.datetime.fromisoformat(current_ts_obj)
             
             if not max_ts or current_ts_obj > max_ts:
                 max_ts = current_ts_obj

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
    query_job.result()
    print("MERGE complete.")
    
    # 5. Update Watermark
    if max_ts:
        watermark_ref.set({"last_event_timestamp": max_ts}, merge=True)
        print(f"Watermark updated to {max_ts}.")

if __name__ == "__main__":
    run_etl()
