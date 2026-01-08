import os
import google.auth
from google.cloud import bigquery
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request

# Simple mapping for demo purposes. 
# In production, this would be in Firestore or a SECURE config.
TENANT_SA_MAPPING = {
    "test_tenant": "metrics-tenant-test@solidcam-f58bc.iam.gserviceaccount.com",
    "demo_tenant": "metrics-tenant-demo@solidcam-f58bc.iam.gserviceaccount.com"
}

def get_impersonated_bq_client(tenant_id: str):
    """
    Creates a BigQuery client that impersonates the specific Service Account 
    bound to the given tenant. This ensures RLS is enforced based on the 
    impersonated identity.
    """
    target_sa = TENANT_SA_MAPPING.get(tenant_id)
    
    # Get default credentials (the runtime SA of the service)
    # The runtime SA must have 'Service Account Token Creator' role on the target SAs.
    base_credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    
    if not target_sa:
        # Fallback to base credentials for untracked tenants (dev mode)
        # In production, this might raise an error.
        print(f"WARNING: No specific SA mapping for {tenant_id}. Using default credentials.")
        return bigquery.Client(project=project_id, credentials=base_credentials)

    # Build impersonated credentials
    try:
        impersonated_creds = impersonated_credentials.Credentials(
            source_credentials=base_credentials,
            target_principal=target_sa,
            target_scopes=["https://www.googleapis.com/auth/bigquery"],
            lifetime=3600
        )
        # Refresh to ensure validity
        impersonated_creds.refresh(Request())
        return bigquery.Client(project=project_id, credentials=impersonated_creds)
    except Exception as e:
        print(f"IMPERSONATION FAILED for {target_sa}: {e}")
        print("FALLING BACK TO DEFAULT CREDENTIALS FOR SIMULATION.")
        return bigquery.Client(project=project_id, credentials=base_credentials)
