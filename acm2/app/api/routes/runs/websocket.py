"""
WebSocket endpoint for run updates.

Provides real-time run state updates to connected clients.
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...websockets import run_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/runs/ws/run/{run_id}")
async def websocket_run_updates(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time run updates.
    Clients receive the full run state whenever it changes.
    """
    await run_ws_manager.connect(websocket, run_id)
    try:
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        run_ws_manager.disconnect(websocket, run_id)
