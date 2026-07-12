import json
import logging

from fastapi import WebSocket

logger = logging.getLogger("jenkins-incident-api.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        if not self._connections:
            return
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


manager = ConnectionManager()