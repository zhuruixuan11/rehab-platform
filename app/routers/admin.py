from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.deps import get_current_user, require_role
from app.auth.security import hash_password
from app.database import db
from app.models.schemas import (AnnouncementIn, CoachReviewIn, ConfigUpdateIn,
                                ResetPasswordIn, UserRoleIn, UserStatusIn)
from app.services import stats_service
from app.services.message_service import system_notify
from app.utils.helpers import clamp_page, log_operation, parse_date

router = APIRouter(prefix="/api/admin", tags=["管理员端"],
                   dependencies=[Depends(require_role("admin"))])


# ---------------- 用户管理 ----------------
@router.get("/users")
def users(role: str = None, q: str = None, status: int = None,
          page: int = 1, page_size: int = 20, user: dict = Depends(get_current_user)):
    where, params = ["1=1"], []
    if role:
        where.append("u.role = %s")
        params.append(role)
    if status is not None:
        where.append("u.status = %s")
        params.append(status)
    if q:
        where.append("(u.username LIKE %s OR u.nickname LIKE %s OR u.phone LIKE %s)")
        params.extend([f"%{q}%"] * 3)
    cond = " AND ".join(where)
    total = db.query(f"SELECT COUNT(*) AS cnt FROM users u WHERE {cond}",
                     tuple(params), one=True)["cnt"]
    offset, size = clamp_page(page, page_size)
    rows = db.query(
        f"SELECT u.id, u.username, u.nickname, u.role, u.phone, u.gender, u.avatar, "
        f"u.reminder_time, u.current_streak, u.longest_streak, u.status, "
        f"u.created_at, u.last_login_at, "
        f"(SELECT COUNT(*) FROM rehab_logs c WHERE c.user_id = u.id) AS checkin_count, "
        f"(SELECT MAX(c.checkin_date) FROM rehab_logs c WHERE c.user_id = u.id) AS last_checkin "
        f"FROM users u WHERE {cond} ORDER BY u.created_at DESC LIMIT %s OFFSET %s",
        tuple(params) + (size, offset))
    return {"total": total, "items": [
        {**r, "created_at": str(r["created_at"]),
         "last_login_at": str(r["last_login_at"]) if r["last_login_at"] else None,
         "last_checkin": r["last_checkin"].isoformat() if r["last_checkin"] else None,
         "reminder_time": str(r["reminder_time"]) if r["reminder_time"] else None}
        for r in rows]}


@router.put("/users/{user_id}/status")
def set_user_status(user_id: int, data: UserStatusIn, request: Request,
                    user: dict = Depends(get_current_user)):
    target = db.query("SELECT id, role, nickname FROM users WHERE id = %s", (user_id,), one=True)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="不能操作自己的账号")
    if data.status not in (0, 1):
        raise HTTPException(status_code=400, detail="状态参数不合法")
    db.execute("UPDATE users SET status = %s WHERE id = %s", (data.status, user_id))
    log_operation(user["id"], "用户管理", "启用账号" if data.status == 1 else "禁用账号",
                  f"用户 {target['nickname']}(id={user_id})", request.client.host)
    return {"ok": True}


@router.put("/users/{user_id}/role")
def set_user_role(user_id: int, data: UserRoleIn, request: Request,
                  user: dict = Depends(get_current_user)):
    target = db.query("SELECT id, role, nickname FROM users WHERE id = %s", (user_id,), one=True)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    db.execute("UPDATE users SET role = %s WHERE id = %s", (data.role, user_id))
    if data.role == "coach":
        db.execute(
            "INSERT INTO therapist_profiles (user_id, review_status) VALUES (%s,'approved') "
            "ON DUPLICATE KEY UPDATE review_status = 'approved'",
            (user_id,))
    log_operation(user["id"], "用户管理", "角色调整",
                  f"{target['nickname']}(id={user_id}) -> {data.role}", request.client.host)
    return {"ok": True}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, data: ResetPasswordIn, request: Request,
                   user: dict = Depends(get_current_user)):
    target = db.query("SELECT id, nickname FROM users WHERE id = %s", (user_id,), one=True)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.execute("UPDATE users SET password_hash = %s WHERE id = %s",
               (hash_password(data.new_password), user_id))
    system_notify(user_id, "管理员已重置你的密码，请及时登录并修改。")
    log_operation(user["id"], "用户管理", "重置密码", f"用户 {target['nickname']}(id={user_id})",
                  request.client.host)
    return {"ok": True}


# ---------------- 教练审核 ----------------
@router.get("/coach-reviews")
def coach_reviews(status: str = None, user: dict = Depends(get_current_user)):
    sql = ("SELECT p.*, u.username, u.nickname, u.avatar, u.created_at AS register_at "
           "FROM therapist_profiles p JOIN users u ON u.id = p.user_id")
    params = []
    if status:
        sql += " WHERE p.review_status = %s"
        params.append(status)
    sql += " ORDER BY p.review_status = 'pending' DESC, p.created_at DESC LIMIT 200"
    rows = db.query(sql, tuple(params))
    return [{**r, "created_at": str(r["created_at"]),
             "register_at": str(r["register_at"]),
             "reviewed_at": str(r["reviewed_at"]) if r["reviewed_at"] else None} for r in rows]


@router.post("/coach-reviews/{user_id}/review")
def review_coach(user_id: int, data: CoachReviewIn, request: Request,
                 user: dict = Depends(get_current_user)):
    profile = db.query("SELECT * FROM therapist_profiles WHERE user_id = %s", (user_id,), one=True)
    if not profile:
        raise HTTPException(status_code=404, detail="教练档案不存在")
    if profile["review_status"] == "approved" and not data.approve:
        data.review_note = data.review_note or "撤销认证"
    new_status = "approved" if data.approve else "rejected"
    db.execute(
        "UPDATE therapist_profiles SET review_status = %s, review_note = %s, reviewed_by = %s, "
        "reviewed_at = NOW() WHERE user_id = %s",
        (new_status, data.review_note, user["id"], user_id))
    if data.approve:
        system_notify(user_id, "恭喜！你的教练资质审核已通过，已获得平台认证标识。")
    else:
        system_notify(user_id, f"你的教练资质审核未通过。原因：{data.review_note or '资料不完整'}")
    log_operation(user["id"], "教练审核", "通过认证" if data.approve else "驳回认证",
                  f"教练 user_id={user_id}", request.client.host)
    return {"ok": True}


# ---------------- 内容管理 ----------------
@router.get("/announcements")
def announcements(user: dict = Depends(get_current_user)):
    rows = db.query("SELECT a.*, u.nickname AS creator FROM announcements a "
                    "LEFT JOIN users u ON u.id = a.created_by "
                    "ORDER BY a.is_pinned DESC, a.publish_at DESC")
    return [{**r, "publish_at": str(r["publish_at"]),
             "created_at": str(r["created_at"])} for r in rows]


@router.post("/announcements")
def create_announcement(data: AnnouncementIn, request: Request,
                        user: dict = Depends(get_current_user)):
    ann_id = db.insert(
        "INSERT INTO announcements (title, content, is_pinned, status, target_role, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (data.title, data.content, data.is_pinned, data.status, data.target_role, user["id"]))
    if data.status == "published":
        targets = db.query("SELECT id FROM users WHERE status = 1 AND role = %s",
                           (data.target_role,)) if data.target_role != "all" else \
            db.query("SELECT id FROM users WHERE status = 1")
        for t in targets:
            system_notify(t["id"], f"【公告】{data.title}")
    log_operation(user["id"], "内容管理", "发布公告", f"title={data.title}", request.client.host)
    return {"id": ann_id}


@router.put("/announcements/{ann_id}")
def update_announcement(ann_id: int, data: AnnouncementIn, request: Request,
                        user: dict = Depends(get_current_user)):
    row = db.query("SELECT id FROM announcements WHERE id = %s", (ann_id,), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="公告不存在")
    db.execute(
        "UPDATE announcements SET title=%s, content=%s, is_pinned=%s, status=%s, target_role=%s "
        "WHERE id=%s",
        (data.title, data.content, data.is_pinned, data.status, data.target_role, ann_id))
    log_operation(user["id"], "内容管理", "编辑公告", f"ann_id={ann_id}", request.client.host)
    return {"ok": True}


@router.delete("/announcements/{ann_id}")
def delete_announcement(ann_id: int, request: Request, user: dict = Depends(get_current_user)):
    db.execute("DELETE FROM announcements WHERE id = %s", (ann_id,))
    log_operation(user["id"], "内容管理", "删除公告", f"ann_id={ann_id}", request.client.host)
    return {"ok": True}


@router.get("/plans")
def all_plans(q: str = None, user: dict = Depends(get_current_user)):
    """计划分配总览：只读展示各教练给学员布置的计划。"""
    sql = ("SELECT p.*, s.nickname AS student_name, c.nickname AS coach_name, "
           "(SELECT COUNT(*) FROM program_items pi WHERE pi.plan_id = p.id) AS item_count "
           "FROM rehab_programs p JOIN users s ON s.id = p.student_id "
           "JOIN users c ON c.id = p.coach_id")
    params = []
    if q:
        sql += " WHERE p.title LIKE %s"
        params.append(f"%{q}%")
    sql += " ORDER BY p.created_at DESC LIMIT 200"
    rows = db.query(sql, tuple(params))
    return [{**r, "start_date": r["start_date"].isoformat(), "end_date": r["end_date"].isoformat(),
             "created_at": str(r["created_at"])} for r in rows]


# ---------------- 数据统计 ----------------
@router.get("/stats/overview")
def stats_overview(user: dict = Depends(get_current_user)):
    return stats_service.admin_overview()


@router.get("/stats/trend")
def stats_trend(days: int = 30, user: dict = Depends(get_current_user)):
    days = min(max(days, 7), 90)
    return stats_service.admin_trend(days)


@router.get("/stats/checkins")
def stats_checkins(day: str = None, page: int = 1, page_size: int = 20,
                   user: dict = Depends(get_current_user)):
    """某日打卡明细（看板下钻用），默认今天。"""
    from datetime import date as date_cls
    d = parse_date(day) if day else date_cls.today()
    offset, size = clamp_page(page, page_size)
    total = db.query("SELECT COUNT(*) AS cnt FROM rehab_logs WHERE checkin_date = %s",
                     (d,), one=True)["cnt"]
    rows = db.query(
        "SELECT c.id, c.checkin_date, c.content, c.train_volume, c.duration_min, c.intensity, "
        "c.is_makeup, u.id AS user_id, u.nickname, u.role "
        "FROM rehab_logs c JOIN users u ON u.id = c.user_id "
        "WHERE c.checkin_date = %s ORDER BY c.train_volume DESC LIMIT %s OFFSET %s",
        (d, size, offset))
    return {"date": d.isoformat(), "total": total,
            "items": [{**r, "checkin_date": r["checkin_date"].isoformat()} for r in rows]}


@router.get("/stats/active-users")
def stats_active_users(days: int = 30, limit: int = 50,
                       user: dict = Depends(get_current_user)):
    """近 N 天有打卡记录的活跃用户（看板下钻用）。"""
    from datetime import date as date_cls
    from datetime import timedelta
    days = min(max(days, 1), 90)
    since = date_cls.today() - timedelta(days=days - 1)
    rows = db.query(
        "SELECT u.id, u.nickname, u.role, u.current_streak, "
        "MAX(c.checkin_date) AS last_checkin, COUNT(c.id) AS checkin_days "
        "FROM rehab_logs c JOIN users u ON u.id = c.user_id "
        "WHERE c.checkin_date >= %s GROUP BY u.id, u.nickname, u.role, u.current_streak "
        "ORDER BY checkin_days DESC LIMIT %s",
        (since, min(max(limit, 1), 200)))
    return {"days": days,
            "items": [{**r, "last_checkin": r["last_checkin"].isoformat()} for r in rows]}


@router.get("/stats/messages")
def stats_messages(page: int = 1, page_size: int = 15, user: dict = Depends(get_current_user)):
    """近30天消息明细（看板下钻用），含聊天与系统通知。"""
    offset, size = clamp_page(page, page_size)
    total = db.query(
        "SELECT COUNT(*) AS cnt FROM messages WHERE created_at >= NOW() - INTERVAL 30 DAY",
        one=True)["cnt"]
    rows = db.query(
        "SELECT m.id, m.msg_type, m.content, m.created_at, m.is_read, "
        "su.nickname AS sender_name, su.role AS sender_role, "
        "ru.nickname AS receiver_name, ru.role AS receiver_role "
        "FROM messages m "
        "LEFT JOIN users su ON su.id = m.sender_id "
        "LEFT JOIN users ru ON ru.id = m.receiver_id "
        "WHERE m.created_at >= NOW() - INTERVAL 30 DAY "
        "ORDER BY m.created_at DESC LIMIT %s OFFSET %s",
        (size, offset))
    return {"total": total,
            "items": [{**r, "created_at": str(r["created_at"])} for r in rows]}


# ---------------- 系统配置 ----------------
@router.get("/configs")
def configs(user: dict = Depends(get_current_user)):
    return db.query("SELECT * FROM system_configs ORDER BY config_key")


@router.put("/configs")
def update_configs(data: ConfigUpdateIn, request: Request, user: dict = Depends(get_current_user)):
    for key, value in data.configs.items():
        row = db.query("SELECT config_key FROM system_configs WHERE config_key = %s", (key,), one=True)
        if not row:
            raise HTTPException(status_code=400, detail=f"未知配置项 {key}")
        db.execute("UPDATE system_configs SET config_value = %s WHERE config_key = %s",
                   (str(value), key))
    log_operation(user["id"], "系统配置", "修改配置", str(data.configs), request.client.host)
    return {"ok": True}


@router.get("/logs")
def logs(module: str = None, admin: str = None, page: int = 1, page_size: int = 20,
         user: dict = Depends(get_current_user)):
    where, params = ["1=1"], []
    if module:
        where.append("l.module = %s")
        params.append(module)
    if admin:
        where.append("u.nickname LIKE %s")
        params.append(f"%{admin}%")
    cond = " AND ".join(where)
    total = db.query(
        f"SELECT COUNT(*) AS cnt FROM operation_logs l LEFT JOIN users u ON u.id = l.admin_id "
        f"WHERE {cond}", tuple(params), one=True)["cnt"]
    offset, size = clamp_page(page, page_size)
    rows = db.query(
        f"SELECT l.*, u.nickname AS admin_name FROM operation_logs l "
        f"LEFT JOIN users u ON u.id = l.admin_id WHERE {cond} "
        f"ORDER BY l.created_at DESC LIMIT %s OFFSET %s",
        tuple(params) + (size, offset))
    return {"total": total, "items": [
        {**r, "created_at": str(r["created_at"])} for r in rows]}
