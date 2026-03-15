"""WebSocket connection manager for real-time positions and chat."""
import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per hunt. Broadcasts positions and chat."""

    def __init__(self):
        self._hunt_connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        hunt_id: int,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            if hunt_id not in self._hunt_connections:
                self._hunt_connections[hunt_id] = set()
            self._hunt_connections[hunt_id].add(websocket)
        logger.debug("WebSocket connected for hunt %s", hunt_id)

    async def disconnect(self, hunt_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            if hunt_id in self._hunt_connections:
                self._hunt_connections[hunt_id].discard(websocket)
                if not self._hunt_connections[hunt_id]:
                    del self._hunt_connections[hunt_id]
        try:
            await websocket.close()
        except Exception:
            pass
        logger.debug("WebSocket disconnected for hunt %s", hunt_id)

    async def broadcast_position(self, hunt_id: int, position: dict[str, Any]) -> None:
        """Broadcast position to all clients subscribed to this hunt."""
        await self._broadcast(hunt_id, {"type": "position", "data": position})

    async def broadcast_to_hunts(
        self,
        hunt_ids: list[int],
        message_type: str,
        data: dict[str, Any],
    ) -> None:
        """Broadcast to all clients in any of these hunts (e.g. chat to team's hunts)."""
        msg = {"type": message_type, "data": data}
        seen: set[WebSocket] = set()
        for hunt_id in hunt_ids:
            async with self._lock:
                connections = self._hunt_connections.get(hunt_id, set()).copy()
            dead = []
            for ws in connections:
                if ws in seen:
                    continue
                seen.add(ws)
                try:
                    await ws.send_text(json.dumps(msg))
                except Exception:
                    dead.append(ws)
            if dead:
                async with self._lock:
                    for ws in dead:
                        self._hunt_connections.get(hunt_id, set()).discard(ws)

    async def _broadcast(self, hunt_id: int, message: dict) -> None:
        msg = json.dumps(message)
        async with self._lock:
            connections = self._hunt_connections.get(hunt_id, set()).copy()
        dead = []
        for ws in connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._hunt_connections.get(hunt_id, set()).discard(ws)


# Global instance - populated at startup
manager = ConnectionManager()
