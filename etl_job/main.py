import os
import datetime
from google.cloud import firestore
from google.cloud import bigquery
from google.api_core.datetime_helpers import DatetimeWithNanoseconds

# Configuration
SOURCE_PROJECT_ID = os.environ.get("SOURCE_PROJECT_ID", os.environ.get("GCP_PROJECT"))
DEST_PROJECT_ID = os.environ.get("DEST_PROJECT_ID", os.environ.get("GCP_PROJECT"))
DATASET_ID = "simco_ai"
TABLE_ID = "events_fact"
WATERMARK_DOC_REF = "admin/etl_state"

def run_etl():
    print(f"Starting ETL: {SOURCE_PROJECT_ID} (Firestore) -> {DEST_PROJECT_ID} (BigQuery)...")
    
    # Initialize clients
    db = firestore.Client(project=SOURCE_PROJECT_ID)
    bq = bigquery.Client(project=DEST_PROJECT_ID)
    
    # 1. Get Watermark
    watermark_ref = db.document(WATERMARK_DOC_REF)
    watermark_snapshot = watermark_ref.get()
    
    last_ingested_at = None
    if watermark_snapshot.exists:
        last_ingested_at = watermark_snapshot.get("last_event_timestamp")
        
    if not last_ingested_at:
        print("No watermark found. Defaulting to 24 hours ago for initial load.")
        last_ingested_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    else:
        print(f"Resuming from watermark: {last_ingested_at}")

    # 2. Fetch new events
    # Only "STOP" or "DOWNTIME" usually matter for metrics, but we load everything available.
    # Assuming 'events' collection exists.
    # We query for events updated or created after last_ingested_at
    # Note: Firestore queries on timestamps require an index. If missing, this will fail with a URL to create it.
    
    docs = db.collection("events")\
             .where(filter=firestore.FieldFilter("start_ts", ">", last_ingested_at))\
             .order_by("start_ts")\
             .limit(1000)\
             .stream()
    
    rows_to_insert = []
    max_ts = last_ingested_at
    
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
            
        # Basic transformation
        row = {
            "event_id": event_id,
            "tenant_id": data.get("tenant_id", "unknown_tenant"),
            "site_id": data.get("site_id", "unknown_site"),
            "machine_id": data.get("machine_id"),
            "event_type": data.get("event_type", "UNKNOWN"),
            "reason_code": data.get("reason_code"),
            "reason_text": data.get("reason_text"),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "duration_seconds": data.get("duration_seconds"),
            "ingested_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        # Calculate duration if missing
        if row["duration_seconds"] is None and row["start_ts"] and row["end_ts"]:
             try:
                 s = datetime.datetime.fromisoformat(str(row["start_ts"]))
                 e = datetime.datetime.fromisoformat(str(row["end_ts"]))
                 row["duration_seconds"] = int((e - s).total_seconds())
             except:
                 pass

        rows_to_insert.append(row)
        
        # Track max timestamp for watermark update
        # We need the original object for comparison if possible, or parse back
        # For simplicity, using the firestore object if available
        current_ts_obj = data.get("start_ts")
        if current_ts_obj and (not max_ts or current_ts_obj > max_ts):
            max_ts = current_ts_obj

        count += 1

    print(f"Found {count} new events.")

    # 3. Load to BigQuery
    if rows_to_insert:
        table_ref = f"{DEST_PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        errors = bq.insert_rows_json(table_ref, rows_to_insert)
        
        if errors:
            print(f"Encountered errors while inserting rows: {errors}")
            # In production, handle DLQ
        else:
            print(f"Successfully loaded {len(rows_to_insert)} rows to {table_ref}.")
            
            # 4. Update Watermark
            watermark_ref.set({"last_event_timestamp": max_ts}, merge=True)
            print(f"Watermark updated to {max_ts}.")
    else:
        print("No new data to load.")

if __name__ == "__main__":
    run_etl()
