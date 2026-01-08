#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
DATASET_ID="simco_ai"
TABLE_ID="events_fact"
LOCATION="us-central1"

echo "Using Project DB: $PROJECT_ID"

# 1. Create Dataset
if ! bq ls --project_id=$PROJECT_ID --dataset_id=$DATASET_ID &>/dev/null; then
    echo "Creating dataset $DATASET_ID..."
    bq --location=$LOCATION mk --dataset $PROJECT_ID:$DATASET_ID
else
    echo "Dataset $DATASET_ID already exists."
fi

# 2. Create Table
if ! bq ls --project_id=$PROJECT_ID $DATASET_ID | grep -w $TABLE_ID &>/dev/null; then
    echo "Creating table $TABLE_ID..."
    bq mk --table \
       --location=$LOCATION \
       --clustering_fields=tenant_id,site_id,machine_id,event_type \
       --time_partitioning_field=start_ts \
       --time_partitioning_type=DAY \
       $PROJECT_ID:$DATASET_ID.$TABLE_ID \
       infra/bq_schema.json
else
    echo "Table $TABLE_ID already exists (skipping creation)."
    # Optional: Update schema if needed
    # bq update $PROJECT_ID:$DATASET_ID.$TABLE_ID infra/bq_schema.json
fi

echo "BigQuery setup complete."
