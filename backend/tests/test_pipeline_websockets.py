import json
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.db.init_db import init_db
from app.services.websocket_manager import websocket_manager
from tests.test_helpers import get_admin_headers, get_admin_token

class TestPipelineWebSockets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app, headers=get_admin_headers())
        cls.token = get_admin_token()

    def setUp(self):
        schema_def = {
            "fields": [
                {"name": "event_id", "type": "string", "required": True},
                {"name": "latency", "type": "float", "required": True},
            ],
            "strict": False,
        }
        res = self.client.post(
            "/api/v1/pipelines/",
            json={
                "name": "WS Test Stream",
                "description": "WebSocket integration stream",
                "source": "WS Client",
                "destination": "Dashboard",
                "schema_definition": schema_def,
            },
        )
        assert res.status_code == 201, res.text
        self.pipeline_id = res.json()["id"]

    def tearDown(self):
        self.client.delete(f"/api/v1/pipelines/{self.pipeline_id}")

    def test_01_websocket_connect_and_initial_state(self):
        with self.client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws?token={self.token}") as ws:
            raw_data = ws.receive_text()
            packet = json.loads(raw_data)
            self.assertEqual(packet["type"], "initial_state")
            self.assertEqual(packet["pipeline_id"], self.pipeline_id)
            self.assertEqual(packet["pipeline"]["name"], "WS Test Stream")
            self.assertEqual(packet["pipeline"]["status"], "active")
            self.assertIn("recent_snapshots", packet)
            self.assertIn("recent_anomalies", packet)

    def test_02_websocket_heartbeat_ping_pong(self):
        with self.client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws?token={self.token}") as ws:
            ws.receive_text()  # Drain initial state

            # Send ping
            ws.send_text(json.dumps({"type": "ping"}))
            reply = json.loads(ws.receive_text())
            self.assertEqual(reply["type"], "pong")
            self.assertIn("timestamp", reply)

    def test_03_websocket_live_telemetry_broadcast(self):
        with self.client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws?token={self.token}") as ws:
            ws.receive_text()  # Drain initial state

            # Broadcast telemetry update to connected pipeline subscribers
            websocket_manager.broadcast_sync(
                self.pipeline_id,
                {
                    "type": "telemetry_update",
                    "pipeline_id": self.pipeline_id,
                    "batch_summary": {"records_received": 3, "records_accepted": 3, "records_rejected": 0},
                    "pipeline": {"total_records_ingested": 3, "total_records_processed": 3},
                    "latest_snapshot": {"throughput_rps": 15.0, "avg_latency_ms": 2.1},
                },
            )

            msg_text = ws.receive_text()
            packet = json.loads(msg_text)
            self.assertEqual(packet["type"], "telemetry_update")
            self.assertEqual(packet["pipeline_id"], self.pipeline_id)
            self.assertEqual(packet["batch_summary"]["records_received"], 3)
            self.assertEqual(packet["pipeline"]["total_records_ingested"], 3)
            self.assertEqual(packet["pipeline"]["total_records_processed"], 3)
            self.assertEqual(packet["latest_snapshot"]["throughput_rps"], 15.0)

    def test_04_websocket_status_change_broadcast(self):
        with self.client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws?token={self.token}") as ws:
            ws.receive_text()  # Drain initial state

            # Broadcast status change to connected subscribers
            websocket_manager.broadcast_sync(
                self.pipeline_id,
                {
                    "type": "status_change",
                    "pipeline_id": self.pipeline_id,
                    "status": "stopped",
                },
            )

            msg_text = ws.receive_text()
            packet = json.loads(msg_text)
            self.assertEqual(packet["type"], "status_change")
            self.assertEqual(packet["pipeline_id"], self.pipeline_id)
            self.assertEqual(packet["status"], "stopped")

    def test_05_websocket_unknown_pipeline_rejection(self):
        # Connecting to a non-existent pipeline should fail / close immediately
        with self.assertRaises(Exception):
            with self.client.websocket_connect(f"/api/v1/pipelines/non-existent-pipe-id/ws?token={self.token}") as ws:
                ws.receive_text()

    def test_06_websocket_missing_token_rejection(self):
        # Connecting without token or auth header must be rejected with close code 4001
        unauthed_client = TestClient(app)
        with self.assertRaises(Exception):
            with unauthed_client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws") as ws:
                ws.receive_text()

    def test_07_websocket_multiple_clients(self):
        # Verify multiple clients can connect and receive broadcasts
        with self.client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws?token={self.token}") as ws1:
            ws1.receive_text()  # Drain initial state 1
            with self.client.websocket_connect(f"/api/v1/pipelines/{self.pipeline_id}/ws?token={self.token}") as ws2:
                ws2.receive_text()  # Drain initial state 2

                # Broadcast to both clients
                websocket_manager.broadcast_sync(
                    self.pipeline_id,
                    {"type": "telemetry_update", "pipeline_id": self.pipeline_id, "msg": "hello-multi"},
                )

                pkt1 = json.loads(ws1.receive_text())
                pkt2 = json.loads(ws2.receive_text())
                self.assertEqual(pkt1["msg"], "hello-multi")
                self.assertEqual(pkt2["msg"], "hello-multi")

if __name__ == "__main__":
    unittest.main()
