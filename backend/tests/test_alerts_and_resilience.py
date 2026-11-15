import json
import time
from datetime import datetime, timezone, timedelta
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.pipeline import PipelineModel, PipelineAlertModel
from app.services.stream_processor import stream_processor
from tests.test_helpers import get_admin_headers

class TestAlertsAndResilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app, headers=get_admin_headers())

    def setUp(self):
        self.schema_def = {
            "fields": [
                {"name": "sensor_id", "type": "string", "required": True},
                {"name": "temperature", "type": "float", "required": True},
                {"name": "pressure", "type": "float", "required": False},
            ],
            "strict": False,
        }
        res = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "Industrial IoT Sensors",
                "description": "Factory floor temperature & pressure stream",
                "source": "MQTT - telemetry",
                "destination": "Postgres - iot_archive",
                "schema_definition": self.schema_def,
            },
        )
        assert res.status_code == 201, res.text
        self.pipeline_id = res.json()["id"]

    def tearDown(self):
        self.client.delete(f"/api/v1/pipelines/{self.pipeline_id}")

    def test_01_repeated_schema_violations_alert_and_deduplication(self):
        # Ingest 4 invalid records to cross the repeated violation threshold (>= 3)
        invalid_batch = [
            {"temperature": "not_a_number"},  # missing sensor_id + wrong type
            {"sensor_id": 999, "temperature": "bad"},
            {"sensor_id": 123},  # missing temperature
            {"pressure": 101.3}, # missing sensor_id & temperature
        ]
        res = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": invalid_batch},
        )
        self.assertEqual(res.status_code, 200)

        # Query alerts
        alerts_res = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts")
        self.assertEqual(alerts_res.status_code, 200)
        alerts = alerts_res.json()
        schema_alerts = [a for a in alerts if a["alert_type"] == "repeated_schema_violations"]
        self.assertGreaterEqual(len(schema_alerts), 1)

        alert = schema_alerts[0]
        self.assertEqual(alert["severity"], "warning")
        self.assertIn("Repeated schema violations", alert["title"])
        self.assertFalse(alert["resolved"])
        self.assertFalse(alert["acknowledged"])
        self.assertIsNotNone(alert["evidence"])
        initial_count = alert["occurrence_count"]
        self.assertGreaterEqual(initial_count, 1)

        # Ingest another violation immediately -> should deduplicate and increment occurrence_count
        res2 = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": [{"invalid": "record"}]},
        )
        self.assertEqual(res2.status_code, 200)

        alerts_res2 = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts")
        schema_alerts2 = [a for a in alerts_res2.json() if a["alert_type"] == "repeated_schema_violations"]
        # Deduplication ensures we still have exactly 1 alert row for this dedup_key
        self.assertEqual(len(schema_alerts2), 1)
        self.assertGreaterEqual(schema_alerts2[0]["occurrence_count"], initial_count)

    def test_02_high_failure_rate_alert(self):
        # Ingest a batch with high failure rate (e.g. 5 failed out of 6 records = 83% > 30% threshold)
        batch = [
            {"sensor_id": "sensor_01", "temperature": 25.0}, # 1 valid
            {"bad": 1},
            {"bad": 2},
            {"bad": 3},
            {"bad": 4},
            {"bad": 5},
        ]
        res = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": batch},
        )
        self.assertEqual(res.status_code, 200)

        alerts_res = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts")
        self.assertEqual(alerts_res.status_code, 200)
        alerts = alerts_res.json()
        failure_alerts = [a for a in alerts if a["alert_type"] == "high_failure_rate"]
        self.assertGreaterEqual(len(failure_alerts), 1)
        self.assertEqual(failure_alerts[0]["severity"], "critical")
        self.assertIn("evidence", failure_alerts[0])
        self.assertGreater(failure_alerts[0]["evidence"]["failure_rate"], 30.0)

    def test_03_anomaly_spike_alert(self):
        # Feed 15 normal baseline values so stats can establish mean and std
        baseline = [{"sensor_id": "sensor_01", "temperature": 25.0 + (i % 3) * 0.2} for i in range(15)]
        self.client.post(f"/api/v1/pipelines/{self.pipeline_id}/ingest", json={"records": baseline})

        # Now send 4 extreme outliers to trigger anomaly spike alert (threshold >= 3 anomalies)
        outliers = [
            {"sensor_id": "sensor_01", "temperature": 999.0},
            {"sensor_id": "sensor_01", "temperature": -800.0},
            {"sensor_id": "sensor_01", "temperature": 1500.0},
            {"sensor_id": "sensor_01", "temperature": 2000.0},
        ]
        self.client.post(f"/api/v1/pipelines/{self.pipeline_id}/ingest", json={"records": outliers})

        alerts_res = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts")
        alerts = alerts_res.json()
        anomaly_alerts = [a for a in alerts if a["alert_type"] == "anomaly_spike"]
        self.assertGreaterEqual(len(anomaly_alerts), 1)
        self.assertEqual(anomaly_alerts[0]["severity"], "warning")
        self.assertGreaterEqual(anomaly_alerts[0]["evidence"]["anomaly_count"], 3)

    def test_04_alert_acknowledgement_and_resolution(self):
        # Generate an alert first
        self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/ingest",
            json={"records": [{"bad": i} for i in range(5)]},
        )
        alerts = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts").json()
        self.assertGreater(len(alerts), 0)
        target_alert = alerts[0]
        alert_id = target_alert["id"]

        # Check detail endpoint
        detail_res = self.client.get(f"/api/v1/pipelines/alerts/{alert_id}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["id"], alert_id)

        # 1. Acknowledge alert
        ack_res = self.client.post(f"/api/v1/pipelines/alerts/{alert_id}/acknowledge")
        self.assertEqual(ack_res.status_code, 200)
        ack_data = ack_res.json()
        self.assertTrue(ack_data["acknowledged"])
        self.assertIsNotNone(ack_data["acknowledged_at"])
        self.assertFalse(ack_data["resolved"])

        # 2. Check health score before resolution
        pipe_before = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}").json()
        score_before = pipe_before["health_score"]

        # 3. Resolve alert
        res_res = self.client.post(f"/api/v1/pipelines/alerts/{alert_id}/resolve")
        self.assertEqual(res_res.status_code, 200)
        res_data = res_res.json()
        self.assertTrue(res_data["resolved"])
        self.assertIsNotNone(res_data["resolved_at"])

        # 4. Check health score after resolution -> score should be equal or higher (penalty removed)
        pipe_after = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}").json()
        score_after = pipe_after["health_score"]
        self.assertGreaterEqual(score_after, score_before)

    def test_05_inactivity_audit_endpoint_and_alert(self):
        db = SessionLocal()
        try:
            # Manually set last_ingestion_at to 15 minutes ago
            pipe = db.query(PipelineModel).filter(PipelineModel.id == self.pipeline_id).first()
            pipe.total_records_ingested = 10
            pipe.last_ingestion_at = datetime.now(timezone.utc) - timedelta(minutes=15)
            db.commit()
        finally:
            db.close()

        # Trigger on-demand health check with max_inactive_seconds=300 (5 minutes)
        res = self.client.post(
            f"/api/v1/pipelines/{self.pipeline_id}/health-check?max_inactive_seconds=300"
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["pipeline_id"], self.pipeline_id)
        self.assertIn("health_score", data)

        # Check that inactivity alert was generated
        alerts = self.client.get(f"/api/v1/pipelines/{self.pipeline_id}/alerts").json()
        inactivity_alerts = [a for a in alerts if a["alert_type"] == "inactivity"]
        self.assertEqual(len(inactivity_alerts), 1)
        self.assertEqual(inactivity_alerts[0]["severity"], "warning")
        self.assertIn("inactive_seconds", inactivity_alerts[0]["evidence"])

    def test_06_explainable_health_score_calculation(self):
        db = SessionLocal()
        try:
            pipe = db.query(PipelineModel).filter(PipelineModel.id == self.pipeline_id).first()
            # Scenario A: 100% success rate, low latency, no alerts -> health 100.0
            pipe.success_rate = 100.0
            pipe.avg_latency_ms = 12.0
            pipe.status = "active"
            health_a = stream_processor.calculate_pipeline_health(pipe, db)
            self.assertEqual(health_a, 100.0)

            # Scenario B: Add a critical unresolved alert
            alert = PipelineAlertModel(
                pipeline_id=self.pipeline_id,
                severity="critical",
                alert_type="high_failure_rate",
                title="Critical failure test",
                description="Test description",
                dedup_key=f"{self.pipeline_id}:test_crit",
                resolved=False,
            )
            db.add(alert)
            db.commit()

            health_b = stream_processor.calculate_pipeline_health(pipe, db)
            # Critical penalty is -20
            self.assertLessEqual(health_b, 80.0)

            # Scenario C: Resolve the alert -> health restored to 100.0
            alert.resolved = True
            db.commit()
            health_c = stream_processor.calculate_pipeline_health(pipe, db)
            self.assertEqual(health_c, 100.0)
        finally:
            db.close()
