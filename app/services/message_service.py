from app.database import db
from app.models.schemas import BatchMessageIn
from app.services.ws_manager import notify


def _user_brief(user_id: int) -> dict:
    return db.query("SELECT id, nickname, avatar, role FROM users WHERE id = %s",
                    (user_id,), one=True) or {"id": user_id, "nickname": "已注销用户", "avatar": "", "role": "student"}


def send_message(sender_id: int | None, receiver_id: int, msg_type: str = "text",
                 content: str = "", media_path: str = "") -> dict:
    message_id = db.insert(
        "INSERT INTO messages (sender_id, receiver_id, msg_type, content, media_path) "
        "VALUES (%s,%s,%s,%s,%s)",
        (sender_id, receiver_id, msg_type, content, media_path))
    msg = db.query("SELECT * FROM messages WHERE id = %s", (message_id,), one=True)
    payload = {**msg, "created_at": str(msg["created_at"])}
    if sender_id:
        sender = _user_brief(sender_id)
        payload["sender_nickname"] = sender["nickname"]
        payload["sender_avatar"] = sender["avatar"]
        notify(receiver_id, {"type": "message", "data": payload})
    return payload


def system_notify(receiver_id: int, content: str) -> None:
    """sender 为 NULL 的系统通知，同时推送 WS。"""
    send_message(None, receiver_id, "system", content)
    notify(receiver_id, {"type": "notification", "message": content})


def get_contacts(user_id: int, role: str) -> list:
    """学员的联系人 = 相关教练；教练的联系人 = 名下学员。"""
    if role == "student":
        rows = db.query(
            "SELECT DISTINCT u.id, u.nickname, u.avatar, u.role FROM users u "
            "JOIN rehab_programs p ON p.coach_id = u.id WHERE p.student_id = %s",
            (user_id,))
    else:
        rows = db.query(
            "SELECT DISTINCT u.id, u.nickname, u.avatar, u.role FROM users u "
            "JOIN rehab_programs p ON p.student_id = u.id WHERE p.coach_id = %s",
            (user_id,))
    contacts = []
    for r in rows:
        last = db.query(
            "SELECT content, msg_type, created_at, sender_id FROM messages "
            "WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s) "
            "ORDER BY id DESC LIMIT 1",
            (user_id, r["id"], r["id"], user_id), one=True)
        unread = db.query(
            "SELECT COUNT(*) AS cnt FROM messages WHERE sender_id = %s AND receiver_id = %s AND is_read = 0",
            (r["id"], user_id), one=True)["cnt"]
        contacts.append({
            "id": r["id"], "nickname": r["nickname"], "avatar": r["avatar"], "role": r["role"],
            "unread": unread,
            "last_message": (last["content"][:30] if last else ""),
            "last_time": str(last["created_at"]) if last else "",
        })
    return contacts


def chat_history(user_id: int, peer_id: int, limit: int = 200) -> list:
    rows = db.query(
        "SELECT m.*, s.nickname AS sender_nickname, s.avatar AS sender_avatar "
        "FROM messages m LEFT JOIN users s ON s.id = m.sender_id "
        "WHERE (m.sender_id = %s AND m.receiver_id = %s) OR (m.sender_id = %s AND m.receiver_id = %s) "
        "ORDER BY m.id DESC LIMIT %s",
        (user_id, peer_id, peer_id, user_id, limit))
    return [{**r, "created_at": str(r["created_at"])} for r in reversed(rows)]


def mark_read(user_id: int, peer_id: int) -> None:
    db.execute(
        "UPDATE messages SET is_read = 1 WHERE sender_id = %s AND receiver_id = %s AND is_read = 0",
        (peer_id, user_id))


def unread_total(user_id: int) -> int:
    row = db.query("SELECT COUNT(*) AS cnt FROM messages WHERE receiver_id = %s AND is_read = 0",
                   (user_id,), one=True)
    return row["cnt"]


def system_messages(user_id: int, limit: int = 50) -> list:
    rows = db.query(
        "SELECT * FROM messages WHERE receiver_id = %s AND msg_type = 'system' "
        "ORDER BY id DESC LIMIT %s", (user_id, limit))
    return [{**r, "created_at": str(r["created_at"])} for r in rows]


def batch_send(coach_id: int, data: BatchMessageIn) -> int:
    if data.target == "student_ids" and not data.student_ids:
        raise ValueError("请选择接收学员")
    if data.target == "all":
        from app.services.plan_service import coach_student_ids
        student_ids = coach_student_ids(coach_id)
    else:
        student_ids = data.student_ids
    for sid in student_ids:
        send_message(coach_id, sid, data.msg_type, data.content, data.media_path)
    return len(student_ids)
