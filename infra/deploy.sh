#!/bin/bash
set -e

# 0. Detect Project ID
PROJECT_ID=$(grep -o '"default": "[^"]*"' .firebaserc | cut -d'"' -f4)
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project)
fi

REGION="us-central1"
REPO="simco-repo"
SA_NAME="cloud-run-sa"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

echo "Deploying to Project: $PROJECT_ID (Detected from .firebaserc or config)"

# 1. Enable Services
echo "Enabling required APIs..."
gcloud services enable run.googleapis.com \
                       artifactregistry.googleapis.com \
                       cloudbuild.googleapis.com \
                       bigquery.googleapis.com \
                       firestore.googleapis.com \
                       iam.googleapis.com --project "$PROJECT_ID"

# 2. Setup BigQuery
echo "Setting up BigQuery dataset and table..."
export GCP_PROJECT=$PROJECT_ID
./venv_etl/bin/python3 etl_job/setup_bq.py

# 3. Create Service Account & Grant Permissions
if ! gcloud iam service-accounts describe $SA_EMAIL --project "$PROJECT_ID" &>/dev/null; then
    echo "Creating service account $SA_NAME..."
    gcloud iam service-accounts create $SA_NAME --display-name="Cloud Run Core Service Account" --project "$PROJECT_ID"
fi

echo "Granting permissions to $SA_EMAIL..."
for ROLE in "roles/bigquery.dataEditor" "roles/bigquery.jobUser" "roles/datastore.user" "roles/logging.logWriter"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" --condition=None &>/dev/null
done

# 4. Create Artifact Registry
if ! gcloud artifacts repositories describe $REPO --location=$REGION --project "$PROJECT_ID" &>/dev/null; then
    echo "Creating Artifact Registry $REPO..."
    gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --project "$PROJECT_ID"
fi

# 5. Deploy ETL Job
echo "Building and Deploying ETL Job..."
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/etl-job etl_job/ --project "$PROJECT_ID"
gcloud run jobs deploy etl-job \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/etl-job \
  --region $REGION \
  --task-timeout 300s \
  --service-account "$SA_EMAIL" \
  --set-env-vars GCP_PROJECT=$PROJECT_ID --project "$PROJECT_ID"

# 6. Deploy Metrics Service
echo "Building and Deploying Metrics Service..."
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/metrics-service metrics_service/ --project "$PROJECT_ID"
gcloud run deploy metrics-service \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/metrics-service \
  --region $REGION \
  --platform managed \
  --no-allow-unauthenticated \
  --service-account "$SA_EMAIL" \
  --set-env-vars GCP_PROJECT=$PROJECT_ID --project "$PROJECT_ID"

# 7. Grant Invoke Permission
echo "Granting Cloud Run Invoker permission to $SA_EMAIL..."
gcloud run services add-iam-policy-binding metrics-service \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.invoker" \
  --region=$REGION \
  --project="$PROJECT_ID"

echo "------------------------------------------------"
echo "Deployment Complete!"
echo "------------------------------------------------"
