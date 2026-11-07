from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user
from app.database import db
from app.models.schemas import MessageIn
from app.services import message_service

router = APIRouter(prefix="/api", tags=["消息与公告"])


@router.get("/messages/contacts")
def contacts(user: dict = Depends(get_current_user)):
    return message_service.get_contacts(user["id"], user["role"])


@router.get("/messages/unread")
def unread(user: dict = Depends(get_current_user)):
    return {"count": message_service.unread_total(user["id"])}


@router.get("/messages/system")
def system_messages(user: dict = Depends(get_current_user)):
    return message_service.system_messages(user["id"])


@router.get("/messages/contacts/{peer_id}")
def chat(peer_id: int, user: dict = Depends(get_current_user)):
    peer = db.query("SELECT id, nickname, avatar, role, status FROM users WHERE id = %s",
                    (peer_id,), one=True)
    if not peer:
        raise HTTPException(status_code=404, detail="联系人不存在")
    message_service.mark_read(user["id"], peer_id)
    return {
        "peer": peer,
        "messages": message_service.chat_history(user["id"], peer_id),
    }


@router.post("/messages")
def send(data: MessageIn, user: dict = Depends(get_current_user)):
    receiver = db.query("SELECT id, status FROM users WHERE id = %s",
                        (data.receiver_id,), one=True)
    if not receiver or receiver["status"] != 1:
        raise HTTPException(status_code=404, detail="接收方不存在或已禁用")
    if receiver["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="不能给自己发消息")
    allowed = False
    if user["role"] == "admin":
        allowed = True
    elif user["role"] == "coach":
        row = db.query("SELECT id FROM rehab_programs WHERE coach_id = %s AND student_id = %s",
                       (user["id"], data.receiver_id), one=True)
        allowed = bool(row)
    else:
        row = db.query("SELECT id FROM rehab_programs WHERE coach_id = %s AND student_id = %s",
                       (data.receiver_id, user["id"]), one=True)
        allowed = bool(row) or db.query(
            "SELECT id FROM messages WHERE sender_id = %s AND receiver_id = %s LIMIT 1",
            (data.receiver_id, user["id"]), one=True) is not None
    if not allowed:
        raise HTTPException(status_code=403, detail="只能与你的教练/学员对话")
    msg = message_service.send_message(user["id"], data.receiver_id,
                                       data.msg_type, data.content, data.media_path)
    return msg


@router.get("/announcements")
def announcements(user: dict = Depends(get_current_user)):
    rows = db.query(
        "SELECT id, title, content, is_pinned, publish_at FROM announcements "
        "WHERE status = 'published' AND target_role IN ('all', %s) "
        "ORDER BY is_pinned DESC, publish_at DESC LIMIT 20",
        (user["role"],))
    return [{**r, "publish_at": str(r["publish_at"])} for r in rows]
