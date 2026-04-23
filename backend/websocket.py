"""WebSocket price broadcaster.

FastAPI exposes /ws/prices. When a new futures price lands, all connected
clients receive a JSON message.

Usage in main.py:
    from backend.websocket import router as ws_router, on_new_price
    app.include_router(ws_router)
    futures_feed.register_price_callback(on_new_price)
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = structlog.get_logger(__name__)

router = APIRouter()
_connections: set[WebSocket] = set()


@router.websocket("/ws/prices")
async def prices_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _connections.add(websocket)
    log.info("ws_client_connected", total=len(_connections))
    try:
        while True:
            # Keep connection alive; we push data via on_new_price.
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections.discard(websocket)
        log.info("ws_client_disconnected", total=len(_connections))


async def on_new_price(symbol: str, row: dict[str, Any]) -> None:
    """Called by futures_feed after each successful write."""
    if not _connections:
        return
    payload = json.dumps({"symbol": symbol, **row})
    dead: set[WebSocket] = set()
    for ws in _connections:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)
