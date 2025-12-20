from typing import Dict, List
from fastapi import WebSocket
from ..utils.json_utils import serialize_for_ws
import logging

logger = logging.getLogger(__name__)


class RunConnectionManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        if run_id not in self.connections:
            self.connections[run_id] = []
        self.connections[run_id].append(websocket)
        logger.info(f"[WS] Client connected to run {run_id}. Total connections for this run: {len(self.connections[run_id])}")

    def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        if run_id in self.connections:
            self.connections[run_id] = [ws for ws in self.connections[run_id] if ws != websocket]
            logger.info(f"[WS] Client disconnected from run {run_id}. Remaining: {len(self.connections[run_id])}")

    async def broadcast(self, run_id: str, message: dict) -> None:
        conns = self.connections.get(run_id, [])
        logger.info(f"[WS] Broadcasting to run {run_id}: {len(conns)} connections. Event: {message.get('event', 'unknown')}")
        if conns:
            for ws in conns:
                try:
                    await ws.send_json(serialize_for_ws(message))
                    logger.debug(f"[WS] Sent message to client for run {run_id}")
                except Exception as e:
                    logger.warning(f"[WS] Failed to send to client: {e}")

run_ws_manager = RunConnectionManager()
