import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth.deps import get_current_user, require_role
from app.database import db
from app.models.schemas import (CheckinCommentIn, ExerciseIn, MakeupReviewIn, PlanIn,
                                TemplateIn, UrgeIn, BatchMessageIn)
from app.services import message_service, plan_service, stats_service
from app.services.checkin_service import apply_makeup, get_checkin_detail
from app.services.message_service import send_message
from app.utils.helpers import parse_date

router = APIRouter(prefix="/api/coach", tags=["教练端"],
                   dependencies=[Depends(require_role("coach"))])


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    return stats_service.coach_dashboard(user["id"])


# ---------------- 学员管理 ----------------
@router.get("/students")
def students(filter_status: str = None, user: dict = Depends(get_current_user)):
    if filter_status and filter_status not in ("checked", "unchecked", "low"):
        raise HTTPException(status_code=400, detail="筛选参数不合法")
    return stats_service.coach_students(user["id"], filter_status)


@router.get("/all-students")
def all_students(q: str = None, user: dict = Depends(get_current_user)):
    """全部可选学员（含尚未建立关联的新学员），供制定训练计划时选择。"""
    sql = ("SELECT u.id, u.nickname, u.avatar, u.phone, u.current_streak, u.longest_streak, "
           "(SELECT weight FROM body_records br WHERE br.user_id = u.id AND br.weight IS NOT NULL "
           "ORDER BY record_date DESC LIMIT 1) AS latest_weight, "
           "(SELECT body_fat FROM body_records br WHERE br.user_id = u.id AND br.body_fat IS NOT NULL "
           "ORDER BY record_date DESC LIMIT 1) AS latest_body_fat "
           "FROM users u WHERE u.role = 'student' AND u.status = 1")
    params = []
    if q:
        sql += " AND (u.nickname LIKE %s OR u.username LIKE %s OR u.phone LIKE %s)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY u.current_streak DESC LIMIT 500"
    rows = db.query(sql, tuple(params))
    for r in rows:
        if r["latest_weight"] is not None:
            r["latest_weight"] = float(r["latest_weight"])
        if r["latest_body_fat"] is not None:
            r["latest_body_fat"] = float(r["latest_body_fat"])
    return rows


@router.get("/students/export")
def students_export(user: dict = Depends(get_current_user)):
    rows = stats_service.coach_students(user["id"])
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["学员", "今日打卡", "30天打卡天数", "30天打卡率%", "30天训练量kg",
                     "当前连续", "历史最长", "最近体重kg"])
    for s in rows:
        writer.writerow([s["nickname"], "是" if s["checked_today"] else "否", s["days_30"],
                         s["rate_30"], s["volume_30"], s["current_streak"],
                         s["longest_streak"], s["latest_weight"] or ""])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=students.csv"})


@router.get("/students/{student_id}")
def student_detail(student_id: int, user: dict = Depends(get_current_user)):
    own_ids = plan_service.coach_student_ids(user["id"])
    if student_id not in own_ids:
        raise HTTPException(status_code=403, detail="该学员不在你的名下")
    student = db.query(
        "SELECT id, nickname, avatar, phone, gender, current_streak, longest_streak, created_at "
        "FROM users WHERE id = %s", (student_id,), one=True)
    if not student:
        raise HTTPException(status_code=404, detail="学员不存在")
    checkins = db.query(
        "SELECT id, checkin_date, content, train_volume, duration_min, intensity, is_makeup "
        "FROM rehab_logs WHERE user_id = %s ORDER BY checkin_date DESC LIMIT 30", (student_id,))
    body = db.query(
        "SELECT record_date, weight, body_fat FROM body_records WHERE user_id = %s "
        "ORDER BY record_date DESC LIMIT 30", (student_id,))
    return {
        "student": {**student, "created_at": str(student["created_at"])},
        "checkins": [{**c, "checkin_date": c["checkin_date"].isoformat()} for c in checkins],
        "body_records": [{**b, "record_date": b["record_date"].isoformat()} for b in reversed(body)],
    }


@router.post("/students/{student_id}/urge")
def urge(student_id: int, data: UrgeIn, user: dict = Depends(get_current_user)):
    own_ids = plan_service.coach_student_ids(user["id"])
    if student_id not in own_ids:
        raise HTTPException(status_code=403, detail="该学员不在你的名下")
    send_message(user["id"], student_id, "text", f"【催打卡】{data.message}")
    return {"ok": True, "urged_today": True}


# ---------------- 训练计划 ----------------
@router.get("/plans")
def list_plans(student_id: int = None, user: dict = Depends(get_current_user)):
    return plan_service.get_coach_plans(user["id"], student_id)


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: int, user: dict = Depends(get_current_user)):
    plan = plan_service.get_plan_detail(plan_id)
    if not plan or plan["coach_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


@router.post("/plans")
def create_plan(data: PlanIn, user: dict = Depends(get_current_user)):
    student = db.query("SELECT id, role, status FROM users WHERE id = %s",
                       (data.student_id,), one=True)
    if not student or student["role"] != "student" or student["status"] != 1:
        raise HTTPException(status_code=400, detail="学员不存在或不可用")
    try:
        plan_id = plan_service.create_plan(user["id"], data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    send_message(user["id"], data.student_id, "text",
                 f"教练为你制定了新训练计划【{data.title}】，请在计划页查看。")
    return {"id": plan_id}


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, data: PlanIn, user: dict = Depends(get_current_user)):
    ok, err = plan_service.update_plan(user["id"], plan_id, data)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    send_message(user["id"], data.student_id, "text",
                 f"训练计划【{data.title}】已更新，请查看最新安排。")
    return {"ok": True}


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: dict = Depends(get_current_user)):
    ok, err = plan_service.delete_plan(user["id"], plan_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


@router.post("/plans/{plan_id}/copy")
def copy_plan(plan_id: int, user: dict = Depends(get_current_user)):
    new_id, err = plan_service.copy_plan(user["id"], plan_id, date.today())
    if not new_id:
        raise HTTPException(status_code=400, detail=err)
    return {"id": new_id}


@router.post("/plans/{plan_id}/recommend")
def recommend_plan(plan_id: int, user: dict = Depends(get_current_user)):
    """教练把自己的计划推荐给学员（学员端计划页优先展示）。"""
    row = db.query("SELECT id, title, student_id FROM rehab_programs "
                   "WHERE id = %s AND coach_id = %s", (plan_id, user["id"]), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="计划不存在")
    db.execute("UPDATE rehab_programs SET is_recommended = 1, recommend_weight = 50 WHERE id = %s",
               (plan_id,))
    send_message(user["id"], row["student_id"], "text",
                 f"教练向你推荐了训练计划【{row['title']}】，快去计划页查看吧！")
    return {"ok": True}


@router.delete("/plans/{plan_id}/recommend")
def cancel_recommend(plan_id: int, user: dict = Depends(get_current_user)):
    row = db.query("SELECT id FROM rehab_programs WHERE id = %s AND coach_id = %s",
                   (plan_id, user["id"]), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="计划不存在")
    db.execute("UPDATE rehab_programs SET is_recommended = 0, recommend_weight = 0 WHERE id = %s",
               (plan_id,))
    return {"ok": True}


# ---------------- 动作库 ----------------
@router.get("/exercises")
def list_exercises(q: str = None, category: str = None, user: dict = Depends(get_current_user)):
    sql = "SELECT * FROM rehab_exercises WHERE is_custom = 0 OR creator_id = %s"
    params = [user["id"]]
    if q:
        sql += " AND name LIKE %s"
        params.append(f"%{q}%")
    if category:
        sql += " AND category = %s"
        params.append(category)
    sql += " ORDER BY category, difficulty, name"
    return db.query(sql, tuple(params))


@router.post("/exercises")
def create_exercise(data: ExerciseIn, user: dict = Depends(get_current_user)):
    exists = db.query("SELECT id FROM rehab_exercises WHERE name = %s", (data.name,), one=True)
    if exists:
        raise HTTPException(status_code=400, detail="动作名称已存在")
    new_id = db.insert(
        "INSERT INTO rehab_exercises (name, category, equipment, difficulty, default_sets, "
        "default_reps, default_weight, is_custom, creator_id) VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)",
        (data.name, data.category, data.equipment, data.difficulty, data.default_sets,
         data.default_reps, data.default_weight, user["id"]))
    return {"id": new_id}


# ---------------- 线上指导：打卡流与评论 ----------------
@router.get("/checkin-feed")
def checkin_feed(days: int = 7, user: dict = Depends(get_current_user)):
    student_ids = plan_service.coach_student_ids(user["id"])
    if not student_ids:
        return []
    marks = ",".join(["%s"] * len(student_ids))
    rows = db.query(
        f"SELECT c.*, u.nickname AS student_name, u.avatar AS student_avatar, "
        f"(SELECT COUNT(*) FROM rehab_log_comments cc WHERE cc.checkin_id = c.id) AS comment_count "
        f"FROM rehab_logs c JOIN users u ON u.id = c.user_id "
        f"WHERE c.user_id IN ({marks}) AND c.checkin_date >= %s "
        f"ORDER BY c.checkin_date DESC, c.id DESC LIMIT 100",
        tuple(student_ids) + (date.today() - timedelta(days=min(max(days, 1), 30)),))
    result = []
    for r in rows:
        media = db.query("SELECT file_path, media_type FROM rehab_log_media WHERE checkin_id = %s",
                         (r["id"],))
        result.append({**r, "checkin_date": r["checkin_date"].isoformat(),
                       "created_at": str(r["created_at"]), "media": media})
    return result


@router.get("/checkins/{student_id}/{checkin_date}")
def student_checkin_detail(student_id: int, checkin_date: str, user: dict = Depends(get_current_user)):
    own_ids = plan_service.coach_student_ids(user["id"])
    if student_id not in own_ids:
        raise HTTPException(status_code=403, detail="该学员不在你的名下")
    detail = get_checkin_detail(student_id, parse_date(checkin_date))
    if not detail:
        raise HTTPException(status_code=404, detail="当日无打卡记录")
    return detail


@router.post("/checkins/{checkin_id}/comments")
def add_comment(checkin_id: int, data: CheckinCommentIn, user: dict = Depends(get_current_user)):
    checkin = db.query(
        "SELECT c.*, u.nickname AS student_name FROM rehab_logs c JOIN users u ON u.id = c.user_id "
        "WHERE c.id = %s", (checkin_id,), one=True)
    if not checkin:
        raise HTTPException(status_code=404, detail="打卡记录不存在")
    own_ids = plan_service.coach_student_ids(user["id"])
    if checkin["user_id"] not in own_ids:
        raise HTTPException(status_code=403, detail="该学员不在你的名下")
    comment_id = db.insert(
        "INSERT INTO rehab_log_comments (checkin_id, coach_id, content, voice_path) VALUES (%s,%s,%s,%s)",
        (checkin_id, user["id"], data.content, data.voice_path))
    send_message(user["id"], checkin["user_id"], "text",
                 f"教练点评了你的打卡（{checkin['checkin_date'].isoformat()}）：{data.content[:100]}")
    return {"id": comment_id}


# ---------------- 补签审批 ----------------
@router.get("/makeup-requests")
def makeup_requests(status: str = "pending", user: dict = Depends(get_current_user)):
    student_ids = plan_service.coach_student_ids(user["id"])
    if not student_ids:
        return []
    marks = ",".join(["%s"] * len(student_ids))
    sql = (f"SELECT m.*, u.nickname AS student_name, u.avatar FROM makeup_requests m "
           f"JOIN users u ON u.id = m.user_id WHERE m.user_id IN ({marks})")
    params = list(student_ids)
    if status and status != "all":
        sql += " AND m.status = %s"
        params.append(status)
    sql += " ORDER BY m.created_at DESC LIMIT 100"
    rows = db.query(sql, tuple(params))
    return [{**r, "checkin_date": r["checkin_date"].isoformat(),
             "created_at": str(r["created_at"]),
             "reviewed_at": str(r["reviewed_at"]) if r["reviewed_at"] else None} for r in rows]


@router.post("/makeup-requests/{request_id}/review")
def review_makeup(request_id: int, data: MakeupReviewIn, user: dict = Depends(get_current_user)):
    req = db.query("SELECT * FROM makeup_requests WHERE id = %s", (request_id,), one=True)
    if not req:
        raise HTTPException(status_code=404, detail="申请不存在")
    if req["status"] != "pending":
        raise HTTPException(status_code=400, detail="该申请已处理")
    own_ids = plan_service.coach_student_ids(user["id"])
    if req["user_id"] not in own_ids:
        raise HTTPException(status_code=403, detail="该学员不在你的名下")
    new_status = "approved" if data.approve else "rejected"
    db.execute(
        "UPDATE makeup_requests SET status=%s, reviewed_by=%s, review_note=%s, reviewed_at=NOW() "
        "WHERE id=%s",
        (new_status, user["id"], data.review_note, request_id))
    if data.approve:
        apply_makeup(req["user_id"], req["checkin_date"])
        send_message(user["id"], req["user_id"], "text",
                     f"你的补签申请（{req['checkin_date'].isoformat()}）已通过。")
    else:
        send_message(user["id"], req["user_id"], "text",
                     f"你的补签申请（{req['checkin_date'].isoformat()}）未通过。原因：{data.review_note or '无'}")
    return {"ok": True}


# ---------------- 消息模板与批量发送 ----------------
@router.get("/templates")
def templates(user: dict = Depends(get_current_user)):
    return db.query("SELECT * FROM message_templates WHERE coach_id IS NULL OR coach_id = %s "
                    "ORDER BY created_at DESC", (user["id"],))


@router.post("/templates")
def create_template(data: TemplateIn, user: dict = Depends(get_current_user)):
    template_id = db.insert(
        "INSERT INTO message_templates (coach_id, title, content, category) VALUES (%s,%s,%s,%s)",
        (user["id"], data.title, data.content, data.category))
    return {"id": template_id}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, user: dict = Depends(get_current_user)):
    row = db.query("SELECT id FROM message_templates WHERE id = %s AND coach_id = %s",
                   (template_id, user["id"]), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="模板不存在")
    db.execute("DELETE FROM message_templates WHERE id = %s", (template_id,))
    return {"ok": True}


@router.post("/messages/batch")
def batch_messages(data: BatchMessageIn, user: dict = Depends(get_current_user)):
    try:
        count = message_service.batch_send(user["id"], data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"sent": count}
