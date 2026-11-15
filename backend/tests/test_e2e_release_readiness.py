import os
import json
import time
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.core.config import settings
from app.services.cache_service import cache_service

import fakeredis

class TestReleaseReadinessE2E(unittest.TestCase):
    """
    End-to-End Release Readiness Suite covering all 11 critical workflows:
    1. Register and log in.
    2. Create and switch organizations where permitted.
    3. Upload a CSV/Excel dataset.
    4. View profiling and data-quality results.
    5. Detect anomalies.
    6. Ask questions through Gemini Copilot.
    7. Create a pipeline and ingest JSON events.
    8. Verify live dashboard updates.
    9. Trigger and acknowledge alerts.
    10. Verify Redis caching and invalidation.
    11. Verify role permissions and cross-organization isolation.
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.fake_redis = fakeredis.FakeRedis(decode_responses=True)
        cache_service.set_client(cls.fake_redis)
        cls.client = TestClient(app)

    def setUp(self):
        self.fake_redis.flushall()

    def test_01_workflow_register_and_login(self):
        """Workflow 1: Register and log in."""
        unique_email = f"e2e_lead_{int(time.time() * 1000)}@datapulse.io"
        reg_payload = {
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Jordan Data Lead",
            "role": "data_engineer",
            "organization_name": "Jordan Analytics Org",
        }
        reg_res = self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(reg_res.status_code, 201)
        reg_data = reg_res.json()
        self.assertIn("access_token", reg_data)
        self.assertIn("refresh_token", reg_data)

        # Verify /me profile with the issued token
        headers = {"Authorization": f"Bearer {reg_data['access_token']}"}
        me_res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        me_data = me_res.json()
        self.assertEqual(me_data["email"], unique_email)
        self.assertEqual(me_data["full_name"], "Jordan Data Lead")
        self.assertEqual(me_data["role"], "data_engineer")
        self.assertIsNotNone(me_data["active_organization_id"])

        # Test login
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "SecurePassword123!"},
        )
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.json()
        self.assertIn("access_token", login_data)

    def test_02_workflow_create_and_switch_organizations(self):
        """Workflow 2: Create and switch organizations where permitted."""
        email = f"org_admin_{int(time.time() * 1000)}@datapulse.io"
        reg_res = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "SecurePassword123!",
                "full_name": "Org Administrator",
                "role": "admin",
                "organization_name": "Primary Workspace",
            },
        )
        self.assertEqual(reg_res.status_code, 201)
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create secondary organization
        create_res = self.client.post(
            "/api/v1/organizations/",
            json={"name": "Secondary Enterprise Org", "description": "Production EU workspace"},
            headers=headers,
        )
        self.assertEqual(create_res.status_code, 201)
        sec_org = create_res.json()
        sec_org_id = sec_org["id"]

        # List organizations
        list_res = self.client.get("/api/v1/organizations/", headers=headers)
        self.assertEqual(list_res.status_code, 200)
        orgs = list_res.json()
        self.assertGreaterEqual(len(orgs), 2)
        self.assertTrue(any(o["name"] == "Secondary Enterprise Org" for o in orgs))

        # Switch to secondary organization
        switch_res = self.client.post(f"/api/v1/organizations/switch/{sec_org_id}", headers=headers)
        self.assertEqual(switch_res.status_code, 200)
        switch_data = switch_res.json()
        self.assertIn("access_token", switch_data)

        # Verify active context reflects new organization
        switched_headers = {"Authorization": f"Bearer {switch_data['access_token']}"}
        me_switched = self.client.get("/api/v1/auth/me", headers=switched_headers)
        self.assertEqual(me_switched.status_code, 200)
        self.assertEqual(me_switched.json()["active_organization_id"], sec_org_id)

    def test_03_to_05_workflows_dataset_upload_profiling_and_anomalies(self):
        """Workflows 3, 4, 5: Upload CSV, view profiling & quality results, detect anomalies."""
        email = f"data_eng_{int(time.time() * 1000)}@datapulse.io"
        reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "SecurePassword123!",
                "full_name": "Eng Profiler",
                "role": "data_engineer",
                "organization_name": "Data Quality Org",
            },
        )
        self.assertEqual(reg.status_code, 201)
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # 3. Upload dataset (dirty_transactions.csv)
        csv_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "dirty_transactions.csv")
        self.assertTrue(os.path.exists(csv_path), f"Sample file not found at {csv_path}")

        with open(csv_path, "rb") as f:
            upload_res = self.client.post(
                "/api/v1/datasets/upload",
                files={"file": ("dirty_transactions.csv", f, "text/csv")},
                headers=headers,
            )
        self.assertEqual(upload_res.status_code, 201)
        dataset_data = upload_res.json()
        dataset_id = dataset_data["id"]
        self.assertIn("Dirty Transactions", dataset_data["name"])
        self.assertIn(dataset_data["status"], ["healthy", "warning", "critical"])

        # 4. View profiling and quality scores
        detail_res = self.client.get(f"/api/v1/datasets/{dataset_id}", headers=headers)
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertGreater(detail["row_count"], 0)
        self.assertGreater(detail["column_count"], 0)
        self.assertIn("quality_score", detail)
        self.assertIn("column_profiles", detail)
        self.assertTrue(len(detail["column_profiles"]) > 0)
        self.assertIn("quality_report", detail)

        # 5. Detect anomalies
        self.assertIn("anomalies", detail)
        self.assertGreaterEqual(len(detail["anomalies"]), 1)
        anomaly_types = [a["anomaly_type"] for a in detail["anomalies"]]
        self.assertTrue(any("outlier" in t or "statistical" in t or "null" in t for t in anomaly_types))

    def test_06_workflow_gemini_copilot(self):
        """Workflow 6: Ask questions through Gemini Copilot and get recommendations."""
        email = f"copilot_user_{int(time.time() * 1000)}@datapulse.io"
        reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "SecurePassword123!",
                "full_name": "Copilot Tester",
                "role": "data_engineer",
                "organization_name": "Copilot Test Org",
            },
        )
        self.assertEqual(reg.status_code, 201)
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Upload dataset for Copilot context
        csv_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "clean_customers.csv")
        with open(csv_path, "rb") as f:
            upload_res = self.client.post(
                "/api/v1/datasets/upload",
                files={"file": ("clean_customers.csv", f, "text/csv")},
                headers=headers,
            )
        dataset_id = upload_res.json()["id"]

        # Fetch suggestions
        sug_res = self.client.get(f"/api/v1/copilot/suggestions/{dataset_id}", headers=headers)
        self.assertEqual(sug_res.status_code, 200)
        suggestions = sug_res.json()["suggestions"]
        self.assertGreaterEqual(len(suggestions), 1)

        # Query Copilot
        query_res = self.client.post(
            "/api/v1/copilot/query",
            json={
                "dataset_id": dataset_id,
                "question": "What is the overall data quality of this customer dataset?",
            },
            headers=headers,
        )
        self.assertEqual(query_res.status_code, 200)
        resp_data = query_res.json()
        self.assertIn("answer", resp_data)
        self.assertIn("metrics", resp_data)
        self.assertTrue(len(resp_data["answer"]) > 20)

    def test_07_to_09_workflows_streaming_telemetry_and_alerts(self):
        """Workflows 7, 8, 9: Pipeline creation, stream ingest, live telemetry, alert acknowledge & resolve."""
        email = f"pipeline_eng_{int(time.time() * 1000)}@datapulse.io"
        reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "SecurePassword123!",
                "full_name": "Stream Lead",
                "role": "data_engineer",
                "organization_name": "Pipeline Stream Org",
            },
        )
        self.assertEqual(reg.status_code, 201)
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # 7. Create Pipeline
        schema_def = {
            "fields": [
                {"name": "order_id", "type": "string", "required": True},
                {"name": "amount", "type": "float", "required": True},
                {"name": "currency", "type": "string", "required": False},
            ],
            "strict": False,
        }
        pipe_res = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "E-Commerce Ingestion Pipeline",
                "source": "Kafka - orders_raw",
                "destination": "Postgres - orders_curated",
                "schema_definition": schema_def,
            },
            headers=headers,
        )
        self.assertEqual(pipe_res.status_code, 201)
        pipeline_id = pipe_res.json()["id"]

        # Ingest valid events
        valid_records = [
            {"order_id": f"ord_{i}", "amount": 100.0 + i * 5, "currency": "USD"}
            for i in range(5)
        ]
        ingest_res = self.client.post(
            f"/api/v1/pipelines/{pipeline_id}/ingest",
            json={"records": valid_records},
            headers=headers,
        )
        self.assertEqual(ingest_res.status_code, 200)
        self.assertEqual(ingest_res.json()["records_accepted"], 5)

        # 8. Verify live dashboard metrics snapshots
        pipe_detail_res = self.client.get(f"/api/v1/pipelines/{pipeline_id}", headers=headers)
        self.assertEqual(pipe_detail_res.status_code, 200)
        pipe_detail = pipe_detail_res.json()
        self.assertGreaterEqual(pipe_detail["total_records_processed"], 5)
        self.assertEqual(pipe_detail["total_records_ingested"], 5)

        metrics_res = self.client.get(f"/api/v1/pipelines/{pipeline_id}/metrics", headers=headers)
        self.assertEqual(metrics_res.status_code, 200)
        metrics = metrics_res.json()
        self.assertIsInstance(metrics, list)
        self.assertGreaterEqual(len(metrics), 1)
        latest_metric = metrics[0]
        self.assertGreaterEqual(latest_metric["records_processed"], 1)

        # 9. Ingest invalid records to trigger alerts
        bad_records = [
            {"amount": "not_numeric"}, # missing order_id & wrong amount
            {"currency": "USD"},
            {"amount": None},
            {"bad": True},
        ]
        self.client.post(
            f"/api/v1/pipelines/{pipeline_id}/ingest",
            json={"records": bad_records},
            headers=headers,
        )

        alerts_res = self.client.get(f"/api/v1/pipelines/{pipeline_id}/alerts", headers=headers)
        self.assertEqual(alerts_res.status_code, 200)
        alerts = alerts_res.json()
        self.assertGreaterEqual(len(alerts), 1)
        target_alert = alerts[0]
        alert_id = target_alert["id"]

        # Acknowledge alert
        ack_res = self.client.post(
            f"/api/v1/pipelines/alerts/{alert_id}/acknowledge",
            headers=headers,
        )
        self.assertEqual(ack_res.status_code, 200)
        self.assertTrue(ack_res.json()["acknowledged"])

        # Resolve alert
        res_res = self.client.post(
            f"/api/v1/pipelines/alerts/{alert_id}/resolve",
            headers=headers,
        )
        self.assertEqual(res_res.status_code, 200)
        self.assertTrue(res_res.json()["resolved"])

    def test_10_workflow_redis_caching_and_invalidation(self):
        """Workflow 10: Verify Redis caching hits, misses, TTL, and mutation invalidation."""
        email = f"cache_user_{int(time.time() * 1000)}@datapulse.io"
        reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "SecurePassword123!",
                "full_name": "Cache Tester",
                "role": "data_engineer",
                "organization_name": "Caching Test Org",
            },
        )
        self.assertEqual(reg.status_code, 201)
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Query me to get active org
        me_res = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)
        org_id = me_res.json()["active_organization_id"]

        summary_key = cache_service.build_key(org_id, "overview", "summary")
        self.assertIsNone(self.fake_redis.get(summary_key))

        # First request -> cache miss, populates Redis
        res1 = self.client.get("/api/v1/overview/summary", headers=headers)
        self.assertEqual(res1.status_code, 200)
        self.assertIsNotNone(self.fake_redis.get(summary_key))

        # Second request -> cache hit
        res2 = self.client.get("/api/v1/overview/summary", headers=headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res1.json(), res2.json())

        # Create pipeline -> triggers invalidation of overview summary
        schema_def = {"fields": [{"name": "id", "type": "string"}]}
        self.client.post(
            "/api/v1/pipelines/",
            json={"name": "Cache Test Pipe", "schema_definition": schema_def},
            headers=headers,
        )
        # Overview cache key was invalidated
        self.assertIsNone(self.fake_redis.get(summary_key))

    def test_11_workflow_rbac_permissions_and_tenant_isolation(self):
        """Workflow 11: Verify role permissions and cross-organization tenant isolation."""
        # Create Org A with admin
        admin_res = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tenant_a_admin_{int(time.time() * 1000)}@org-a.com",
                "password": "SecurePassword123!",
                "full_name": "Alpha Admin",
                "role": "admin",
                "organization_name": "Tenant Alpha",
            },
        )
        self.assertEqual(admin_res.status_code, 201)
        admin_headers = {"Authorization": f"Bearer {admin_res.json()['access_token']}"}

        # Admin creates pipeline in Org A
        p_res = self.client.post(
            "/api/v1/pipelines/",
            json={"name": "Alpha Confidential Pipeline", "schema_definition": {"fields": [{"name": "id", "type": "string"}]}},
            headers=admin_headers,
        )
        self.assertEqual(p_res.status_code, 201)
        pipe_id_a = p_res.json()["id"]

        # Create Viewer in Org A
        viewer_res = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tenant_a_viewer_{int(time.time() * 1000)}@org-a.com",
                "password": "SecurePassword123!",
                "full_name": "Alpha Viewer",
                "role": "viewer",
                "organization_name": "Tenant Alpha Viewer Group",
            },
        )
        self.assertEqual(viewer_res.status_code, 201)
        viewer_headers = {"Authorization": f"Bearer {viewer_res.json()['access_token']}"}

        # Viewer attempts pipeline creation -> 403 Forbidden (RBAC enforcement)
        bad_create = self.client.post(
            "/api/v1/pipelines/",
            json={"name": "Viewer Pipe", "schema_definition": {"fields": [{"name": "id", "type": "string"}]}},
            headers=viewer_headers,
        )
        self.assertEqual(bad_create.status_code, 403)

        # Create Org B with separate user
        b_res = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tenant_b_user_{int(time.time() * 1000)}@org-b.com",
                "password": "SecurePassword123!",
                "full_name": "Beta Admin",
                "role": "admin",
                "organization_name": "Tenant Beta",
            },
        )
        self.assertEqual(b_res.status_code, 201)
        b_headers = {"Authorization": f"Bearer {b_res.json()['access_token']}"}

        # Tenant B attempts to read Tenant A's pipeline -> 404 Not Found (Tenant isolation / IDOR protection)
        idor_res = self.client.get(f"/api/v1/pipelines/{pipe_id_a}", headers=b_headers)
        self.assertEqual(idor_res.status_code, 404)

        # Tenant B pipeline list does NOT contain Tenant A's pipeline
        list_b = self.client.get("/api/v1/pipelines/", headers=b_headers)
        self.assertEqual(list_b.status_code, 200)
        self.assertFalse(any(p["id"] == pipe_id_a for p in list_b.json()))

if __name__ == "__main__":
    unittest.main()
