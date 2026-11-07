"""康复业务接口：康复档案、康复评估、筛查预警、排班预约、康复报告、中医体质辨识。"""
import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user, require_role
from app.database import db

router = APIRouter(prefix="/api/rehab", tags=["康复业务"])

PATIENT = "student"      # 患者（沿用原 role 值，前端显示为「患者」）
THERAPIST = "coach"      # 康复治疗师（沿用原 role 值，前端显示为「康复治疗师」）
ADMIN = "admin"

# 九种体质：标准辨识阈值
TCM_TYPES = ["平和质", "气虚质", "阳虚质", "阴虚质", "痰湿质", "湿热质", "血瘀质", "气郁质", "特禀质"]

TCM_ADVICE = {
    "平和质": "平和质：阴阳气血调和，康复训练可按计划循序渐进，注意劳逸结合、规律作息。",
    "气虚质": "气虚质：易疲乏、气短。康复训练宜低强度、多次短时，避免过度耗气；"
              "可配合八段锦、腹式呼吸训练，饮食宜山药、黄芪、大枣。",
    "阳虚质": "阳虚质：畏寒肢冷。训练前充分热身、注意保暖，避免大汗伤阳；"
              "可艾灸关元、命门，饮食宜温补（生姜、羊肉），忌生冷。",
    "阴虚质": "阴虚质：手足心热、口干。康复训练避免高温环境与大量出汗，"
              "注意补水养阴，可练太极、静功，饮食宜百合、银耳、梨。",
    "痰湿质": "痰湿质：形体偏胖、困重。宜中低强度有氧配合核心训练，循序渐进增加运动量；"
              "饮食少油腻甜食，可食薏苡仁、赤小豆、冬瓜。",
    "湿热质": "湿热质：口苦、易长痘。训练后及时清洁、避免闷热环境，"
              "饮食清淡，少辛辣油炸，可食绿豆、苦瓜、冬瓜。",
    "血瘀质": "血瘀质：痛有定处、易瘀青。康复以温通经络为主，可配合推拿、艾灸、热敷；"
              "训练强度渐进，避免暴力牵拉，饮食可少量活血食材（山楂、黑木耳）。",
    "气郁质": "气郁质：情绪低落、胸胁胀。康复训练宜舒展类（瑜伽、拉伸、户外快走），"
              "配合呼吸放松；注意情绪疏导，可饮玫瑰花茶。",
    "特禀质": "特禀质：过敏体质。注意训练环境（花粉、尘螨）与器械清洁，"
              "出现过敏反应及时停止训练并就医。",
}


def _is_patient(user: dict) -> bool:
    return user["role"] == PATIENT


def _is_therapist(user: dict) -> bool:
    return user["role"] == THERAPIST


def _can_access_patient(user: dict, patient_id: int) -> bool:
    if user["role"] == ADMIN:
        return True
    if _is_patient(user):
        return int(user["id"]) == int(patient_id)
    if _is_therapist(user):
        row = db.query(
            "SELECT 1 ok FROM rehab_cases WHERE patient_id=%s AND therapist_id=%s LIMIT 1",
            (patient_id, user["id"]), one=True)
        return row is not None
    return False


# ==================== 康复档案 ====================
class CaseIn(BaseModel):
    patient_id: int
    condition_name: str
    condition_type: str = "运动损伤"
    injured_side: str = "左"
    onset_date: date | None = None
    stage: str = "恢复期"
    chief_complaint: str = ""
    diagnosis: str = ""
    goal: str = ""


@router.get("/cases")
def list_cases(user: dict = Depends(get_current_user)):
    """康复档案列表：患者看自己，治疗师看自己负责的，管理员看全部。"""
    if user["role"] == ADMIN:
        where, params = "1=1", ()
    elif _is_therapist(user):
        where, params = "c.therapist_id=%s", (user["id"],)
    else:
        where, params = "c.patient_id=%s", (user["id"],)
    rows = db.query(
        f"SELECT c.*, p.nickname AS patient_name, p.username AS patient_username, "
        f"t.nickname AS therapist_name FROM rehab_cases c "
        f"LEFT JOIN users p ON p.id=c.patient_id LEFT JOIN users t ON t.id=c.therapist_id "
        f"WHERE {where} ORDER BY c.status='active' DESC, c.id DESC", params)
    return rows


@router.post("/cases")
def create_case(data: CaseIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    """治疗师为患者建立康复档案。"""
    target = db.query("SELECT id, role FROM users WHERE id=%s", (data.patient_id,), one=True)
    if not target:
        raise HTTPException(400, "患者不存在")
    case_id = db.insert(
        "INSERT INTO rehab_cases (patient_id, therapist_id, condition_name, condition_type, injured_side, "
        "onset_date, stage, chief_complaint, diagnosis, goal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (data.patient_id, user["id"], data.condition_name, data.condition_type, data.injured_side,
         data.onset_date, data.stage, data.chief_complaint, data.diagnosis, data.goal))
    return {"ok": True, "case_id": case_id}


@router.put("/cases/{case_id}")
def update_case(case_id: int, data: CaseIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    cur = db.query("SELECT * FROM rehab_cases WHERE id=%s", (case_id,), one=True)
    if not cur:
        raise HTTPException(404, "康复档案不存在")
    if user["role"] != ADMIN and cur["therapist_id"] != user["id"]:
        raise HTTPException(403, "无权修改该康复档案")
    db.execute(
        "UPDATE rehab_cases SET condition_name=%s, condition_type=%s, injured_side=%s, onset_date=%s, "
        "stage=%s, chief_complaint=%s, diagnosis=%s, goal=%s WHERE id=%s",
        (data.condition_name, data.condition_type, data.injured_side, data.onset_date, data.stage,
         data.chief_complaint, data.diagnosis, data.goal, case_id))
    return {"ok": True}


# ==================== 康复评估 ====================
class AssessmentIn(BaseModel):
    patient_id: int
    case_id: int | None = None
    assess_date: date | None = None
    pain_vas: int = 0
    rom: dict = {}
    mmt: dict = {}
    balance_score: int = 0
    gait_score: int = 0
    posture_score: int = 0
    adl_score: int = 0
    berg_score: int | None = None
    tug_sec: float | None = None
    walk10m_sec: float | None = None
    odi_score: int | None = None
    womac_score: int | None = None
    notes: str = ""


@router.get("/assessments")
def list_assessments(patient_id: int | None = None, case_id: int | None = None,
                     user: dict = Depends(get_current_user)):
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者评估数据")
    cond, params = "a.patient_id=%s", [pid]
    if case_id:
        cond += " AND a.case_id=%s"
        params.append(case_id)
    rows = db.query(
        f"SELECT a.*, u.nickname AS assessor_name FROM rehab_assessments a "
        f"LEFT JOIN users u ON u.id=a.assessor_id WHERE {cond} ORDER BY a.assess_date ASC, a.id ASC",
        tuple(params))
    import json
    for r in rows:
        for k in ("rom_json", "mmt_json"):
            if r.get(k):
                try:
                    r[k.replace("_json", "")] = json.loads(r[k])
                except Exception:
                    r[k.replace("_json", "")] = {}
    return rows


@router.post("/assessments")
def create_assessment(data: AssessmentIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    import json
    if not _can_access_patient(user, data.patient_id):
        raise HTTPException(403, "无权为该患者录入评估")
    aid = db.insert(
        "INSERT INTO rehab_assessments (patient_id, case_id, assess_date, assessor_id, pain_vas, "
        "rom_json, mmt_json, balance_score, gait_score, posture_score, adl_score, "
        "berg_score, tug_sec, walk10m_sec, odi_score, womac_score, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (data.patient_id, data.case_id, data.assess_date or date.today(), user["id"], data.pain_vas,
         json.dumps(data.rom, ensure_ascii=False), json.dumps(data.mmt, ensure_ascii=False),
         data.balance_score, data.gait_score, data.posture_score, data.adl_score,
         data.berg_score, data.tug_sec, data.walk10m_sec, data.odi_score, data.womac_score,
         data.notes))
    return {"ok": True, "assessment_id": aid}


@router.get("/assessments/trend")
def assessment_trend(patient_id: int | None = None, case_id: int | None = None,
                     user: dict = Depends(get_current_user)):
    """康复趋势：疼痛VAS下降与功能评分上升，供前端画图。"""
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者评估数据")
    cond, params = "patient_id=%s", [pid]
    if case_id:
        cond += " AND case_id=%s"
        params.append(case_id)
    rows = db.query(
        f"SELECT assess_date, pain_vas, balance_score, gait_score, posture_score, adl_score "
        f"FROM rehab_assessments WHERE {cond} ORDER BY assess_date ASC, id ASC", tuple(params))
    return [{"date": str(r["assess_date"]), "pain_vas": r["pain_vas"],
             "balance": r["balance_score"], "gait": r["gait_score"],
             "posture": r["posture_score"], "adl": r["adl_score"]} for r in rows]


@router.get("/patients")
def my_patients(user: dict = Depends(require_role(THERAPIST, ADMIN))):
    """治疗师的患者名册（用于录入评估时选择）。"""
    if user["role"] == ADMIN:
        rows = db.query("SELECT id, username, nickname FROM users WHERE role=%s ORDER BY id", (PATIENT,))
    else:
        rows = db.query(
            "SELECT DISTINCT u.id, u.username, u.nickname FROM users u "
            "JOIN rehab_cases c ON c.patient_id=u.id WHERE c.therapist_id=%s ORDER BY u.id", (user["id"],))
    return rows


# ==================== 红旗征筛查 ====================
RED_FLAG_ITEMS = [
    ("fever", "不明原因发热、盗汗或体重明显下降"),
    ("night_pain", "夜间静息痛或疼痛进行性加重"),
    ("saddle", "鞍区麻木、大小便功能障碍"),
    ("weakness", "双下肢进行性无力或行走困难"),
    ("trauma", "近期严重外伤，疑似骨折/脱位"),
    ("cardiopulmonary", "胸痛、胸闷、静息气促或心悸"),
    ("wound", "术后伤口红肿、渗液或持续发热"),
    ("dizziness", "眩晕伴恶心呕吐、复视或言语不清"),
]
RED_FLAG_LABEL = dict(RED_FLAG_ITEMS)


class ScreeningIn(BaseModel):
    patient_id: int
    case_id: int | None = None
    items: dict[str, bool] = {}
    notes: str = ""


def _screening_out(row: dict) -> dict:
    try:
        items = json.loads(row.get("items_json") or "{}")
    except Exception:
        items = {}
    positives = [RED_FLAG_LABEL[k] for k, v in items.items() if v and k in RED_FLAG_LABEL]
    return {
        **row,
        "items": items,
        "positive_labels": positives,
        "has_red_flag": bool(row.get("has_red_flag")),
        "created_at": str(row.get("created_at") or ""),
    }


@router.get("/screenings")
def list_screenings(patient_id: int | None = None, case_id: int | None = None,
                    limit: int = 10, user: dict = Depends(get_current_user)):
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者筛查记录")
    cond, params = "patient_id=%s", [pid]
    if case_id:
        cond += " AND case_id=%s"
        params.append(case_id)
    rows = db.query(
        f"SELECT * FROM rehab_screenings WHERE {cond} ORDER BY id DESC LIMIT %s",
        tuple(params) + (min(max(limit, 1), 50),))
    return [_screening_out(r) for r in rows]


@router.post("/screenings")
def create_screening(data: ScreeningIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    if not _can_access_patient(user, data.patient_id):
        raise HTTPException(403, "无权为该患者录入筛查")
    items = {k: bool(v) for k, v in data.items.items() if k in RED_FLAG_LABEL}
    has_red = 1 if any(items.values()) else 0
    sid = db.insert(
        "INSERT INTO rehab_screenings (patient_id, case_id, assessor_id, items_json, has_red_flag, notes) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (data.patient_id, data.case_id, user["id"],
         json.dumps(items, ensure_ascii=False), has_red, data.notes))
    positives = [RED_FLAG_LABEL[k] for k, v in items.items() if v]
    return {"ok": True, "screening_id": sid, "has_red_flag": bool(has_red),
            "positive_labels": positives,
            "advice": ("筛查命中红旗征，建议暂停高强度训练并尽快就医/转诊进一步检查。"
                       if has_red else "未命中红旗征，可按康复方案循序渐进训练。")}


# ==================== 依从率 / 待办预警 ====================
def _adherence_stats(patient_id: int, days: int = 7) -> dict:
    today = date.today()
    start = today - timedelta(days=days - 1)
    plan_ids = [r["id"] for r in db.query(
        "SELECT id FROM rehab_programs WHERE student_id=%s AND status='active'", (patient_id,))]
    planned_days = 0
    if plan_ids:
        marks = ",".join(["%s"] * len(plan_ids))
        rows = db.query(
            f"SELECT DISTINCT day_date FROM program_items WHERE plan_id IN ({marks}) "
            f"AND day_date BETWEEN %s AND %s", tuple(plan_ids) + (start, today))
        planned_days = len(rows)
    logged = db.query(
        "SELECT COUNT(DISTINCT checkin_date) AS c FROM rehab_logs "
        "WHERE user_id=%s AND checkin_date BETWEEN %s AND %s",
        (patient_id, start, today), one=True)["c"]
    denom = planned_days or days
    rate = min(100, round(logged / denom * 100)) if denom else 0
    return {
        "days": days, "start_date": str(start), "end_date": str(today),
        "planned_days": planned_days, "target_days": denom,
        "logged_days": int(logged), "rate": rate,
        "has_plan": bool(plan_ids),
    }


@router.get("/adherence")
def adherence(patient_id: int | None = None, days: int = 7,
              user: dict = Depends(get_current_user)):
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者依从率")
    return _adherence_stats(pid, min(max(days, 1), 30))


@router.get("/alerts")
def todo_alerts(user: dict = Depends(require_role(THERAPIST, ADMIN))):
    """治疗师待办预警：超 3 天未训练、练后疼痛异常、超 14 天未复评、依从率偏低。"""
    today = date.today()
    if user["role"] == ADMIN:
        cases = db.query(
            "SELECT c.*, u.nickname AS patient_name FROM rehab_cases c "
            "JOIN users u ON u.id=c.patient_id WHERE c.status='active' ORDER BY c.id")
    else:
        cases = db.query(
            "SELECT c.*, u.nickname AS patient_name FROM rehab_cases c "
            "JOIN users u ON u.id=c.patient_id WHERE c.therapist_id=%s AND c.status='active' "
            "ORDER BY c.id", (user["id"],))

    items = []
    for case in cases:
        pid = case["patient_id"]
        name = case["patient_name"]

        def add(alert_type, level, title, message, action="查看"):
            items.append({
                "patient_id": pid, "patient_name": name, "case_id": case["id"],
                "condition_name": case["condition_name"], "type": alert_type,
                "level": level, "title": title, "message": message, "action": action,
            })

        last_log = db.query(
            "SELECT MAX(checkin_date) AS d FROM rehab_logs WHERE user_id=%s",
            (pid,), one=True)["d"]
        gap = (today - last_log).days if last_log else None
        if gap is None or gap > 3:
            add("no_log", "high" if (gap is None or gap >= 7) else "warn", "训练中断",
                (f"已 {gap} 天未记录康复日志，请及时跟进。" if gap is not None
                 else "尚无康复日志记录，请了解患者执行情况。"), "发送提醒")

        abn = db.query(
            "SELECT checkin_date, vas_before, vas_after FROM rehab_logs "
            "WHERE user_id=%s AND checkin_date>=%s AND vas_after IS NOT NULL "
            "AND (vas_after>=7 OR (vas_before IS NOT NULL AND vas_after-vas_before>=2)) "
            "ORDER BY checkin_date DESC LIMIT 1",
            (pid, today - timedelta(days=14)), one=True)
        if abn:
            add("vas", "high", "练后疼痛异常",
                f"{str(abn['checkin_date'])} 练前 VAS {abn['vas_before'] if abn['vas_before'] is not None else '-'}"
                f" → 练后 {abn['vas_after']}，建议调整训练量并复评。", "去评估")

        last_assess = db.query(
            "SELECT MAX(assess_date) AS d FROM rehab_assessments WHERE patient_id=%s",
            (pid,), one=True)["d"]
        a_gap = (today - last_assess).days if last_assess else None
        if a_gap is None or a_gap > 14:
            add("reassess", "warn", "待复评",
                (f"距上次评估已 {a_gap} 天，建议安排复评以更新方案。" if a_gap is not None
                 else "尚未进行康复评估，建议尽快完成首次评估。"), "去评估")

        adh = _adherence_stats(pid)
        if adh["rate"] < 60:
            add("adherence", "warn", "依从率偏低",
                f"近 7 天应训练 {adh['target_days']} 天，实际 {adh['logged_days']} 天（{adh['rate']}%）。",
                "发送提醒")

    level_order = {"high": 0, "warn": 1, "info": 2}
    items.sort(key=lambda x: (level_order.get(x["level"], 9), x["patient_name"]))
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "high": sum(1 for i in items if i["level"] == "high"),
            "warn": sum(1 for i in items if i["level"] == "warn"),
            "patients": len({i["patient_id"] for i in items}),
        },
    }


# ==================== 阶段康复模板 ====================
STAGE_TEMPLATES = [
    ("early", "0-2 周 · 保护期", {1},
     "控制疼痛与肿胀，维持无痛关节活动度，激活基础肌力。"),
    ("mid", "2-6 周 · 恢复期", {1, 2},
     "逐步增加关节活动度与负荷，重建动作控制与耐力。"),
    ("late", "6 周+ · 强化期", {2, 3},
     "强化力量、平衡与功能性动作，为回归日常/运动做准备。"),
]


@router.get("/stage-templates")
def stage_templates(patient_id: int | None = None, case_id: int | None = None,
                    user: dict = Depends(get_current_user)):
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者阶段模板")
    if case_id:
        case = db.query("SELECT * FROM rehab_cases WHERE id=%s AND patient_id=%s",
                        (case_id, pid), one=True)
    else:
        case = db.query("SELECT * FROM rehab_cases WHERE patient_id=%s "
                        "ORDER BY (status='active') DESC, id DESC LIMIT 1", (pid,), one=True)
    text = " ".join(str(case.get(k) or "") for k in
                    ("condition_name", "condition_type", "chief_complaint", "diagnosis")) if case else ""
    matched = [cat for cat, kws in BODY_PART_KEYWORDS.items() if any(k in text for k in kws)]
    if not matched:
        matched = ["核心躯干", "平衡步态"]

    stages = []
    for key, name, diffs, desc in STAGE_TEMPLATES:
        cph = ",".join(["%s"] * len(matched))
        dph = ",".join(["%s"] * len(diffs))
        rows = db.query(
            f"SELECT id, name, category, equipment, difficulty, default_sets, default_reps, "
            f"default_weight, contraindications, alternatives FROM rehab_exercises "
            f"WHERE is_custom=0 AND category IN ({cph}) "
            f"AND difficulty IN ({dph}) ORDER BY sort_order, id LIMIT 12",
            tuple(matched) + tuple(sorted(diffs)))
        seen, picks = set(), []
        for r in rows:
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            picks.append(r)
            if len(picks) == 4:
                break
        if len(picks) < 4:
            extra = db.query(
                "SELECT id, name, category, equipment, difficulty, default_sets, default_reps, "
                "default_weight FROM rehab_exercises WHERE is_custom=0 AND difficulty IN "
                f"({dph}) ORDER BY sort_order, id LIMIT 20", tuple(sorted(diffs)))
            for r in extra:
                if r["name"] not in seen:
                    picks.append(r)
                    seen.add(r["name"])
                if len(picks) == 4:
                    break
        pattern = [(0, 0), (0, 1), (2, 2), (2, 3), (4, 0), (4, 1)]
        items = []
        for offset, idx in pattern:
            if idx >= len(picks):
                continue
            e = picks[idx]
            items.append({
                "day_offset": offset, "exercise_name": e["name"], "category": e["category"],
                "sets": e["default_sets"], "reps": e["default_reps"],
                "weight_suggest": float(e["default_weight"] or 0),
                "note": f"{name} · {e['category']}", "sort_order": len(items),
            })
        stages.append({"key": key, "name": name, "description": desc, "items": items})

    return {
        "case_id": case["id"] if case else None,
        "condition_name": case["condition_name"] if case else "",
        "matched_categories": matched,
        "stages": stages,
    }


# ==================== 排班 / 预约 / 疗程卡 ====================
class ScheduleIn(BaseModel):
    work_date: date
    start_time: str
    end_time: str
    slot_min: int = 30
    capacity: int = 1
    location: str = "康衡康复中心"
    note: str = ""


class AppointmentIn(BaseModel):
    schedule_id: int | None = None
    coach_id: int | None = None
    appt_date: date | None = None
    start_time: str = ""
    end_time: str = ""
    appt_type: str = "门诊评估"
    note: str = ""


class TreatmentCardIn(BaseModel):
    patient_id: int
    case_id: int | None = None
    title: str
    total_sessions: int = 10
    valid_from: date | None = None
    valid_to: date | None = None
    note: str = ""


class FollowupIn(BaseModel):
    patient_id: int
    case_id: int | None = None
    due_date: date | None = None
    content: str = ""


class ReminderIn(BaseModel):
    patient_id: int
    content: str = ""


def _time_add(start: str, minutes: int) -> str:
    try:
        h, m = [int(x) for x in start.split(":")[:2]]
        total = h * 60 + m + minutes
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"
    except Exception:
        return start


@router.get("/schedules")
def list_schedules(start_date: date | None = None, end_date: date | None = None,
                   coach_id: int | None = None, user: dict = Depends(get_current_user)):
    cond, params = ["1=1"], []
    if _is_patient(user):
        cond.append("s.work_date >= %s")
        params.append(date.today())
    else:
        if coach_id:
            cond.append("s.coach_id=%s")
            params.append(coach_id)
        if _is_therapist(user):
            cond.append("s.coach_id=%s")
            params.append(user["id"])
    if start_date:
        cond.append("s.work_date >= %s")
        params.append(start_date)
    if end_date:
        cond.append("s.work_date <= %s")
        params.append(end_date)
    rows = db.query(
        f"SELECT s.*, u.nickname AS coach_name, u.avatar AS coach_avatar, "
        f"(SELECT COUNT(*) FROM appointments a WHERE a.schedule_id=s.id "
        f"AND a.status IN ('booked','completed')) AS booked "
        f"FROM therapist_schedules s JOIN users u ON u.id=s.coach_id "
        f"WHERE {' AND '.join(cond)} ORDER BY s.work_date, s.start_time", tuple(params))
    for r in rows:
        r["work_date"] = str(r["work_date"])
        r["remaining"] = max(0, (r["capacity"] or 1) - (r["booked"] or 0))
    return rows


@router.post("/schedules")
def create_schedule(data: ScheduleIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    if data.end_time <= data.start_time:
        raise HTTPException(400, "结束时间需晚于开始时间")
    coach_id = user["id"] if _is_therapist(user) else user["id"]
    sid = db.insert(
        "INSERT INTO therapist_schedules (coach_id, work_date, start_time, end_time, slot_min, "
        "capacity, location, note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (coach_id, data.work_date, data.start_time, data.end_time, data.slot_min,
         data.capacity, data.location, data.note))
    return {"ok": True, "schedule_id": sid}


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    row = db.query("SELECT coach_id FROM therapist_schedules WHERE id=%s", (schedule_id,), one=True)
    if not row:
        raise HTTPException(404, "排班不存在")
    if user["role"] != ADMIN and row["coach_id"] != user["id"]:
        raise HTTPException(403, "无权删除该排班")
    db.execute("DELETE FROM therapist_schedules WHERE id=%s", (schedule_id,))
    return {"ok": True}


@router.get("/appointments")
def list_appointments(status: str | None = None, user: dict = Depends(get_current_user)):
    cond, params = ["1=1"], []
    if _is_patient(user):
        cond.append("a.patient_id=%s")
        params.append(user["id"])
    elif _is_therapist(user):
        cond.append("a.coach_id=%s")
        params.append(user["id"])
    if status and status != "all":
        cond.append("a.status=%s")
        params.append(status)
    rows = db.query(
        f"SELECT a.*, p.nickname AS patient_name, p.avatar AS patient_avatar, "
        f"c.nickname AS coach_name, c.avatar AS coach_avatar "
        f"FROM appointments a JOIN users p ON p.id=a.patient_id "
        f"JOIN users c ON c.id=a.coach_id WHERE {' AND '.join(cond)} "
        f"ORDER BY a.appt_date DESC, a.start_time DESC LIMIT 100", tuple(params))
    for r in rows:
        r["appt_date"] = str(r["appt_date"])
    return rows


@router.post("/appointments")
def create_appointment(data: AppointmentIn, user: dict = Depends(get_current_user)):
    if not _is_patient(user):
        raise HTTPException(403, "请在患者端进行预约")
    today = date.today()
    schedule = None
    if data.schedule_id:
        schedule = db.query("SELECT * FROM therapist_schedules WHERE id=%s",
                            (data.schedule_id,), one=True)
        if not schedule:
            raise HTTPException(404, "排班不存在")
        if schedule["work_date"] < today:
            raise HTTPException(400, "该排班已过期")
        booked = db.query(
            "SELECT COUNT(*) AS c FROM appointments WHERE schedule_id=%s "
            "AND status IN ('booked','completed')", (data.schedule_id,), one=True)["c"]
        if booked >= (schedule["capacity"] or 1):
            raise HTTPException(400, "该时段已约满，请选择其他时间")
        coach_id = schedule["coach_id"]
        appt_date = schedule["work_date"]
        start_time = data.start_time or schedule["start_time"]
        end_time = data.end_time or _time_add(start_time, schedule["slot_min"] or 30)
    else:
        if not data.coach_id or not data.appt_date or not data.start_time:
            raise HTTPException(400, "请选择康复治疗师、日期与时间")
        if data.appt_date < today:
            raise HTTPException(400, "预约日期不能早于今天")
        coach = db.query("SELECT id FROM users WHERE id=%s AND role=%s",
                         (data.coach_id, THERAPIST), one=True)
        if not coach:
            raise HTTPException(400, "康复治疗师不存在")
        coach_id, appt_date = data.coach_id, data.appt_date
        start_time, end_time = data.start_time, data.end_time

    dup = db.query(
        "SELECT id FROM appointments WHERE patient_id=%s AND appt_date=%s AND start_time=%s "
        "AND status='booked'", (user["id"], appt_date, start_time), one=True)
    if dup:
        raise HTTPException(400, "该时段已有预约")
    aid = db.insert(
        "INSERT INTO appointments (patient_id, coach_id, schedule_id, appt_date, start_time, "
        "end_time, appt_type, note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (user["id"], coach_id, data.schedule_id, appt_date, start_time, end_time,
         data.appt_type, data.note))
    return {"ok": True, "appointment_id": aid}


@router.post("/appointments/{appointment_id}/complete")
def complete_appointment(appointment_id: int, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    row = db.query("SELECT * FROM appointments WHERE id=%s", (appointment_id,), one=True)
    if not row:
        raise HTTPException(404, "预约不存在")
    if user["role"] != ADMIN and row["coach_id"] != user["id"]:
        raise HTTPException(403, "无权操作该预约")
    if row["status"] != "booked":
        raise HTTPException(400, "该预约不是待就诊状态")
    db.execute("UPDATE appointments SET status='completed' WHERE id=%s", (appointment_id,))

    card = db.query(
        "SELECT * FROM treatment_cards WHERE patient_id=%s AND status='active' "
        "AND used_sessions < total_sessions ORDER BY valid_to IS NULL, valid_to LIMIT 1",
        (row["patient_id"],), one=True)
    remaining = None
    if card:
        used = (card["used_sessions"] or 0) + 1
        status = "finished" if used >= card["total_sessions"] else "active"
        db.execute("UPDATE treatment_cards SET used_sessions=%s, status=%s WHERE id=%s",
                   (used, status, card["id"]))
        remaining = max(0, card["total_sessions"] - used)
    return {"ok": True, "card_remaining": remaining}


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int, user: dict = Depends(get_current_user)):
    row = db.query("SELECT * FROM appointments WHERE id=%s", (appointment_id,), one=True)
    if not row:
        raise HTTPException(404, "预约不存在")
    if user["role"] != ADMIN and row["patient_id"] != user["id"] and row["coach_id"] != user["id"]:
        raise HTTPException(403, "无权取消该预约")
    if row["status"] != "booked":
        raise HTTPException(400, "仅可取消待就诊预约")
    db.execute("UPDATE appointments SET status='cancelled' WHERE id=%s", (appointment_id,))
    return {"ok": True}


@router.get("/treatment-cards")
def list_treatment_cards(patient_id: int | None = None, user: dict = Depends(get_current_user)):
    if patient_id is None and not _is_patient(user):
        if user["role"] == ADMIN:
            rows = db.query(
                "SELECT tc.*, p.nickname AS patient_name FROM treatment_cards tc "
                "JOIN users p ON p.id=tc.patient_id "
                "ORDER BY tc.status='active' DESC, tc.id DESC")
        else:
            rows = db.query(
                "SELECT tc.*, p.nickname AS patient_name FROM treatment_cards tc "
                "JOIN users p ON p.id=tc.patient_id "
                "WHERE tc.patient_id IN (SELECT DISTINCT patient_id FROM rehab_cases "
                "WHERE therapist_id=%s) ORDER BY tc.status='active' DESC, tc.id DESC", (user["id"],))
    else:
        pid = patient_id or user["id"]
        if not _can_access_patient(user, pid):
            raise HTTPException(403, "无权查看该患者疗程卡")
        rows = db.query(
            "SELECT tc.*, p.nickname AS patient_name FROM treatment_cards tc "
            "JOIN users p ON p.id=tc.patient_id WHERE tc.patient_id=%s "
            "ORDER BY tc.status='active' DESC, tc.id DESC", (pid,))
    for r in rows:
        r["valid_from"] = str(r["valid_from"]) if r["valid_from"] else None
        r["valid_to"] = str(r["valid_to"]) if r["valid_to"] else None
        r["remaining"] = max(0, (r["total_sessions"] or 0) - (r["used_sessions"] or 0))
    return rows


@router.post("/treatment-cards")
def create_treatment_card(data: TreatmentCardIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    if not _can_access_patient(user, data.patient_id):
        raise HTTPException(403, "无权为该患者创建疗程卡")
    cid = db.insert(
        "INSERT INTO treatment_cards (patient_id, case_id, title, total_sessions, used_sessions, "
        "valid_from, valid_to, note) VALUES (%s,%s,%s,%s,0,%s,%s,%s)",
        (data.patient_id, data.case_id, data.title, data.total_sessions,
         data.valid_from, data.valid_to, data.note))
    return {"ok": True, "card_id": cid}


# ==================== 随访提醒 ====================
@router.get("/followups")
def list_followups(status: str | None = None, user: dict = Depends(get_current_user)):
    cond, params = ["1=1"], []
    if _is_patient(user):
        cond.append("f.patient_id=%s")
        params.append(user["id"])
    elif _is_therapist(user):
        cond.append("f.coach_id=%s")
        params.append(user["id"])
    if status and status != "all":
        cond.append("f.status=%s")
        params.append(status)
    rows = db.query(
        f"SELECT f.*, p.nickname AS patient_name, c.nickname AS coach_name "
        f"FROM followups f JOIN users p ON p.id=f.patient_id "
        f"JOIN users c ON c.id=f.coach_id WHERE {' AND '.join(cond)} "
        f"ORDER BY f.status='pending' DESC, f.due_date DESC, f.id DESC LIMIT 100", tuple(params))
    for r in rows:
        r["due_date"] = str(r["due_date"]) if r["due_date"] else None
        r["sent_at"] = str(r["sent_at"]) if r["sent_at"] else None
        r["created_at"] = str(r["created_at"])
    return rows


@router.post("/followups")
def create_followup(data: FollowupIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    if not _can_access_patient(user, data.patient_id):
        raise HTTPException(403, "无权为该患者创建随访")
    fid = db.insert(
        "INSERT INTO followups (patient_id, coach_id, case_id, due_date, content) "
        "VALUES (%s,%s,%s,%s,%s)",
        (data.patient_id, user["id"], data.case_id, data.due_date or date.today(), data.content))
    return {"ok": True, "followup_id": fid}


@router.post("/followups/send-reminder")
def send_reminder(data: ReminderIn, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    """预警项一键发送提醒：写入随访记录并发送站内消息。"""
    if not _can_access_patient(user, data.patient_id):
        raise HTTPException(403, "无权提醒该患者")
    content = data.content or "康复治疗师提醒：请按时完成康复训练并记录康复日志。"
    from app.services.message_service import send_message
    send_message(user["id"], data.patient_id, "text", f"【康复随访】{content}")
    fid = db.insert(
        "INSERT INTO followups (patient_id, coach_id, due_date, content, status, sent_at) "
        "VALUES (%s,%s,%s,%s,'sent',NOW())",
        (data.patient_id, user["id"], date.today(), content))
    return {"ok": True, "followup_id": fid}


@router.post("/followups/{followup_id}/send")
def send_followup(followup_id: int, user: dict = Depends(require_role(THERAPIST, ADMIN))):
    row = db.query("SELECT * FROM followups WHERE id=%s", (followup_id,), one=True)
    if not row:
        raise HTTPException(404, "随访记录不存在")
    if user["role"] != ADMIN and row["coach_id"] != user["id"]:
        raise HTTPException(403, "无权发送该随访")
    from app.services.message_service import send_message
    send_message(row["coach_id"], row["patient_id"], "text", f"【康复随访】{row['content']}")
    db.execute("UPDATE followups SET status='sent', sent_at=NOW() WHERE id=%s", (followup_id,))
    return {"ok": True}


# ==================== 康复报告 ====================
@router.get("/report")
def rehab_report(patient_id: int | None = None, case_id: int | None = None,
                 user: dict = Depends(get_current_user)):
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者报告")
    patient = db.query(
        "SELECT id, username, nickname, gender, phone, created_at FROM users WHERE id=%s",
        (pid,), one=True)
    if case_id:
        case = db.query("SELECT * FROM rehab_cases WHERE id=%s AND patient_id=%s",
                        (case_id, pid), one=True)
    else:
        case = db.query("SELECT * FROM rehab_cases WHERE patient_id=%s "
                        "ORDER BY (status='active') DESC, id DESC LIMIT 1", (pid,), one=True)
    cond, params = "patient_id=%s", [pid]
    if case_id:
        cond += " AND case_id=%s"
        params.append(case_id)
    assessments = db.query(
        f"SELECT * FROM rehab_assessments WHERE {cond} ORDER BY assess_date, id", tuple(params))
    for a in assessments:
        for k in ("rom_json", "mmt_json"):
            if a.get(k):
                try:
                    a[k.replace("_json", "")] = json.loads(a[k])
                except Exception:
                    a[k.replace("_json", "")] = {}
    plans = db.query(
        "SELECT id, title, start_date, end_date FROM rehab_programs "
        "WHERE student_id=%s AND status='active' ORDER BY start_date DESC", (pid,))
    for p in plans:
        p["start_date"], p["end_date"] = str(p["start_date"]), str(p["end_date"])
    cards = list_treatment_cards(pid, user)
    appts = db.query(
        "SELECT a.*, c.nickname AS coach_name FROM appointments a "
        "JOIN users c ON c.id=a.coach_id WHERE a.patient_id=%s AND a.status='booked' "
        "ORDER BY a.appt_date, a.start_time LIMIT 10", (pid,))
    for a in appts:
        a["appt_date"] = str(a["appt_date"])
    screening = db.query(
        "SELECT * FROM rehab_screenings WHERE patient_id=%s ORDER BY id DESC LIMIT 1",
        (pid,), one=True)
    logs = db.query(
        "SELECT checkin_date, duration_min, intensity, vas_before, vas_after FROM rehab_logs "
        "WHERE user_id=%s ORDER BY checkin_date DESC LIMIT 14", (pid,))
    for r in logs:
        r["checkin_date"] = str(r["checkin_date"])

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "patient": {**patient, "created_at": str(patient["created_at"])} if patient else {},
        "case": {**case, "onset_date": str(case["onset_date"]) if case and case["onset_date"] else None,
                 "created_at": str(case["created_at"])} if case else None,
        "assessments": [{**a, "assess_date": str(a["assess_date"])} for a in assessments],
        "first_assessment": (dict(assessments[0], assess_date=str(assessments[0]["assess_date"]))
                             if assessments else None),
        "latest_assessment": (dict(assessments[-1], assess_date=str(assessments[-1]["assess_date"]))
                              if assessments else None),
        "adherence": _adherence_stats(pid),
        "plans": plans,
        "treatment_cards": cards,
        "appointments": appts,
        "screening": _screening_out(screening) if screening else None,
        "recent_logs": logs,
    }


# ==================== 评估 → 动作推荐 ====================
BODY_PART_KEYWORDS = {
    "肩部": ["肩", "肩袖", "冈上", "三角肌", "冻结肩", "肩周", "锁骨"],
    "肘腕": ["肘", "腕", "网球肘", "肱骨外上髁", "腕管", "手指", "腱鞘"],
    "颈腰椎": ["颈", "腰", "椎", "椎间盘", "坐骨神经", "颈椎", "腰椎"],
    "胸背": ["胸椎", "胸廓", "胸部", "背部", "腰背", "肩胛", "肋骨", "背肌"],
    "核心躯干": ["核心", "躯干", "腹部", "骨盆", "产后"],
    "髋部": ["髋", "臀部", "髂", "股骨", "梨状肌"],
    "膝部": ["膝", "半月板", "前交叉", "后交叉", "ACL", "PCL", "髌", "腘"],
    "踝足": ["踝", "足踝", "足底", "足弓", "跟腱", "崴脚", "扭伤", "跖"],
    "平衡步态": ["平衡", "步态", "本体感觉", "共济", "眩晕", "前庭", "跌倒"],
    "心肺全身": ["心肺", "耐力", "全身", "体适能", "气促"],
}

DIFF_LABEL = {1: "早期", 2: "中期", 3: "后期"}

# 康复阶段对应可执行的难度区间
STAGE_DIFF = {
    "急性期": {1},
    "恢复期": {1, 2},
    "强化期": {2, 3},
    "维持期": {2, 3},
}


@router.get("/exercise-recommendations")
def exercise_recommendations(patient_id: int | None = None, case_id: int | None = None,
                             limit: int = 8, user: dict = Depends(get_current_user)):
    """按康复档案 + 最新评估（部位 / 疼痛VAS / 阶段）推荐动作，供评估页与方案编排使用。"""
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者推荐动作")
    limit = min(max(limit, 1), 12)

    if case_id:
        case = db.query("SELECT * FROM rehab_cases WHERE id=%s AND patient_id=%s",
                        (case_id, pid), one=True)
        assessment = db.query(
            "SELECT * FROM rehab_assessments WHERE patient_id=%s AND case_id=%s "
            "ORDER BY assess_date DESC, id DESC LIMIT 1", (pid, case_id), one=True)
    else:
        case = db.query("SELECT * FROM rehab_cases WHERE patient_id=%s "
                        "ORDER BY (status='active') DESC, id DESC LIMIT 1", (pid,), one=True)
        assessment = db.query(
            "SELECT * FROM rehab_assessments WHERE patient_id=%s "
            "ORDER BY assess_date DESC, id DESC LIMIT 1", (pid,), one=True)

    text_parts = []
    if case:
        text_parts += [case.get("condition_name") or "", case.get("condition_type") or "",
                       case.get("chief_complaint") or "", case.get("diagnosis") or ""]
    if assessment:
        text_parts.append(str(assessment.get("rom_json") or ""))
        text_parts.append(str(assessment.get("mmt_json") or ""))
    text = " ".join(text_parts)

    matched = [cat for cat, kws in BODY_PART_KEYWORDS.items() if any(k in text for k in kws)]

    stage = (case or {}).get("stage") or "恢复期"
    allowed = set(STAGE_DIFF.get(stage, {1, 2}))
    vas = assessment.get("pain_vas") if assessment else None
    note = ""
    if vas is not None:
        if vas >= 7:
            allowed &= {1}
            note = f"当前疼痛 VAS {vas} 分偏高，仅推荐早期低负荷动作，建议先控制疼痛再逐步加量。"
        elif vas >= 4:
            allowed &= {1, 2}
            note = f"当前疼痛 VAS {vas} 分，推荐早期/中期动作，避免高负荷训练。"
    if not allowed:
        allowed = {1}

    def fetch(cats, diffs):
        if not cats or not diffs:
            return []
        cph = ",".join(["%s"] * len(cats))
        dph = ",".join(["%s"] * len(diffs))
        sql = (f"SELECT id, name, category, equipment, difficulty, intro, default_sets, "
               f"default_reps, default_weight, contraindications, alternatives FROM rehab_exercises "
               f"WHERE is_custom=0 AND category IN ({cph}) AND difficulty IN ({dph}) "
               f"ORDER BY sort_order, difficulty, name")
        return db.query(sql, tuple(cats) + tuple(sorted(diffs)))

    rows = fetch(matched, allowed)
    seen = {r["id"] for r in rows}
    if len(rows) < limit:
        supplement = [c for c in ("核心躯干", "平衡步态", "心肺全身") if c not in matched]
        for r in fetch(supplement, allowed):
            if r["id"] not in seen:
                rows.append(r)
                seen.add(r["id"])

    items = []
    for r in rows[:limit]:
        is_match = r["category"] in matched
        label = DIFF_LABEL.get(r["difficulty"], "")
        reason = (f"对应{r['category']} · {label}" if is_match
                  else f"{r['category']}基础稳定训练 · {label}")
        if vas is not None:
            reason += f"（评估 VAS {vas}）"
        items.append({**r, "reason": reason, "matched": is_match})

    return {
        "basis": {
            "case_id": case["id"] if case else None,
            "condition_name": case["condition_name"] if case else "",
            "stage": stage,
            "pain_vas": vas,
            "assess_date": str(assessment["assess_date"]) if assessment else None,
            "matched_categories": matched,
            "difficulty_labels": [DIFF_LABEL[d] for d in sorted(allowed)],
            "note": note,
        },
        "items": items,
    }


# ==================== 中医体质辨识 ====================
class TcmIn(BaseModel):
    scores: dict


@router.get("/tcm/latest")
def tcm_latest(patient_id: int | None = None, user: dict = Depends(get_current_user)):
    import json
    pid = patient_id or user["id"]
    if not _can_access_patient(user, pid):
        raise HTTPException(403, "无权查看该患者体质数据")
    row = db.query("SELECT * FROM tcm_constitutions WHERE patient_id=%s ORDER BY id DESC LIMIT 1",
                   (pid,), one=True)
    if not row:
        return {"has_data": False}
    try:
        row["scores"] = json.loads(row.get("scores_json") or "{}")
    except Exception:
        row["scores"] = {}
    row["has_data"] = True
    return row


@router.post("/tcm/assess")
def tcm_assess(data: TcmIn, user: dict = Depends(get_current_user)):
    """提交九种体质问卷得分（0-100），计算主体质并给出康复调理建议。"""
    import json
    scores = {t: int(data.scores.get(t, 0)) for t in TCM_TYPES}
    # 平和质为基准，其余体质取最高分；非平和体质 >= 60 判定为"是"，40-59 为"倾向"
    non_balanced = {t: s for t, s in scores.items() if t != "平和质"}
    primary, top = max(non_balanced.items(), key=lambda x: x[1])
    if top < 40 or scores.get("平和质", 0) >= top:
        primary = "平和质"
    advice = TCM_ADVICE.get(primary, "")
    if top >= 60:
        level = "为"
    elif top >= 40:
        level = "倾向为"
    else:
        level = "基本属于"
    full = f"辨识结果：{level}{primary}（最高得分 {top}）。{advice}"
    db.execute("INSERT INTO tcm_constitutions (patient_id, primary_type, scores_json, advice) VALUES (%s,%s,%s,%s)",
               (user["id"], primary, json.dumps(scores, ensure_ascii=False), full))
    return {"ok": True, "primary_type": primary, "scores": scores, "advice": full}
