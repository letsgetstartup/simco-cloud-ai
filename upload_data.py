import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import os

# --- CONFIGURATION ---
CREDENTIALS_FILE = 'firebase_key.json' # Your downloaded JSON key
DATA_DIR = 'simco_demo_dataset_30d'
CSV_FILES = {
    # Collection Name : CSV Filename
    "machines": os.path.join(DATA_DIR, "machines.csv"),
    "jobs": os.path.join(DATA_DIR, "jobs.csv"),
    "events": os.path.join(DATA_DIR, "events.csv"),
    "tools": os.path.join(DATA_DIR, "tools.csv"),
    "signals": os.path.join(DATA_DIR, "signals.csv") 
}

def upload_data():
    # 1. Initialize Firebase
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: {CREDENTIALS_FILE} not found. Please download it from Firebase Console.")
        return

    cred = credentials.Certificate(CREDENTIALS_FILE)
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        pass # App already initialized

    db = firestore.client()
    print("✅ Connected to Firestore.")

    # 2. Upload CSVs
    for collection_name, csv_file in CSV_FILES.items():
        if os.path.exists(csv_file):
            print(f"Processing {csv_file} -> Collection: '{collection_name}'...")
            
            # Read CSV
            df = pd.read_csv(csv_file)
            
            # Convert to list of dictionaries (records)
            records = df.to_dict(orient='records')
            
            # Batch upload is faster, but for simplicity we iterate
            # (Firestore batch limit is 500, simple iteration is safer for small demos)
            batch = db.batch()
            count = 0
            
            for record in records:
                # Create a new document reference
                doc_ref = db.collection(collection_name).document()
                batch.set(doc_ref, record)
                count += 1
                
                # Commit every 400 records to be safe
                if count % 400 == 0:
                    batch.commit()
                    batch = db.batch()
                    print(f"   - Uploaded {count} records...")
            
            # Commit remaining
            batch.commit()
            print(f"✅ Finished {collection_name}: {count} records uploaded.")
        else:
            print(f"⚠️ Warning: File {csv_file} not found. Skipping.")

if __name__ == "__main__":
    upload_data()
