import unittest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.pipeline import (
    PipelineModel,
    PipelineMetricSnapshotModel,
    PipelineAlertModel,
    PipelineAnomalyModel,
)
from app.schemas.pipeline import (
    PipelineCreateRequest,
    PipelineUpdateRequest,
    PipelineSchemaDefinition,
    SchemaFieldDefinition,
    PipelineSummarySchema,
    PipelineDetailSchema,
    PipelineAlertSchema,
    PipelineAnomalySchema,
    PipelineMetricSnapshotSchema,
    StreamRecordIngestRequest,
)

class TestPipelineModelsAndSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_schema_field_and_pipeline_create_validation(self):
        # Valid schema definition
        valid_schema = PipelineSchemaDefinition(
            fields=[
                SchemaFieldDefinition(name="order_id", type="string", required=True),
                SchemaFieldDefinition(name="amount", type="float", required=True),
                SchemaFieldDefinition(name="user_email", type="string", required=False),
                SchemaFieldDefinition(name="created_at", type="datetime", required=False),
            ],
            strict=True,
        )
        req = PipelineCreateRequest(
            name="E-Commerce Orders Stream",
            description="Continuous ingestion of checkout orders",
            source="Kafka - orders.events",
            destination="Snowflake - prod_orders",
            schema_definition=valid_schema,
        )
        self.assertEqual(req.name, "E-Commerce Orders Stream")
        self.assertEqual(len(req.schema_definition.fields), 4)
        self.assertTrue(req.schema_definition.strict)

        # Invalid field type rejection
        with self.assertRaises(ValidationError):
            SchemaFieldDefinition(name="bad_field", type="invalid_type")

        # Empty fields list rejection
        with self.assertRaises(ValidationError):
            PipelineSchemaDefinition(fields=[])

    def test_02_pipeline_model_crud_and_defaults(self):
        schema_dict = {
            "fields": [
                {"name": "sensor_id", "type": "string", "required": True},
                {"name": "temperature", "type": "float", "required": True},
            ],
            "strict": False,
        }

        pipeline = PipelineModel(
            name="IoT Sensor Telemetry",
            description="Real-time temperature telemetry",
            source="MQTT Broker",
            destination="PostgreSQL Timeseries",
            schema_definition=schema_dict,
        )
        self.db.add(pipeline)
        self.db.commit()
        self.db.refresh(pipeline)

        # Verify defaults
        self.assertIsNotNone(pipeline.id)
        self.assertEqual(pipeline.status, "active")
        self.assertEqual(pipeline.total_records_ingested, 0)
        self.assertEqual(pipeline.total_records_processed, 0)
        self.assertEqual(pipeline.total_records_failed, 0)
        self.assertEqual(pipeline.success_rate, 100.0)
        self.assertEqual(pipeline.avg_latency_ms, 0.0)
        self.assertIsNone(pipeline.last_ingestion_at)

        # Add related metric snapshot
        snapshot = PipelineMetricSnapshotModel(
            pipeline_id=pipeline.id,
            records_in_interval=100,
            records_processed=98,
            records_failed=2,
            throughput_rps=50.0,
            avg_latency_ms=12.4,
            error_rate=2.0,
            status="active",
        )
        self.db.add(snapshot)

        # Add related alert
        alert = PipelineAlertModel(
            pipeline_id=pipeline.id,
            severity="warning",
            alert_type="high_failure_rate",
            title="Slight error rate increase",
            description="2% failure rate detected during ingestion window",
            dedup_key=f"{pipeline.id}:high_failure_rate",
        )
        self.db.add(alert)

        # Add related anomaly
        anomaly = PipelineAnomalyModel(
            pipeline_id=pipeline.id,
            column_name="temperature",
            anomaly_type="zscore_outlier",
            severity="high",
            description="Temperature spike (85.4C) exceeded 3-sigma fence",
            metric_value=85.4,
            expected_range={"mean": 24.2, "std": 3.1, "max_expected": 33.5},
        )
        self.db.add(anomaly)
        self.db.commit()
        self.db.refresh(pipeline)

        # Test relationships
        self.assertEqual(len(pipeline.metric_snapshots), 1)
        self.assertEqual(len(pipeline.alerts), 1)
        self.assertEqual(len(pipeline.anomalies), 1)
        self.assertEqual(pipeline.alerts[0].dedup_key, f"{pipeline.id}:high_failure_rate")
        self.assertEqual(pipeline.anomalies[0].column_name, "temperature")

        # Test Pydantic serialization
        detail = PipelineDetailSchema.model_validate(pipeline)
        self.assertEqual(detail.name, "IoT Sensor Telemetry")
        self.assertEqual(len(detail.metric_snapshots), 1)
        self.assertEqual(len(detail.alerts), 1)
        self.assertEqual(len(detail.anomalies), 1)

        # Test cascade delete
        pipe_id = pipeline.id
        self.db.delete(pipeline)
        self.db.commit()

        # Children should be cascade-deleted
        self.assertEqual(
            self.db.query(PipelineMetricSnapshotModel).filter_by(pipeline_id=pipe_id).count(), 0
        )
        self.assertEqual(
            self.db.query(PipelineAlertModel).filter_by(pipeline_id=pipe_id).count(), 0
        )
        self.assertEqual(
            self.db.query(PipelineAnomalyModel).filter_by(pipeline_id=pipe_id).count(), 0
        )

    def test_03_stream_ingest_request_schema(self):
        # Single record
        req1 = StreamRecordIngestRequest(record={"id": "evt-1", "val": 42})
        self.assertIsNotNone(req1.record)
        self.assertIsNone(req1.records)

        # Batch records
        req2 = StreamRecordIngestRequest(records=[{"id": "evt-1"}, {"id": "evt-2"}])
        self.assertIsNotNone(req2.records)
        self.assertEqual(len(req2.records), 2)

    def test_04_pipeline_update_schema(self):
        req = PipelineUpdateRequest(status="stopped", description="Paused for maintenance")
        self.assertEqual(req.status, "stopped")
        self.assertEqual(req.description, "Paused for maintenance")

        with self.assertRaises(ValidationError):
            PipelineUpdateRequest(status="invalid_status")

if __name__ == "__main__":
    unittest.main()
