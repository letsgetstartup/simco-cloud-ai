import datetime
from google.cloud import firestore
import os

PROJECT_ID = os.environ.get("GCP_PROJECT", "solidcam-f58bc")

def insert_test_event():
    db = firestore.Client(project=PROJECT_ID)
    
    now = datetime.datetime.now(datetime.timezone.utc)
    start_ts = now - datetime.timedelta(minutes=30)
    end_ts = now - datetime.timedelta(minutes=15)
    
    event_data = {
        "tenant_id": "test_tenant",
        "site_id": "test_site",
        "machine_id": "M001",
        "event_type": "STOP",
        "reason_code": "TEST_REASON",
        "reason_text": "Manual Test Stop",
        "start_ts": start_ts,
        "end_ts": end_ts,
        "duration_seconds": 900,
        "created_at": now
    }
    
    # Add to 'events' collection
    db.collection("events").add(event_data)
    print(f"Inserted test event: {event_data}")

if __name__ == "__main__":
    insert_test_event()
