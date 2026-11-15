import time
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.models.pipeline import PipelineModel
from tests.test_helpers import get_admin_headers

class TestStreamIngestionAndProcessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app, headers=get_admin_headers())

    def setUp(self):
        # Create a test pipeline for each test
        schema_def = {
            "fields": [
                {"name": "order_id", "type": "string", "required": True},
                {"name": "user_id", "type": "string", "required": True},
                {"name": "amount", "type": "float", "required": True},
                {"name": "currency", "type": "string", "required": False},
                {"name": "is_express", "type": "boolean", "required": False},
            ],
            "strict": False,
        }
        res = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "E-Commerce Checkout Stream",
                "description": "Live checkout order transactions",
                "source": "Kafka - orders-topic",
                "destination": "Snowflake - order_events",
                "schema_definition": schema_def,
            },
        )
        assert res.status_code == 201, res.text
        self.pipeline_id = res.json()["id"]

    def tearDown(self):
        # Clean up test pipeline
        self.client.delete(f"/api/v1/pipelines/{self.pipeline_id}")

    def test_01_pipeline_lifecycle_crud_and_status(self):
        # 1. Get detail
        res = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["name"], "E-Commerce Checkout Stream")
        self.assertEqual(data["status"], "active")

        # 2. Update pipeline
        update_res = self.client.put(
            f"/api/v1/pipelines/{self.pipeline_id}",
            json={"description": "Updated checkout description", "source": "HTTP Gateway"},
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(update_res.json()["source"], "HTTP Gateway")

        # 3. Stop pipeline
        stop_res = self.client.post(f"/api/v1/pipelines/{self.pipeline_id}/stop")
        self.assertEqual(stop_res.status_code, 200)
        self.assertEqual(stop_res.json()["status"], "stopped")

        # 4. Ingest while stopped should be rejected (400)
        ingest_res = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"record": {"order_id": "ord-1", "user_id": "usr-1", "amount": 99.5}},
        )
        self.assertEqual(ingest_res.status_code, 400)
        self.assertIn("stopped", ingest_res.json()["detail"].lower())

        # 5. Start pipeline
        start_res = self.client.post(f"/api/v1/pipelines/{self.pipeline_id}/start")
        self.assertEqual(start_res.status_code, 200)
        self.assertEqual(start_res.json()["status"], "active")

    def test_02_single_and_batch_valid_ingestion(self):
        # 1. Single valid record
        res1 = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={
                "record": {
                    "order_id": "ord-1001",
                    "user_id": "usr-2001",
                    "amount": 49.99,
                    "currency": "USD",
                    "is_express": True,
                }
            },
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["records_received"], 1)
        self.assertEqual(data1["records_accepted"], 1)
        self.assertEqual(data1["records_rejected"], 0)
        self.assertGreater(data1["avg_latency_ms"], 0.0)

        # 2. Batch valid records
        batch = [
            {"order_id": f"ord-{i}", "user_id": f"usr-{i}", "amount": float(i * 10), "currency": "USD"}
            for i in range(2, 7)
        ]
        res2 = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": batch},
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["records_received"], 5)
        self.assertEqual(data2["records_accepted"], 5)
        self.assertEqual(data2["records_rejected"], 0)

        # Verify pipeline counters updated
        detail = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}").json()
        self.assertEqual(detail["total_records_ingested"], 6)
        self.assertEqual(detail["total_records_processed"], 6)
        self.assertEqual(detail["success_rate"], 100.0)

    def test_03_schema_violations_and_malformed_records(self):
        # Record 1: missing required 'amount'
        # Record 2: type mismatch ('amount' passed as string)
        # Record 3: valid record
        batch = [
            {"order_id": "ord-bad-1", "user_id": "usr-bad-1"},  # missing amount
            {"order_id": "ord-bad-2", "user_id": "usr-bad-2", "amount": "one-hundred"},  # string amount
            {"order_id": "ord-good-3", "user_id": "usr-good-3", "amount": 75.0, "currency": None},  # optional null is accepted
        ]

        res = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": batch},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["records_received"], 3)
        self.assertEqual(data["records_accepted"], 1)
        self.assertEqual(data["records_rejected"], 2)
        self.assertEqual(len(data["validation_errors"]), 2)

        # Errors contain clear reasons
        error_messages = [e["error"]["message"] for e in data["validation_errors"]]
        self.assertTrue(any("missing or null" in msg for msg in error_messages))
        self.assertTrue(any("expected type 'float'" in msg.lower() for msg in error_messages))

    def test_04_batch_size_and_unknown_pipeline_limits(self):
        # 1. Unknown pipeline ID -> 404
        res404 = self.client.post(
            "/api/v1/pipelines/non-existent-pipe-id/ingest",
            json={"record": {"order_id": "1", "user_id": "1", "amount": 10.0}},
        )
        self.assertEqual(res404.status_code, 404)

        # 2. Empty records payload -> 422
        res_empty = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": []},
        )
        self.assertEqual(res_empty.status_code, 422)

        # 3. Payload with neither 'record' nor 'records' -> 422
        res_none = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={},
        )
        self.assertEqual(res_none.status_code, 422)

        # 4. Exceeding batch size limit (> 500) -> 413
        oversized_batch = [{"order_id": f"ord-{i}", "user_id": "usr", "amount": 10.0} for i in range(501)]
        res_large = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": oversized_batch},
        )
        self.assertEqual(res_large.status_code, 413)

    def test_05_duplicate_record_detection(self):
        record = {
            "order_id": "ord-dedup-test",
            "user_id": "usr-dedup-test",
            "amount": 120.0,
            "currency": "USD",
        }

        # First ingestion -> unique
        res1 = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"record": record},
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(len(res1.json().get("anomalies_detected") or []), 0)

        # Second ingestion with same payload -> flagged as duplicate anomaly
        res2 = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"record": record},
        )
        self.assertEqual(res2.status_code, 200)
        anomalies = res2.json().get("anomalies_detected") or []
        self.assertTrue(any(a["type"] == "duplicate_record" for a in anomalies))

    def test_06_numeric_anomaly_detection_zscore(self):
        # 1. Feed 15 normal baseline records (amount around 50.0 ± 2.0)
        baseline = [
            {"order_id": f"base-{i}", "user_id": f"u-{i}", "amount": 50.0 + (i % 3)}
            for i in range(15)
        ]
        self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": baseline},
        )

        # 2. Ingest an extreme statistical outlier (amount = 950.0)
        res_outlier = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"record": {"order_id": "spike-1", "user_id": "u-spike", "amount": 950.0}},
        )
        self.assertEqual(res_outlier.status_code, 200)
        anomalies = res_outlier.json().get("anomalies_detected") or []
        self.assertTrue(len(anomalies) >= 1)
        outlier_anom = [a for a in anomalies if a["type"] == "zscore_outlier"]
        self.assertTrue(len(outlier_anom) >= 1)
        self.assertEqual(outlier_anom[0]["column"], "amount")

    def test_07_alert_generation_and_deduplication(self):
        # Ingest batch with 80% failures to trigger high_failure_rate alert
        bad_batch = [
            {"order_id": f"bad-{i}"}  # missing user_id and amount
            for i in range(10)
        ] + [
            {"order_id": "good-1", "user_id": "u-1", "amount": 10.0}
        ]
        res = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": bad_batch},
        )
        self.assertEqual(res.status_code, 200)

        # Check alerts endpoint
        alerts_res = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts")
        self.assertEqual(alerts_res.status_code, 200)
        alerts = alerts_res.json()
        self.assertTrue(len(alerts) >= 1)
        self.assertTrue(any(a["alert_type"] == "high_failure_rate" for a in alerts))

        # Re-triggering immediately within 60s cooldown should NOT create duplicate alert row,
        # but increment occurrence_count on existing alert
        count_before = len(alerts)
        self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": bad_batch},
        )
        alerts_res2 = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts")
        alerts2 = alerts_res2.json()
        self.assertEqual(len(alerts2), count_before)
        failure_alert = next(a for a in alerts2 if a["alert_type"] == "high_failure_rate")
        self.assertGreaterEqual(failure_alert["occurrence_count"], 2)

    def test_08_simulator_start_stop_and_status(self):
        # 1. Check simulator initial status (not running)
        res_init = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/simulator/status")
        self.assertEqual(res_init.status_code, 200)
        self.assertFalse(res_init.json()["is_running"])

        # 2. Start simulator
        res_start = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/simulator/start",
            json={"rate_records_per_sec": 10.0, "batch_size": 2, "anomaly_rate": 0.1},
        )
        self.assertEqual(res_start.status_code, 200)
        self.assertTrue(res_start.json()["is_running"])
        self.assertTrue(res_start.json()["is_simulated"])

        # Give simulator short time to generate a tick
        time.sleep(0.3)

        # 3. Check status during execution
        res_mid = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/simulator/status")
        self.assertEqual(res_mid.status_code, 200)
        self.assertTrue(res_mid.json()["is_running"])

        # 4. Stop simulator
        res_stop = self.client.post(f"/api/v1/pipelines/{self.pipeline_id}/simulator/stop")
        self.assertEqual(res_stop.status_code, 200)
        self.assertFalse(res_stop.json()["is_running"])

    def test_09_metrics_snapshots_endpoint(self):
        # Ingest a couple records to populate metric snapshot
        self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"record": {"order_id": "m-1", "user_id": "u-1", "amount": 20.0}},
        )
        metrics_res = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/metrics")
        self.assertEqual(metrics_res.status_code, 200)
        snapshots = metrics_res.json()
        self.assertGreater(len(snapshots), 0)
        self.assertEqual(snapshots[0]["pipeline_id"], self.pipeline_id)
        self.assertGreaterEqual(snapshots[0]["records_in_interval"], 1)

if __name__ == "__main__":
    unittest.main()
