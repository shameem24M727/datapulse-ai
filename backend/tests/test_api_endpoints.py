import os
import sys
import unittest

from fastapi.testclient import TestClient
from app.main import app
from app.db.init_db import init_db
from tests.test_helpers import get_admin_headers

class TestAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app, headers=get_admin_headers())
        cls.samples_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")

    def test_01_health_endpoints(self):
        res1 = self.client.get("/health")
        self.assertEqual(res1.status_code, 200)
        self.assertIn(res1.json()["milestone"], [2, 3])

        res2 = self.client.get("/api/v1/health/detailed")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["services"]["api"], "online")

    def test_02_upload_clean_csv(self):
        path = os.path.join(self.samples_dir, "clean_customers.csv")
        with open(path, "rb") as f:
            res = self.client.post("/api/v1/datasets/upload", files={"file": ("clean_customers.csv", f, "text/csv")})

        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["original_filename"], "clean_customers.csv")
        self.assertEqual(data["row_count"], 50)
        self.assertEqual(data["column_count"], 6)
        self.assertGreaterEqual(data["quality_score"], 85.0)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(len(data["column_profiles"]), 6)
        self.assertIsNotNone(data["quality_report"])

    def test_03_upload_dirty_csv_and_anomalies(self):
        path = os.path.join(self.samples_dir, "dirty_transactions.csv")
        with open(path, "rb") as f:
            res = self.client.post("/api/v1/datasets/upload", files={"file": ("dirty_transactions.csv", f, "text/csv")})

        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["row_count"], 100)
        # Should detect anomalies (null spike and/or statistical outliers)
        self.assertTrue(len(data["anomalies"]) >= 1)
        # Should have lower quality score due to nulls and duplicates
        self.assertLess(data["quality_score"], 100.0)

    def test_04_upload_excel_xlsx(self):
        path = os.path.join(self.samples_dir, "inventory_products.xlsx")
        with open(path, "rb") as f:
            res = self.client.post(
                "/api/v1/datasets/upload",
                files={"file": ("inventory_products.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["file_type"], "xlsx")
        self.assertEqual(data["row_count"], 40)
        self.assertEqual(data["column_count"], 6)

    def test_05_upload_empty_file_rejected(self):
        path = os.path.join(self.samples_dir, "empty_dataset.csv")
        with open(path, "rb") as f:
            res = self.client.post("/api/v1/datasets/upload", files={"file": ("empty_dataset.csv", f, "text/csv")})

        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json()["detail"].lower())

    def test_06_upload_invalid_file_rejected(self):
        path = os.path.join(self.samples_dir, "invalid_file.txt")
        with open(path, "rb") as f:
            res = self.client.post("/api/v1/datasets/upload", files={"file": ("invalid_file.txt", f, "text/plain")})

        self.assertEqual(res.status_code, 400)
        self.assertIn("unsupported", res.json()["detail"].lower())

    def test_07_dataset_list_and_delete(self):
        # 1. Upload a dedicated dataset for this test
        path = os.path.join(self.samples_dir, "clean_customers.csv")
        with open(path, "rb") as f:
            upload_res = self.client.post("/api/v1/datasets/upload", files={"file": ("to_delete.csv", f, "text/csv")})
        self.assertEqual(upload_res.status_code, 201)
        target_id = upload_res.json()["id"]

        # 2. List datasets
        res = self.client.get("/api/v1/datasets/")
        self.assertEqual(res.status_code, 200)
        datasets = res.json()
        self.assertGreater(len(datasets), 0)
        self.assertTrue(any(d["id"] == target_id for d in datasets))

        # 3. Get dataset detail
        detail_res = self.client.get(f"/api/v1/datasets/{target_id}")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["id"], target_id)

        # 4. Overview summary
        overview_res = self.client.get("/api/v1/overview/summary")
        self.assertEqual(overview_res.status_code, 200)
        self.assertGreater(overview_res.json()["total_datasets"], 0)

        # 5. Delete dataset
        del_res = self.client.delete(f"/api/v1/datasets/{target_id}")
        self.assertEqual(del_res.status_code, 200)

        # 6. Verify not found after deletion
        not_found = self.client.get(f"/api/v1/datasets/{target_id}")
        self.assertEqual(not_found.status_code, 404)

if __name__ == "__main__":
    unittest.main()
