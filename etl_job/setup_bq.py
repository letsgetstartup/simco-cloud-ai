import os
from google.cloud import bigquery
from google.api_core.exceptions import Conflict

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT"))
DATASET_ID = "simco_ai"
TABLE_ID = "events_fact"
LOCATION = "us-central1"

def setup_bq():
    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)
    
    # 1. Create Dataset
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = LOCATION
    try:
        client.create_dataset(dataset, timeout=30)
        print(f"Created dataset {dataset_ref}")
    except Conflict:
        print(f"Dataset {dataset_ref} already exists")

    # 2. Create Table with Schema
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    schema = [
        bigquery.SchemaField("event_id", "STRING", mode="REQUIRED", description="Unique ID of the event"),
        bigquery.SchemaField("tenant_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("site_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("machine_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("event_type", "STRING", mode="REQUIRED", description="e.g., STOP, DOWNTIME, ALARM"),
        bigquery.SchemaField("reason_code", "STRING", mode="NULLABLE", description="Normalized reason code"),
        bigquery.SchemaField("reason_text", "STRING", mode="NULLABLE", description="Raw reason text"),
        bigquery.SchemaField("start_ts", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("end_ts", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("duration_seconds", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="NULLABLE", default_value_expression="CURRENT_TIMESTAMP()"),
    ]
    
    table = bigquery.Table(table_ref, schema=schema)
    
    # Partitioning
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="start_ts"
    )
    
    # Clustering
    table.clustering_fields = ["tenant_id", "site_id", "machine_id", "event_type"]
    
    try:
        client.create_table(table)
        print(f"Created table {table_ref}")
    except Conflict:
        print(f"Table {table_ref} already exists")

if __name__ == "__main__":
    if not PROJECT_ID:
        print("Error: GCP_PROJECT or GOOGLE_CLOUD_PROJECT env var must be set.")
    else:
        setup_bq()
