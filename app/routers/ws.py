import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.security import decode_token
from app.database import db
from app.services import camp_service, message_service
from app.services.ws_manager import manager

logger = logging.getLogger("fitness.ws")
router = APIRouter()


async def _handle_camp_message(websocket: WebSocket, user: dict, data: dict):
    """营内群聊：校验成员资格 → 落库 → 广播给全体在营成员（含教练）。"""
    camp_id = data.get("camp_id")
    try:
        camp_id = int(camp_id)
    except (TypeError, ValueError):
        return
    camp = camp_service.get_camp(camp_id)
    if not camp or camp["status"] != "ongoing":
        await websocket.send_json({"type": "camp_error", "message": "营期不存在或未开营"})
        return
    is_coach = camp["coach_id"] == user["id"]
    if not is_coach and not camp_service.is_member(camp_id, user["id"]):
        await websocket.send_json({"type": "camp_error", "message": "你不是该训练营成员"})
        return
    msg_type = data.get("msg_type", "text")
    if msg_type not in ("text", "image", "voice", "video"):
        msg_type = "text"
    content = str(data.get("content", ""))[:2000]
    media_path = str(data.get("media_path", ""))[:255]
    if not content and not media_path:
        return
    msg = camp_service.send_camp_message(camp_id, user["id"], msg_type, content, media_path)
    await camp_service.broadcast_camp_message(
        camp_id, {"type": "camp_msg", "camp_id": camp_id, "data": msg})


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = ""):
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception:
        await websocket.close(code=4001)
        return

    user = db.query("SELECT id, nickname, role, status FROM users WHERE id = %s",
                    (user_id,), one=True)
    if not user or user["status"] != 1:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    manager.connect(user_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "user": {"id": user_id,
                                                                 "nickname": user["nickname"]}})
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "camp":
                await _handle_camp_message(websocket, user, data)
                continue
            msg_type = data.get("type", "text")
            if msg_type not in ("text", "image", "voice", "video"):
                msg_type = "text"
            receiver_id = data.get("to")
            content = str(data.get("content", ""))[:2000]
            media_path = str(data.get("media_path", ""))
            if not receiver_id or not content:
                continue
            receiver = db.query("SELECT id, status FROM users WHERE id = %s",
                                (receiver_id,), one=True)
            if not receiver or receiver["status"] != 1:
                await websocket.send_json({"type": "error", "message": "接收方不存在或已禁用"})
                continue
            message_service.send_message(user_id, receiver_id, msg_type, content, media_path)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.info("WS 异常 user=%s: %s", user_id, exc)
    finally:
        manager.disconnect(user_id)
