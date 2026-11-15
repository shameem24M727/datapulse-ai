import json
import asyncio
import logging
from typing import Dict, Set, Any, Optional, Tuple
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("datapulse.websocket")

class WebSocketConnectionManager:
    """
    Manages active WebSocket connections per pipeline.
    Tracks each connection along with its originating event loop,
    ensuring 100% reliable cross-thread and async broadcasting.
    """
    def __init__(self, max_connections_per_pipeline: int = 50, max_total_connections: int = 200):
        # Maps pipeline_id -> Set of (WebSocket, AbstractEventLoop)
        self._connections: Dict[str, Set[Tuple[WebSocket, asyncio.AbstractEventLoop]]] = {}
        self._max_per_pipeline = max_connections_per_pipeline
        self._max_total = max_total_connections
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Stores the primary server event loop."""
        self._main_loop = loop

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())

    async def connect(self, pipeline_id: str, websocket: WebSocket) -> bool:
        """Accepts a WebSocket connection and registers it with its active event loop."""
        if self.total_connections >= self._max_total:
            await websocket.close(code=1008, reason="Server connection limit reached")
            return False

        if pipeline_id not in self._connections:
            self._connections[pipeline_id] = set()

        if len(self._connections[pipeline_id]) >= self._max_per_pipeline:
            await websocket.close(code=1008, reason="Pipeline connection limit reached")
            return False

        await websocket.accept()
        current_loop = asyncio.get_running_loop()
        self._connections[pipeline_id].add((websocket, current_loop))
        if self._main_loop is None:
            self._main_loop = current_loop

        logger.info(f"WebSocket client connected to pipeline {pipeline_id} (active: {len(self._connections[pipeline_id])})")
        return True

    def disconnect(self, pipeline_id: str, websocket: WebSocket):
        """Removes a disconnected client."""
        if pipeline_id in self._connections:
            self._connections[pipeline_id] = {
                (ws, loop) for (ws, loop) in self._connections[pipeline_id] if ws != websocket
            }
            if not self._connections[pipeline_id]:
                del self._connections[pipeline_id]
        logger.info(f"WebSocket client disconnected from pipeline {pipeline_id}")

    async def broadcast_to_pipeline(self, pipeline_id: str, message: Dict[str, Any]):
        """Asynchronously broadcasts a JSON message to all clients on this loop."""
        conns = list(self._connections.get(pipeline_id, set()))
        if not conns:
            return

        payload_str = json.dumps(message, default=str)
        dead_sockets = []

        for ws, loop in conns:
            try:
                await ws.send_text(payload_str)
            except Exception as exc:
                logger.debug(f"Failed to send to client on {pipeline_id}: {exc}")
                dead_sockets.append(ws)

        for dead_ws in dead_sockets:
            self.disconnect(pipeline_id, dead_ws)

    def broadcast_sync(self, pipeline_id: str, message: Dict[str, Any]):
        """
        Thread-safe broadcast helper: schedules `ws.send_text` directly on each socket's
        event loop. Works seamlessly whether called from an async route, a synchronous
        endpoint, or a background worker thread.
        """
        conns = list(self._connections.get(pipeline_id, set()))
        if not conns:
            return

        payload_str = json.dumps(message, default=str)
        dead_sockets = []

        for ws, loop in conns:
            try:
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(ws.send_text(payload_str), loop)
                else:
                    dead_sockets.append(ws)
            except Exception as e:
                logger.debug(f"Broadcast error on socket {pipeline_id}: {e}")
                dead_sockets.append(ws)

        for dead_ws in dead_sockets:
            self.disconnect(pipeline_id, dead_ws)

websocket_manager = WebSocketConnectionManager()
