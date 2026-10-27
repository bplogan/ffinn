"""
WebSocket connection manager for real-time AI agent progress updates.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

import structlog
from fastapi import WebSocket

log = structlog.get_logger(__name__)


class WebSocketManager:
    """Manages WebSocket connections per tenant for broadcasting progress events."""

    def __init__(self):
        # tenant_id → list of WebSocket connections
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, tenant_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[tenant_id].append(websocket)
        log.info("WS connected", tenant_id=tenant_id, total=len(self._connections[tenant_id]))

    async def post_connect(self, websocket: WebSocket, tenant_id: str) -> None:
        """Register an already-accepted WebSocket (the handler accepted it for auth)."""
        async with self._lock:
            self._connections[tenant_id].append(websocket)
        log.info("WS connected", tenant_id=tenant_id, total=len(self._connections[tenant_id]))

    async def disconnect(self, websocket: WebSocket, tenant_id: str) -> None:
        async with self._lock:
            try:
                self._connections[tenant_id].remove(websocket)
            except ValueError:
                pass

    async def broadcast_to_tenant(self, tenant_id: str, data: dict[str, Any]) -> None:
        message = json.dumps(data)
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(tenant_id, [])):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    try:
                        self._connections[tenant_id].remove(ws)
                    except ValueError:
                        pass

    async def broadcast_to_user(self, tenant_id: str, user_id: str, data: dict) -> None:
        """Send to a specific user's connections (user_id stored as a custom attribute)."""
        message = json.dumps(data)
        for ws in list(self._connections.get(tenant_id, [])):
            try:
                if getattr(ws, "_user_id", None) == user_id:
                    await ws.send_text(message)
            except Exception:
                pass


# Singleton — injected into AIAgentService
ws_manager = WebSocketManager()
