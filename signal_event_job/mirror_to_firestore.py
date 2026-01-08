import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import bigquery
import os

# Configuration
PROJECT_ID = "solidcam-f58bc"
DATASET_ID = "simco_ai"
TABLE_ID = "events_fact"
TENANT_ID = "test_tenant"

def mirror_events():
    # 1. Init BQ
    bq_client = bigquery.Client(project=PROJECT_ID)
    
    # 2. Init Firestore (Emulator or Prod)
    if os.environ.get("FIRESTORE_EMULATOR_HOST"):
        # Local Emulator
        print(f"Connecting to Firestore Emulator: {os.environ['FIRESTORE_EMULATOR_HOST']}")
        firebase_admin.initialize_app(options={'projectId': PROJECT_ID})
    else:
        # Production
        firebase_admin.initialize_app()
        
    db = firestore.client()
    
    # 3. Pull from BQ
    query = f"""
    SELECT * FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
    WHERE tenant_id = '{TENANT_ID}'
    LIMIT 100
    """
    results = bq_client.query(query).result()
    
    count = 0
    for row in results:
        data = dict(row)
        # Convert timestamps to strings for firestore compatibility or use native if possible
        # Firestore handles datetime objects
        
        # We use event_id as the document ID to prevent dupes
        event_id = data.get("event_id", f"evt_{count}")
        db.collection("events").document(event_id).set(data)
        count += 1
        
    print(f"✅ Mirrored {count} events to Firestore.")

if __name__ == "__main__":
    mirror_events()
