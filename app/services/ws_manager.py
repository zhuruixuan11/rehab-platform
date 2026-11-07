import asyncio
import logging

logger = logging.getLogger("fitness.ws")


class ConnectionManager:
    """WebSocket 连接管理：user_id -> websocket"""

    def __init__(self):
        self._connections: dict[int, "websockets"] = {}

    def connect(self, user_id: int, websocket):
        self._connections[user_id] = websocket

    def disconnect(self, user_id: int):
        self._connections.pop(user_id, None)

    def is_online(self, user_id: int) -> bool:
        return user_id in self._connections

    async def send_to_user(self, user_id: int, payload: dict) -> bool:
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(payload)
            return True
        except Exception as exc:
            logger.info("WS 推送失败 user=%s: %s", user_id, exc)
            self.disconnect(user_id)
            return False

    async def broadcast(self, payload: dict, role: str = None):
        for user_id, ws in list(self._connections.items()):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(user_id)


manager = ConnectionManager()


def notify(user_id: int, payload: dict):
    """供同步代码调用的非阻塞推送（fire-and-forget）。"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.send_to_user(user_id, payload))
    except RuntimeError:
        pass
