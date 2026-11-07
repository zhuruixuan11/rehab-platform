import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user, require_role
from app.database import db
from app.models.schemas import BodyRecordIn, CheckinIn, MakeupRequestIn
from app.services import achievement_service, checkin_service, plan_service, stats_service
from app.utils.helpers import get_config_int, parse_date

router = APIRouter(prefix="/api/student", tags=["学员端"],
                   dependencies=[Depends(require_role("student"))])


# ---------------- 每日打卡 ----------------
@router.post("/checkins")
def create_checkin(data: CheckinIn, user: dict = Depends(get_current_user)):
    for p in data.media_paths:
        if ".." in p or p.startswith("/"):
            raise HTTPException(status_code=400, detail="非法媒体路径")
    result, err = checkin_service.create_checkin(user["id"], data)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return result


@router.get("/checkins")
def month_checkins(year: int, month: int, user: dict = Depends(get_current_user)):
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise HTTPException(status_code=400, detail="日期参数不合法")
    return checkin_service.month_heatmap(user["id"], year, month)


@router.get("/checkins/{checkin_date}")
def checkin_detail(checkin_date: str, user: dict = Depends(get_current_user)):
    d = parse_date(checkin_date)
    detail = checkin_service.get_checkin_detail(user["id"], d)
    if not detail:
        # 当日无打卡：返回 200 空结果，避免前端出现 404 报错
        return {"checkin": None, "media": [], "details": [], "comments": []}
    return detail


@router.delete("/checkins/{checkin_date}")
def remove_checkin(checkin_date: str, user: dict = Depends(get_current_user)):
    ok, err = checkin_service.delete_checkin(user["id"], parse_date(checkin_date))
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


@router.get("/streak")
def streak(user: dict = Depends(get_current_user)):
    return checkin_service.checkin_streak_info(user["id"])


# ---------------- 补签 ----------------
@router.post("/makeup-requests")
def create_makeup(data: MakeupRequestIn, user: dict = Depends(get_current_user)):
    if data.checkin_date >= date.today():
        raise HTTPException(status_code=400, detail="只能申请过去日期的补签")
    limit = get_config_int("makeup_days_limit", 7)
    if (date.today() - data.checkin_date).days > limit:
        raise HTTPException(status_code=400, detail=f"仅支持最近 {limit} 天内的补签")
    existing = db.query("SELECT id FROM rehab_logs WHERE user_id = %s AND checkin_date = %s",
                        (user["id"], data.checkin_date), one=True)
    if existing:
        raise HTTPException(status_code=400, detail="该日期已有打卡记录")
    pending = db.query(
        "SELECT id FROM makeup_requests WHERE user_id = %s AND checkin_date = %s AND status = 'pending'",
        (user["id"], data.checkin_date), one=True)
    if pending:
        raise HTTPException(status_code=400, detail="该日期已有待审批的补签申请")
    request_id = db.insert(
        "INSERT INTO makeup_requests (user_id, checkin_date, reason) VALUES (%s,%s,%s)",
        (user["id"], data.checkin_date, data.reason))
    coach_ids = [r["coach_id"] for r in db.query(
        "SELECT DISTINCT coach_id FROM rehab_programs WHERE student_id = %s", (user["id"],))]
    from app.services.ws_manager import notify
    for cid in coach_ids:
        notify(cid, {"type": "makeup_request", "student_id": user["id"],
                     "message": "收到新的补签申请"})
    return {"id": request_id}


@router.get("/makeup-requests")
def my_makeups(user: dict = Depends(get_current_user)):
    rows = db.query(
        "SELECT * FROM makeup_requests WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
        (user["id"],))
    return [{**r, "checkin_date": r["checkin_date"].isoformat(),
             "created_at": str(r["created_at"]),
             "reviewed_at": str(r["reviewed_at"]) if r["reviewed_at"] else None} for r in rows]


# ---------------- 身体数据 ----------------
@router.get("/body-records")
def body_records(days: int = 90, user: dict = Depends(get_current_user)):
    days = min(max(days, 7), 365)
    return stats_service.body_trend(user["id"], days)


@router.post("/body-records")
def add_body_record(data: BodyRecordIn, user: dict = Depends(get_current_user)):
    if data.record_date > date.today():
        raise HTTPException(status_code=400, detail="记录日期不能晚于今天")
    existing = db.query("SELECT id FROM body_records WHERE user_id = %s AND record_date = %s",
                        (user["id"], data.record_date), one=True)
    if existing:
        db.execute(
            "UPDATE body_records SET weight=%s, body_fat=%s, chest=%s, waist=%s, hip=%s, "
            "arm=%s, thigh=%s, photo_path=%s WHERE id = %s",
            (data.weight, data.body_fat, data.chest, data.waist, data.hip,
             data.arm, data.thigh, data.photo_path or "", existing["id"]))
        return {"id": existing["id"], "updated": True}
    new_id = db.insert(
        "INSERT INTO body_records (user_id, record_date, weight, body_fat, chest, waist, hip, "
        "arm, thigh, photo_path) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (user["id"], data.record_date, data.weight, data.body_fat, data.chest, data.waist,
         data.hip, data.arm, data.thigh, data.photo_path or ""))
    return {"id": new_id, "updated": False}


# ---------------- 训练计划 ----------------
@router.get("/plans")
def my_plans(user: dict = Depends(get_current_user)):
    return plan_service.get_student_plans(user["id"])


@router.get("/recommended-plans")
def recommended(user: dict = Depends(get_current_user)):
    return plan_service.recommended_plans()


# ---------------- 动作库 ----------------
@router.get("/exercises")
def exercises(category: str = None, difficulty: int = None, q: str = None,
              user: dict = Depends(get_current_user)):
    """内置动作库。免费用户限前10个（免费动作），会员解锁全部。"""
    from app.routers.member import user_is_member
    is_member = user_is_member(user["id"]) if user["role"] == "student" else True
    where, params = ["is_custom = 0"], []
    if not is_member:
        where.append("is_member_only = 0")   # 免费版限10个
    if category:
        where.append("category = %s")
        params.append(category)
    if difficulty is not None:
        where.append("difficulty = %s")
        params.append(difficulty)
    if q:
        where.append("(name LIKE %s OR intro LIKE %s)")
        params.extend([f"%{q}%"] * 2)
    sql = f"""
        SELECT id, name, category, equipment, difficulty, intro, steps, tips,
               default_sets, default_reps, default_weight, muscles, breathing, anim,
               video_url, is_member_only, contraindications, alternatives
        FROM rehab_exercises
        WHERE {' AND '.join(where)}
        ORDER BY sort_order, difficulty, name
    """
    rows = db.query(sql, tuple(params))
    for r in rows:
        if isinstance(r.get("muscles"), str):
            try: r["muscles"] = json.loads(r["muscles"])
            except ValueError: r["muscles"] = None
    all_count = db.query("SELECT COUNT(*) c FROM rehab_exercises WHERE is_custom = 0", one=True)["c"]
    return {
        "items": rows,
        "is_member": is_member,
        "total_free": db.query("SELECT COUNT(*) c FROM rehab_exercises WHERE is_custom=0 AND is_member_only=0", one=True)["c"],
        "total_paid": all_count,
    }


# ---------------- 成就与排行 ----------------
@router.get("/achievements")
def achievements(user: dict = Depends(get_current_user)):
    return achievement_service.list_achievements(user["id"])


@router.get("/rankings")
def rankings(period: str = "week", metric: str = "days", user: dict = Depends(get_current_user)):
    try:
        data = stats_service.rankings(period, metric)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"period": period, "metric": metric,
            "my_rank": next((r["rank"] for r in data if r["user_id"] == user["id"]), None),
            "items": data}


# ---------------- 数据总览 ----------------
@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    return stats_service.student_dashboard(user["id"])
