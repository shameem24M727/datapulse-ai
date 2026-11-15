import io
import os
import unittest
import pandas as pd
import numpy as np

from app.services.parser import sanitize_filename
from app.services.profiler import profile_dataframe
from app.services.quality_engine import compute_data_quality
from app.services.anomaly_engine import detect_anomalies
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.models.dataset import DatasetModel, ColumnProfileModel, QualityReportModel, AnomalyModel

class TestIngestionAndQualityEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("../../etc/passwd.csv"), "passwd.csv")
        self.assertEqual(sanitize_filename("C:\\Users\\admin\\file.xlsx"), "file.xlsx")
        self.assertEqual(sanitize_filename("customers; DROP TABLE--.csv"), "customers__DROP_TABLE--.csv")

    def test_profiling_and_quality_on_clean_data(self):
        # Clean synthetic dataset
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
            "score": [85.5, 90.0, 78.5, 92.0, 88.0],
            "active": [True, True, False, True, False],
        })

        profile = profile_dataframe(df)
        self.assertEqual(profile["row_count"], 5)
        self.assertEqual(profile["column_count"], 4)
        self.assertEqual(profile["duplicate_rows"], 0)

        # Quality check
        quality = compute_data_quality(df, profile)
        self.assertEqual(quality["completeness_score"], 100.0)
        self.assertEqual(quality["uniqueness_score"], 100.0)
        self.assertGreaterEqual(quality["overall_score"], 90.0)
        self.assertEqual(quality["status"], "healthy")

    def test_quality_penalties_on_dirty_data(self):
        # Dirty dataset with nulls, duplicates, and invalid entries
        df = pd.DataFrame({
            "id": [1, 2, 2, 4, 5, 6, 7, 8, 9, 10],  # 1 duplicate row
            "email": ["a@b.com", None, None, "d@b.com", "e@b.com", "f@b.com", None, "h@b.com", "i@b.com", "j@b.com"],  # 3 nulls (30%)
            "revenue": [100.0, 150.0, 150.0, 200.0, 180.0, 160.0, 190.0, 210.0, 175.0, 185.0],
        })

        profile = profile_dataframe(df)
        self.assertEqual(profile["duplicate_rows"], 1)

        quality = compute_data_quality(df, profile)
        # Completeness should reflect 3 nulls out of 30 total cells = 90%
        self.assertEqual(quality["completeness_score"], 90.0)
        # Uniqueness should reflect 1 duplicate out of 10 rows = 90%
        self.assertEqual(quality["uniqueness_score"], 90.0)
        self.assertLess(quality["overall_score"], 100.0)
        self.assertTrue(len(quality["evidence"]) >= 2)

    def test_anomaly_detection_zscore_and_iqr(self):
        # Dataset with normal distribution + 1 massive extreme outlier (10,000 when normal is ~50)
        np.random.seed(42)
        normal_values = list(np.random.normal(loc=50.0, scale=5.0, size=50))
        # Add extreme outlier
        normal_values.append(5000.0)

        df = pd.DataFrame({
            "transaction_id": list(range(1, 52)),
            "amount": normal_values,
        })

        profile = profile_dataframe(df)
        anomalies = detect_anomalies(df, profile)

        # Must detect outlier in amount
        self.assertTrue(len(anomalies) >= 1)
        amount_anomalies = [a for a in anomalies if a["column_name"] == "amount"]
        self.assertTrue(len(amount_anomalies) >= 1)
        self.assertIn("outlier", amount_anomalies[0]["anomaly_type"])
        self.assertIn("critical", amount_anomalies[0]["severity"])

    def test_database_crud_operations(self):
        db = SessionLocal()
        try:
            # Create
            dataset = DatasetModel(
                name="Test Financials",
                original_filename="financials.csv",
                file_type="csv",
                file_size_bytes=4096,
                row_count=100,
                column_count=5,
                quality_score=94.5,
                status="healthy",
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            dataset_id = dataset.id
            self.assertIsNotNone(dataset_id)

            # Add profile
            col_prof = ColumnProfileModel(
                dataset_id=dataset_id,
                column_name="profit",
                data_type="Float",
                total_count=100,
                null_count=2,
                null_percentage=2.0,
                unique_count=85,
                is_numeric=True,
                mean_value=1240.50,
            )
            db.add(col_prof)

            # Add quality report
            q_rep = QualityReportModel(
                dataset_id=dataset_id,
                overall_score=94.5,
                completeness_score=98.0,
                uniqueness_score=100.0,
                validity_score=90.0,
                consistency_score=90.0,
                total_cells=500,
                null_cells=10,
            )
            db.add(q_rep)

            # Add anomaly
            anom = AnomalyModel(
                dataset_id=dataset_id,
                column_name="profit",
                anomaly_type="zscore_outlier",
                severity="medium",
                affected_rows=1,
                description="Test outlier detected",
            )
            db.add(anom)
            db.commit()

            # Read
            retrieved = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.name, "Test Financials")
            self.assertEqual(len(retrieved.column_profiles), 1)
            self.assertIsNotNone(retrieved.quality_report)
            self.assertEqual(len(retrieved.anomalies), 1)

            # Delete cascade
            db.delete(retrieved)
            db.commit()

            # Verify deleted
            after_del = db.query(DatasetModel).filter(DatasetModel.id == dataset_id).first()
            self.assertIsNone(after_del)
            col_after_del = db.query(ColumnProfileModel).filter(ColumnProfileModel.dataset_id == dataset_id).all()
            self.assertEqual(len(col_after_del), 0)

        finally:
            db.close()

if __name__ == "__main__":
    unittest.main()
