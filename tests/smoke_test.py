import requests
import unittest
import os
import datetime

METRICS_SERVICE_URL = os.environ.get("METRICS_SERVICE_URL", "http://localhost:8000")
OIDC_TOKEN = os.environ.get("OIDC_TOKEN")

class TestMetricsPipeline(unittest.TestCase):
    def setUp(self):
        self.tenant_id = "test_tenant"
        self.site_id = "test_site"
        self.headers = {"X-Tenant-ID": self.tenant_id} # Mock security header
        
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
        self.assertEqual(data["query_type"], "TOP_DOWNTIME_REASONS")
        self.assertIn("confidence", data)
        self.assertIn("warnings", data)
        self.assertIn("metric_version", data)
        self.assertIn("audit", data)
        self.assertIn("query_hash", data["audit"])
        self.assertIn("rows", data)
        
        # Log findings for visibility
        print(f"DQ Confidence: {data['confidence']}")
        print(f"DQ Warnings: {data['warnings']}")

    def test_downtime_by_machine_rollup(self):
        """Test long-range query to verify intelligent rollup routing."""
        url = f"{METRICS_SERVICE_URL}/execute"
        # 30 day range
        payload = {
            "query_type": "DOWNTIME_BY_MACHINE",
            "tenant_id": self.tenant_id,
            "site_id": self.site_id,
            "time_range": {
                "start": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)).isoformat(),
                "end": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, f"Failed: {response.text}")
        data = response.json()
        self.assertEqual(data["effective_time_range"]["source"], "rollup")
        self.assertIn("events_daily_rollup", data["audit"]["table"])

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
        self.assertEqual(response.status_code, 400) 
        self.assertIn("INVALID_QUERY_TYPE", response.text)

    def test_missing_time_range(self):
        url = f"{METRICS_SERVICE_URL}/execute"
        payload = {
            "query_type": "TOP_DOWNTIME_REASONS",
            "tenant_id": self.tenant_id,
            "site_id": self.site_id
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

    def test_tenant_security(self):
        """Test that the service rejects requests with mismatched tenant headers."""
        url = f"{METRICS_SERVICE_URL}/execute"
        payload = {
            "query_type": "TOP_DOWNTIME_REASONS",
            "tenant_id": "malicious_tenant",
            "site_id": self.site_id,
            "time_range": {
                "start": self.start_ts,
                "end": self.end_ts
            }
        }
        # Header has "test_tenant", body has "malicious_tenant"
        response = requests.post(url, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Tenant context mismatch", response.text)

if __name__ == "__main__":
    unittest.main()
