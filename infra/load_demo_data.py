import os
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import Conflict

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT", "manualai-481406")
DATASET_ID = "simco_ai"
DATA_DIR = "simco_demo_dataset_30d"

def load_csv_to_bq(file_name, table_id):
    client = bigquery.Client(project=PROJECT_ID)
    file_path = os.path.join(DATA_DIR, file_name)
    
    if not os.path.exists(file_path):
        print(f"File {file_path} not found. Skipping.")
        return

    print(f"Loading {file_path} into {PROJECT_ID}.{DATASET_ID}.{table_id}...")
    
    # Read with pandas to help with type inference if needed, or just use BQ auto-detect
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, # Overwrite demo data
    )

    with open(file_path, "rb") as source_file:
        load_job = client.load_table_from_file(source_file, f"{PROJECT_ID}.{DATASET_ID}.{table_id}", job_config=job_config)
        
    load_job.result()  # Wait for the job to complete
    
    table = client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{table_id}")
    print(f"Loaded {table.num_rows} rows into {table_id}.")

def main():
    # 0. Ensure Dataset exists
    client = bigquery.Client(project=PROJECT_ID)
    dataset_ref = client.dataset(DATASET_ID)
    try:
        client.create_dataset(bigquery.Dataset(dataset_ref))
        print(f"Created dataset {DATASET_ID}")
    except Conflict:
        pass

    # 1. Load each CSV
    files_to_load = {
        "events.csv": "events",
        "jobs.csv": "jobs",
        "machines.csv": "machines",
        "parts.csv": "parts",
        "signals.csv": "signals",
        "tools.csv": "tools"
    }
    
    for csv_file, table_id in files_to_load.items():
        try:
            load_csv_to_bq(csv_file, table_id)
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")

if __name__ == "__main__":
    main()
