from google.cloud import bigquery
from google.api_core.exceptions import NotFound
import os
import pandas as pd

PROJECT_ID = os.environ.get("GCP_PROJECT", "simco-cloud-ai") 
# Default to project from user workspace context if env var missing; wait, user workspace said simco-cloud-ai?
# Actually os.environ["GCP_PROJECT"] is usually set in Cloud Run.
DATASET = os.environ.get("BQ_DATASET", "simco_ai")

client = bigquery.Client(project=PROJECT_ID)

# Define schemas at module level
FEATURES_SCHEMA = [
    bigquery.SchemaField("tenant_id", "STRING"),
    bigquery.SchemaField("site_id", "STRING"),
    bigquery.SchemaField("machine_id", "STRING"),
    bigquery.SchemaField("ts", "TIMESTAMP"),
    bigquery.SchemaField("window_sec", "INTEGER"),
    bigquery.SchemaField("acc_rms_x", "FLOAT"),
    bigquery.SchemaField("acc_rms_y", "FLOAT"),
    bigquery.SchemaField("acc_rms_z", "FLOAT"),
    bigquery.SchemaField("acc_peak", "FLOAT"),
    bigquery.SchemaField("source_file", "STRING"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
]

EVENTS_SCHEMA = [
    bigquery.SchemaField("event_id", "STRING"),
    bigquery.SchemaField("tenant_id", "STRING"),
    bigquery.SchemaField("site_id", "STRING"),
    bigquery.SchemaField("machine_id", "STRING"),
    bigquery.SchemaField("event_type", "STRING"),
    bigquery.SchemaField("reason_code", "STRING"),
    bigquery.SchemaField("start_ts", "TIMESTAMP"),
    bigquery.SchemaField("end_ts", "TIMESTAMP"),
    bigquery.SchemaField("duration_seconds", "INTEGER"),
    bigquery.SchemaField("metadata_json", "STRING"),
    bigquery.SchemaField("reason_text", "STRING"),
    bigquery.SchemaField("source_updated_at", "TIMESTAMP"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
]

DQ_SCHEMA = [
    bigquery.SchemaField("tenant_id", "STRING"),
    bigquery.SchemaField("site_id", "STRING"),
    bigquery.SchemaField("run_at", "TIMESTAMP"),
    bigquery.SchemaField("batch_size", "INTEGER"),
    bigquery.SchemaField("missing_machine_count", "INTEGER"),
    bigquery.SchemaField("negative_duration_count", "INTEGER"),
    bigquery.SchemaField("missing_start_ts_count", "INTEGER"),
]

def ensure_tables():
    # Features table
    features_table_id = f"{PROJECT_ID}.{DATASET}.signals_features"
    try:
        client.get_table(features_table_id)
        print(f"Table {features_table_id} exists.")
    except NotFound:
        print(f"Creating table {features_table_id}...")
        table = bigquery.Table(features_table_id, schema=FEATURES_SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="ts"
        )
        table.clustering_fields = ["tenant_id", "site_id", "machine_id"]
        client.create_table(table)

    # Events table
    events_table_id = f"{PROJECT_ID}.{DATASET}.events_fact"
    try:
        client.get_table(events_table_id)
        print(f"Table {events_table_id} exists.")
    except NotFound:
        print(f"Creating table {events_table_id}...")
        table = bigquery.Table(events_table_id, schema=EVENTS_SCHEMA)
        # Partition by start_ts typically
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="start_ts"
        )
        table.clustering_fields = ["tenant_id", "machine_id", "event_type"]
        client.create_table(table)

    # DQ Metrics table
    dq_table_id = f"{PROJECT_ID}.{DATASET}.dq_metrics"
    try:
        client.get_table(dq_table_id)
        print(f"Table {dq_table_id} exists.")
    except NotFound:
        print(f"Creating table {dq_table_id}...")
        table = bigquery.Table(dq_table_id, schema=DQ_SCHEMA)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="run_at"
        )
        client.create_table(table)

def reset_tables():
    features_table_id = f"{PROJECT_ID}.{DATASET}.signals_features"
    events_table_id = f"{PROJECT_ID}.{DATASET}.events_fact"
    
    try:
        client.delete_table(features_table_id, not_found_ok=True)
        print(f"Deleted {features_table_id}")
    except Exception as e:
        print(f"Error deleting {features_table_id}: {e}")

    try:
        client.delete_table(events_table_id, not_found_ok=True)
        print(f"Deleted {events_table_id}")
    except Exception as e:
        print(f"Error deleting {events_table_id}: {e}")
    
    # Recreate them
    ensure_tables()

def write_features(feat_df: pd.DataFrame):
    if feat_df.empty:
        return
        
    table_id = f"{PROJECT_ID}.{DATASET}.signals_features"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=FEATURES_SCHEMA # Use explicit schema
    )
    job = client.load_table_from_dataframe(feat_df, table_id, job_config=job_config)
    job.result()  # Wait for the job to complete.
    print(f"Loaded {len(feat_df)} rows to {table_id}")

def write_events_merge(events_df: pd.DataFrame):
    if events_df.empty:
        return

    table_id = f"{PROJECT_ID}.{DATASET}.events_fact"
    staging_table_id = f"{PROJECT_ID}.{DATASET}.events_fact_staging"
    
    # Drop staging table to ensure fresh schema
    client.delete_table(staging_table_id, not_found_ok=True)
    
    # 1. Load to staging
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=EVENTS_SCHEMA # Use explicit schema to ensure types match
    )
    job = client.load_table_from_dataframe(events_df, staging_table_id, job_config=job_config)
    job.result()
    print(f"Loaded {len(events_df)} rows to {staging_table_id}")
    
    # Build column list from schema
    columns = [field.name for field in EVENTS_SCHEMA]
    columns_str = ", ".join(columns)
    values_str = ", ".join([f"S.{c}" for c in columns])

    # 2. MERGE
    query = f"""
    MERGE `{table_id}` T
    USING `{staging_table_id}` S
    ON T.event_id = S.event_id
    WHEN MATCHED THEN
      UPDATE SET
        T.end_ts = S.end_ts,
        T.duration_seconds = S.duration_seconds,
        T.metadata_json = S.metadata_json,
        T.ingested_at = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN
      INSERT ({columns_str})
      VALUES ({values_str})
    """
    query_job = client.query(query)
    query_job.result()
    print("Merged events into events_fact.")

def log_dq_metrics(tenant_id: str, site_id: str, events_df: pd.DataFrame):
    """Logs data quality metrics for the current run."""
    table_id = f"{PROJECT_ID}.{DATASET}.dq_metrics"
    
    dq_data = {
        "tenant_id": [tenant_id],
        "site_id": [site_id],
        "run_at": [pd.Timestamp.utcnow()],
        "batch_size": [len(events_df)],
        "missing_machine_count": [events_df["machine_id"].isna().sum() if "machine_id" in events_df else 0],
        "negative_duration_count": [0], # Placeholder, Bosch data generally clean
        "missing_start_ts_count": [events_df["start_ts"].isna().sum() if "start_ts" in events_df else 0],
    }
    
    if "duration_seconds" in events_df:
        dq_data["negative_duration_count"] = [(events_df["duration_seconds"] < 0).sum()]
        
    dq_df = pd.DataFrame(dq_data)
    
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=DQ_SCHEMA
    )
    job = client.load_table_from_dataframe(dq_df, table_id, job_config=job_config)
    job.result()
    print(f"Logged DQ metrics for {tenant_id}/{site_id}")
