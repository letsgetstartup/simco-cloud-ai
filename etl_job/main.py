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
DQ_TABLE_ID = "dq_metrics"
WATERMARK_DOC_REF = "admin/etl_state"

# ETL Parameters
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", 24))
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", 0))

def run_etl():
    print(f"Starting ETL: {SOURCE_PROJECT_ID} (Firestore) -> {DEST_PROJECT_ID} (BigQuery)...")
    
    # Initialize clients
    db = firestore.Client(project=SOURCE_PROJECT_ID)
    bq = bigquery.Client(project=DEST_PROJECT_ID)
    
    # 1. Determine Search Window
    watermark_ref = db.document(WATERMARK_DOC_REF)
    watermark_snapshot = watermark_ref.get()
    
    last_updated_at = None
    if watermark_snapshot.exists:
        data = watermark_snapshot.to_dict()
        last_updated_at = data.get("last_updated_at_watermark")
        
    if BACKFILL_DAYS > 0:
        print(f"BACKFILL MODE ENABLED: Reprocessing last {BACKFILL_DAYS} days.")
        search_start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=BACKFILL_DAYS)
    elif not last_updated_at:
        print("No watermark found. Defaulting to 48 hours ago for initial load.")
        search_start_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    else:
        print(f"Watermark found: {last_updated_at}")
        if isinstance(last_updated_at, str):
             last_updated_at = datetime.datetime.fromisoformat(last_updated_at)
        elif isinstance(last_updated_at, DatetimeWithNanoseconds):
             last_updated_at = datetime.datetime.fromtimestamp(last_updated_at.timestamp(), tz=datetime.timezone.utc)

        # Apply configurable lookback window to catch updates/corrections
        search_start_time = last_updated_at - datetime.timedelta(hours=LOOKBACK_HOURS)
        print(f"Applying {LOOKBACK_HOURS}h lookback. Search Start Time: {search_start_time}")

    # 2. Fetch events from Firestore
    # Polling based on start_ts for the window, but we filter by doc.update_time internally
    # to catch only what changed since search_start_time
    docs = db.collection("events")\
             .where(filter=firestore.FieldFilter("start_ts", ">", search_start_time - datetime.timedelta(days=1)))\
             .stream()
    
    rows = []
    max_updated_at = last_updated_at if last_updated_at else search_start_time
    count = 0
    
    for doc in docs:
        doc_updated_at = doc.update_time
        if doc_updated_at < search_start_time and BACKFILL_DAYS == 0:
             continue 

        data = doc.to_dict()
        event_id = doc.id
        
        # Parse fields
        start_ts = data.get("start_ts")
        end_ts = data.get("end_ts")
        
        if isinstance(start_ts, DatetimeWithNanoseconds): start_ts = start_ts.isoformat()
        if isinstance(end_ts, DatetimeWithNanoseconds): end_ts = end_ts.isoformat()
            
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
            "source_updated_at": doc_updated_at,
            "ingested_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        # DQ Transform: Ensure duration is valid
        if row["duration_seconds"] is None and row["start_ts"] and row["end_ts"]:
             try:
                 row["duration_seconds"] = int((row["end_ts"] - row["start_ts"]).total_seconds())
             except: pass
        if row["duration_seconds"] is not None:
             row["duration_seconds"] = int(float(row["duration_seconds"])) # Coerce to int for BQ compatibility

        rows.append(row)
        if doc_updated_at > max_updated_at:
             max_updated_at = doc_updated_at
        count += 1

    print(f"Fetched {count} events.")
    if not rows:
        print("No new or updated events found.")
        return

    # 3. Load to Staging Table
    df = pd.DataFrame(rows)
    df['event_id'] = df['event_id'].astype(str)
    
    table_ref = f"{DEST_PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    staging_ref = f"{DEST_PROJECT_ID}.{DATASET_ID}.{STAGING_TABLE_ID}"
    dq_table_ref = f"{DEST_PROJECT_ID}.{DATASET_ID}.{DQ_TABLE_ID}"
    
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    print(f"Loading to staging: {staging_ref}...")
    bq.load_table_from_dataframe(df, staging_ref, job_config=job_config).result()
    
    # 4. Execute MERGE
    print("Executing MERGE into target table...")
    merge_query = f"""
    MERGE `{table_ref}` T
    USING `{staging_ref}` S
    ON T.event_id = S.event_id
    WHEN MATCHED THEN
      UPDATE SET
        tenant_id = S.tenant_id, site_id = S.site_id, machine_id = S.machine_id,
        event_type = S.event_type, reason_code = S.reason_code, reason_text = S.reason_text,
        start_ts = S.start_ts, end_ts = S.end_ts, duration_seconds = S.duration_seconds,
        ingested_at = S.ingested_at
    WHEN NOT MATCHED THEN
      INSERT (event_id, tenant_id, site_id, machine_id, event_type, reason_code, reason_text, start_ts, end_ts, duration_seconds, ingested_at)
      VALUES (S.event_id, S.tenant_id, S.site_id, S.machine_id, S.event_type, S.reason_code, S.reason_text, S.start_ts, S.end_ts, S.duration_seconds, S.ingested_at)
    """
    bq.query(merge_query).result()
    print("MERGE complete.")
    
    # 5. Data Quality Persistence (Workstream F)
    print("Calculating and persisting Data Quality metrics...")
    # We aggregate DQ by tenant/site for the current batch
    dq_calc_query = f"""
    INSERT INTO `{dq_table_ref}` (run_id, tenant_id, site_id, batch_size, missing_machine_count, negative_duration_count, missing_start_ts_count, run_at)
    SELECT 
      GENERATE_UUID() as run_id,
      tenant_id,
      site_id,
      COUNT(*) as batch_size,
      COUNTIF(machine_id IS NULL) as missing_machine_count,
      COUNTIF(duration_seconds < 0) as negative_duration_count,
      COUNTIF(start_ts IS NULL) as missing_start_ts_count,
      CURRENT_TIMESTAMP() as run_at
    FROM `{staging_ref}`
    GROUP BY tenant_id, site_id
    """
    try:
        bq.query(dq_calc_query).result()
    except Exception as e:
        print(f"Warning: Failed to persist DQ metrics: {e}")
    
    # 6. Update Watermark (Only if not in backfill mode)
    if max_updated_at and BACKFILL_DAYS == 0:
        watermark_ref.set({"last_updated_at_watermark": max_updated_at}, merge=True)
        print(f"Watermark updated to {max_updated_at}.")

if __name__ == "__main__":
    run_etl()

if __name__ == "__main__":
    run_etl()
