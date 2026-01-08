import requests
import unittest
import os
import datetime

METRICS_SERVICE_URL = os.environ.get("METRICS_SERVICE_URL", "http://localhost:8000")
OIDC_TOKEN = os.environ.get("OIDC_TOKEN")

class TestMetricsPipeline(unittest.TestCase):
    def setUp(self):
        self.tenant_id = "test_smoke_tenant"
        self.site_id = "test_smoke_site"
        self.headers = {}
        if OIDC_TOKEN:
            self.headers["Authorization"] = f"Bearer {OIDC_TOKEN}"
        
        self.end_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.start_ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat()

    def test_top_downtime_reasons(self):
        url = f"{METRICS_SERVICE_URL}/execute"
        payload = {
            "query_type": "TOP_DOWNTIME_REASONS",
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "time_range": {
                "start": self.start_ts,
                "end": self.end_ts
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, f"Failed: {response.text}")
        
        data = response.json()
        self.assertEqual(data["requested_query"], "TOP_DOWNTIME_REASONS")
        self.assertIn("rows", data)
        self.assertIn("job_id", data["source"])

    def test_downtime_by_machine(self):
        url = f"{METRICS_SERVICE_URL}/execute"
        payload = {
            "query_type": "DOWNTIME_BY_MACHINE",
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "time_range": {
                "start": self.start_ts,
                "end": self.end_ts
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, f"Failed: {response.text}")
        data = response.json()
        self.assertEqual(data["requested_query"], "DOWNTIME_BY_MACHINE")

    def test_invalid_query_type(self):
        url = f"{METRICS_SERVICE_URL}/execute"
        payload = {
            "query_type": "NON_EXISTENT",
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "time_range": {
                "start": self.start_ts,
                "end": self.end_ts
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 422) 

    def test_invalid_time_range(self):
        url = f"{METRICS_SERVICE_URL}/execute"
        payload = {
            "query_type": "TOP_DOWNTIME_REASONS",
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "time_range": {
                "start": self.end_ts, 
                "end": self.start_ts
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("End time must be after start time", response.text)

if __name__ == "__main__":
    unittest.main()
