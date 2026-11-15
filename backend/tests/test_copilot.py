import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.models.dataset import DatasetModel
from app.services.copilot_context import build_dataset_context, generate_dataset_suggestions
from tests.test_helpers import get_admin_headers

class TestCopilotEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app, headers=get_admin_headers())
        cls.samples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")

        # Ingest a clean dataset and a dirty dataset for tests
        clean_path = os.path.join(cls.samples_dir, "clean_customers.csv")
        with open(clean_path, "rb") as f:
            res_clean = cls.client.post(
                "/api/v1/datasets/upload",
                files={"file": ("copilot_test_clean.csv", f, "text/csv")},
            )
        assert res_clean.status_code == 201, res_clean.text
        cls.clean_id = res_clean.json()["id"]

        dirty_path = os.path.join(cls.samples_dir, "dirty_transactions.csv")
        with open(dirty_path, "rb") as f:
            res_dirty = cls.client.post(
                "/api/v1/datasets/upload",
                files={"file": ("copilot_test_dirty.csv", f, "text/csv")},
            )
        assert res_dirty.status_code == 201, res_dirty.text
        cls.dirty_id = res_dirty.json()["id"]

    def test_01_privacy_safe_context_builder(self):
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            dataset = db.query(DatasetModel).filter(DatasetModel.id == self.dirty_id).first()
            self.assertIsNotNone(dataset)
            context = build_dataset_context(dataset)

            # Assert top-level keys
            self.assertIn("dataset", context)
            self.assertIn("quality", context)
            self.assertIn("columns", context)
            self.assertIn("columns_with_nulls", context)
            self.assertIn("anomalies", context)

            # Assert aggregates only, no raw row rows / PII
            self.assertEqual(context["dataset"]["row_count"], 100)
            self.assertNotIn("raw_rows", context)
            self.assertNotIn("records", context)

            # Quality metrics are present
            self.assertIn("overall_score", context["quality"])
            self.assertIn("completeness_score", context["quality"])

            # Anomalies list is populated
            self.assertGreater(len(context["anomalies"]), 0)
        finally:
            db.close()

    def test_02_dynamic_suggestions_generation(self):
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            dataset = db.query(DatasetModel).filter(DatasetModel.id == self.dirty_id).first()
            context = build_dataset_context(dataset)
            suggestions = generate_dataset_suggestions(context)

            self.assertEqual(len(suggestions), 4)
            # Should have context-specific queries
            self.assertTrue(any("quality" in s.lower() for s in suggestions))
            self.assertTrue(any("missing" in s.lower() or "anomaly" in s.lower() for s in suggestions))
        finally:
            db.close()

    def test_03_query_dataset_not_found(self):
        res = self.client.post(
            "/api/v1/copilot/query",
            json={"dataset_id": "non-existent-id", "question": "Explain this dataset."},
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_04_query_dataset_empty_question(self):
        res = self.client.post(
            "/api/v1/copilot/query",
            json={"dataset_id": self.dirty_id, "question": "   "},
        )
        self.assertEqual(res.status_code, 422)

    def test_05_grounded_fallback_explanation(self):
        # Query dirty dataset regarding data quality without Gemini API key
        res = self.client.post(
            "/api/v1/copilot/query",
            json={
                "dataset_id": self.dirty_id,
                "question": "What are the biggest data-quality problems in this dataset?",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["dataset_id"], self.dirty_id)
        self.assertTrue(data["is_fallback"])
        self.assertIn("copilot_test_dirty.csv", data["answer"])
        # Should contain verified metrics and actionable recommendations
        self.assertIsNotNone(data["metrics"])
        self.assertGreaterEqual(len(data["metrics"]), 2)
        self.assertIsNotNone(data["recommendations"])
        self.assertGreaterEqual(len(data["recommendations"]), 1)

    def test_06_grounded_fallback_root_cause_and_recommendations(self):
        # Query root cause for missing values
        res = self.client.post(
            "/api/v1/copilot/query",
            json={
                "dataset_id": self.dirty_id,
                "question": "Why is the data quality score low and what should I fix?",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("Quality Audit Findings", data["answer"])
        self.assertIn("Actionable Recommendations", data["answer"])
        self.assertGreater(len(data["recommendations"]), 0)

    def test_07_mocked_gemini_api_integration(self):
        # Mock google.genai Client response
        mock_response = MagicMock()
        mock_response.text = (
            "Based on the verified profiling, copilot_test_dirty.csv exhibits critical null values.\n"
            "Recommendations:\n"
            "- Investigate upstream ETL ingestion timeouts on the customer_notes column.\n"
            "- Review validation rules before loading into warehouse."
        )

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.services.gemini_service.GeminiCopilotService.is_api_configured", return_value=True):
            with patch("app.services.gemini_service.GeminiCopilotService._get_client", return_value=mock_client):
                res = self.client.post(
                    "/api/v1/copilot/query",
                    json={
                        "dataset_id": self.dirty_id,
                        "question": "Provide a comprehensive audit of this dataset.",
                    },
                )
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertFalse(data["is_fallback"])
                self.assertIn("upstream ETL ingestion timeouts", data["answer"])
                self.assertGreaterEqual(len(data["recommendations"]), 1)

    def test_08_suggestions_endpoint(self):
        res = self.client.get(f"/api/v1/copilot/suggestions/{self.clean_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["dataset_id"], self.clean_id)
        self.assertEqual(len(data["suggestions"]), 4)

    def test_09_history_and_clear_history(self):
        # First verify history has messages from earlier queries on dirty_id
        res = self.client.get(f"/api/v1/copilot/history/{self.dirty_id}")
        self.assertEqual(res.status_code, 200)
        messages = res.json()
        self.assertGreater(len(messages), 0)

        # Clear history
        del_res = self.client.delete(f"/api/v1/copilot/history/{self.dirty_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertGreater(del_res.json()["deleted_count"], 0)

        # History should now be empty
        check_res = self.client.get(f"/api/v1/copilot/history/{self.dirty_id}")
        self.assertEqual(check_res.status_code, 200)
        self.assertEqual(len(check_res.json()), 0)

if __name__ == "__main__":
    unittest.main()
