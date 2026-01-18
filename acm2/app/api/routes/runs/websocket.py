"""
WebSocket endpoint for run updates.

Provides real-time run state updates to connected clients.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.middleware import get_current_user
from ...websockets import run_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


async def authenticate_websocket(websocket: WebSocket, api_key: Optional[str]) -> bool:
    """Authenticate WebSocket connection via API key query parameter."""
    if not api_key:
        await websocket.close(code=4001, reason="Missing API key")
        return False
    
    try:
        user = await get_current_user(api_key)
        if not user:
            await websocket.close(code=4001, reason="Invalid API key")
            return False
        return True
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return False


@router.websocket("/runs/ws/run/{run_id}")
async def websocket_run_updates(
    websocket: WebSocket, 
    run_id: str,
    api_key: Optional[str] = Query(None, description="API key for authentication"),
):
    """
    WebSocket endpoint for real-time run updates.
    Clients receive the full run state whenever it changes.
    
    Authentication is required via 'api_key' query parameter.
    Example: ws://host/runs/ws/run/{run_id}?api_key=<your_api_key>
    """
    # Authenticate before accepting the connection
    if not await authenticate_websocket(websocket, api_key):
        return
    
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
