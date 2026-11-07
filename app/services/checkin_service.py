from datetime import date, datetime, timedelta

from app.database import db
from app.models.schemas import CheckinIn
from app.services import achievement_service
from app.services.ws_manager import notify


def _consecutive_run(dates: list) -> int:
    longest = 0
    current = 0
    prev = None
    for d in dates:
        if prev is not None and (d - prev).days == 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        prev = d
    return longest


def recompute_streak(user_id: int) -> dict:
    rows = db.query(
        "SELECT checkin_date FROM rehab_logs WHERE user_id = %s ORDER BY checkin_date",
        (user_id,),
    )
    dates = [r["checkin_date"] for r in rows]
    date_set = set(dates)

    today = date.today()
    cursor = today if today in date_set else today - timedelta(days=1)
    current = 0
    while cursor in date_set:
        current += 1
        cursor -= timedelta(days=1)

    longest = _consecutive_run(dates)
    db.execute(
        "UPDATE users SET current_streak = %s, longest_streak = %s WHERE id = %s",
        (current, longest, user_id),
    )
    # 连续打卡奖励会员天数（P1-9）
    STREAK_REWARDS = {7: 3, 30: 7, 100: 30, 365: 365}  # 阈值: 奖励天数
    for threshold, reward in STREAK_REWARDS.items():
        if current >= threshold:
            got = db.query("SELECT id FROM streak_rewards WHERE user_id=%s AND streak_days=%s",
                           (user_id, threshold), one=True)
            if not got:
                db.execute("INSERT INTO streak_rewards (user_id, streak_days, reward_days) VALUES (%s,%s,%s)",
                           (user_id, threshold, reward))
                # 延长会员（延迟导入避免循环依赖）
                from app.routers.member import get_active_subscription
                sub = get_active_subscription(user_id)
                start = sub["expire_date"] if sub else today
                expire = start + timedelta(days=reward)
                db.execute("INSERT INTO subscriptions (user_id, plan, order_no, amount, status, start_date, expire_date, notes) "
                           "VALUES (%s,'monthly',%s,0,'paid',%s,%s,%s)",
                           (user_id, f"STREAK_{user_id}_{threshold}", start, expire,
                            f"连续打卡{threshold}天奖励{reward}天会员"))
    return {"current_streak": current, "longest_streak": longest}


def create_checkin(user_id: int, data: CheckinIn) -> tuple[dict | None, str]:
    if data.checkin_date > date.today():
        return None, "打卡日期不能晚于今天"

    existing = db.query(
        "SELECT id FROM rehab_logs WHERE user_id = %s AND checkin_date = %s",
        (user_id, data.checkin_date),
        one=True,
    )
    if existing:
        return None, "当日已打卡，请勿重复提交"

    if data.plan_id:
        plan = db.query(
            "SELECT id, coach_id FROM rehab_programs WHERE id = %s AND student_id = %s",
            (data.plan_id, user_id),
            one=True,
        )
        if not plan:
            return None, "关联的训练计划不存在"

    train_volume = 0
    for d in data.details:
        train_volume += round((d.sets or 0) * (d.reps or 0) * (d.weight or 0))

    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO rehab_logs (user_id, checkin_date, content, plan_id, train_volume, "
            "duration_min, intensity, vas_before, vas_after) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (user_id, data.checkin_date, data.content, data.plan_id,
             train_volume, data.duration_min, data.intensity,
             data.vas_before, data.vas_after),
        )
        checkin_id = cursor.lastrowid
        if data.media_paths:
            cursor.executemany(
                "INSERT INTO rehab_log_media (checkin_id, file_path, media_type) VALUES (%s,%s,%s)",
                [(checkin_id, p, "video" if p.rsplit(".", 1)[-1] in
                  ("mp4", "mov", "webm", "avi", "mkv") else "image") for p in data.media_paths],
            )
        if data.details:
            cursor.executemany(
                "INSERT INTO rehab_log_details (checkin_id, exercise_name, sets, reps, weight, "
                "rpe, heart_rate, rest_sec) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [(checkin_id, d.exercise_name, d.sets, d.reps, d.weight, d.rpe,
                  d.heart_rate, d.rest_sec) for d in data.details],
            )

    streak = recompute_streak(user_id)
    new_badges = achievement_service.check_and_unlock(user_id)

    # 练前/练后疼痛变化提示：练后 VAS >=7 或上升 >=2 分，提示减量并告知治疗师
    vas_alert = ""
    if data.vas_before is not None and data.vas_after is not None:
        delta = data.vas_after - data.vas_before
        if data.vas_after >= 7 or delta >= 2:
            vas_alert = (f"练后疼痛 VAS {data.vas_after} 分（练前 {data.vas_before} 分）明显升高，"
                         f"建议本次减量或暂停，并及时告知康复治疗师。")
        elif delta >= 1:
            vas_alert = (f"练后疼痛略有升高（{data.vas_before}→{data.vas_after}），"
                         f"下次训练建议降低强度并持续观察。")

    coach_ids = [r["coach_id"] for r in db.query(
        "SELECT DISTINCT coach_id FROM rehab_programs WHERE student_id = %s", (user_id,))]
    for coach_id in coach_ids:
        notify(coach_id, {"type": "checkin", "student_id": user_id,
                          "message": "学员已完成今日打卡"})

    return {
        "checkin_id": checkin_id,
        "train_volume": train_volume,
        "streak": streak,
        "new_badges": new_badges,
        "vas_alert": vas_alert,
    }, ""


def month_heatmap(user_id: int, year: int, month: int) -> dict:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    rows = db.query(
        "SELECT checkin_date, intensity, train_volume, duration_min, is_makeup "
        "FROM rehab_logs WHERE user_id = %s AND checkin_date >= %s AND checkin_date < %s "
        "ORDER BY checkin_date",
        (user_id, start, end),
    )
    days = []
    total_volume = 0
    total_duration = 0
    for r in rows:
        total_volume += r["train_volume"] or 0
        total_duration += r["duration_min"] or 0
        days.append({
            "date": r["checkin_date"].isoformat(),
            "intensity": r["intensity"],
            "volume": r["train_volume"],
            "duration": r["duration_min"],
            "is_makeup": bool(r["is_makeup"]),
        })
    return {
        "year": year, "month": month, "days": days,
        "checkin_days": len(days),
        "total_volume": total_volume,
        "total_duration": total_duration,
    }


def get_checkin_detail(user_id: int, checkin_date) -> dict | None:
    checkin = db.query("SELECT * FROM rehab_logs WHERE user_id = %s AND checkin_date = %s",
                       (user_id, checkin_date), one=True)
    if not checkin:
        return None
    media = db.query("SELECT file_path, media_type FROM rehab_log_media WHERE checkin_id = %s",
                     (checkin["id"],))
    details = db.query("SELECT * FROM rehab_log_details WHERE checkin_id = %s ORDER BY id",
                       (checkin["id"],))
    comments = db.query(
        "SELECT c.id, c.content, c.voice_path, c.created_at, u.nickname AS coach_name, u.avatar "
        "FROM rehab_log_comments c JOIN users u ON u.id = c.coach_id "
        "WHERE c.checkin_id = %s ORDER BY c.created_at",
        (checkin["id"],))
    return {
        "checkin": {**checkin, "checkin_date": checkin["checkin_date"].isoformat(),
                    "created_at": str(checkin["created_at"])},
        "media": media,
        "details": details,
        "comments": [{**c, "created_at": str(c["created_at"])} for c in comments],
    }


def delete_checkin(user_id: int, checkin_date) -> tuple[bool, str]:
    row = db.query("SELECT id, is_makeup, created_at FROM rehab_logs "
                   "WHERE user_id = %s AND checkin_date = %s", (user_id, checkin_date), one=True)
    if not row:
        return False, "打卡记录不存在"
    if row["is_makeup"]:
        return False, "补签记录不可删除"
    if row["created_at"].date() != date.today():
        return False, "仅可删除当日打卡"
    db.execute("DELETE FROM rehab_logs WHERE id = %s", (row["id"],))
    recompute_streak(user_id)
    return True, ""


def apply_makeup(user_id: int, makeup_date) -> None:
    """补签审批通过后补写打卡记录。"""
    db.execute(
        "INSERT INTO rehab_logs (user_id, checkin_date, content, intensity, is_makeup) "
        "VALUES (%s,%s,%s,1,1) ON DUPLICATE KEY UPDATE is_makeup = 1",
        (user_id, makeup_date, "补签打卡（教练已审批）"),
    )
    recompute_streak(user_id)
    achievement_service.check_and_unlock(user_id)


def checkin_streak_info(user_id: int) -> dict:
    user = db.query("SELECT current_streak, longest_streak FROM users WHERE id = %s",
                    (user_id,), one=True)
    total = db.query("SELECT COUNT(*) AS cnt FROM rehab_logs WHERE user_id = %s",
                     (user_id,), one=True)
    today_row = db.query("SELECT id FROM rehab_logs WHERE user_id = %s AND checkin_date = %s",
                         (user_id, date.today()), one=True)
    return {
        "current_streak": user["current_streak"],
        "longest_streak": user["longest_streak"],
        "total_days": total["cnt"],
        "checked_today": bool(today_row),
    }
