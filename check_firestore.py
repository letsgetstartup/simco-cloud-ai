import os
from google.cloud import firestore

PROJECT_ID = "solidcam-f58bc"

def check_dates():
    db = firestore.Client(project=PROJECT_ID)
    docs = db.collection("events").order_by("start_ts").limit(1).stream()
    for doc in docs:
        print(f"Oldest event: {doc.to_dict().get('start_ts')}")
    
    docs = db.collection("events").order_by("start_ts", direction=firestore.Query.DESCENDING).limit(1).stream()
    for doc in docs:
        print(f"Newest event: {doc.to_dict().get('start_ts')}")

if __name__ == "__main__":
    check_dates()
