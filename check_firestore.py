import firebase_admin
from firebase_admin import credentials, firestore
import os
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
try:
    # Use anonymous credentials for emulator
    cred = credentials.AnonymousCredentials()
    firebase_admin.initialize_app(cred, {'projectId': 'solidcam-f58bc'})
    db = firestore.client()
    cols = ['machines', 'jobs', 'events', 'tools', 'signals']
    for col in cols:
        docs = list(db.collection(col).limit(1).stream())
        print(f"{col}: {len(docs)} documents")
except Exception as e:
    print(f"Error: {e}")
