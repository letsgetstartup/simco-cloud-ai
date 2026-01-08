from fastapi.testclient import TestClient
from main import app
import datetime
import os

# Set Project ID for the test
os.environ["GOOGLE_CLOUD_PROJECT"] = "solidcam-f58bc"
os.environ["GCP_PROJECT"] = "solidcam-f58bc"

client = TestClient(app)

def test_top_downtime_reasons():
    now = datetime.datetime.now(datetime.timezone.utc)
    start_ts = now - datetime.timedelta(hours=24)
    end_ts = now + datetime.timedelta(hours=1) # slightly future to catch everything
    
    payload = {
        "query_type": "TOP_DOWNTIME_REASONS",
        "tenant_id": "test_tenant",
        "site_id": "test_site",
        "time_range": {
            "start": start_ts.isoformat(),
            "end": end_ts.isoformat()
        }
    }
    
    print(f"Testing with payload: {payload}")
    
    # We need to send X-Tenant-ID header since it is required for security
    response = client.post("/execute", json=payload, headers={"X-Tenant-ID": "test_tenant"})
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["metric_name"] == "top_downtime_reasons"
    assert len(data["rows"]) > 0
    assert data["rows"][0]["reason"] == "TEST_REASON"
    
if __name__ == "__main__":
    try:
        test_top_downtime_reasons()
        print("✅ API Test Passed!")
    except Exception as e:
        print(f"❌ API Test Failed: {e}")
        exit(1)
