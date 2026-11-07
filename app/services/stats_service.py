from datetime import date, timedelta

from app.database import db
from app.redis_client import cache
from app.services import achievement_service
from app.utils.helpers import get_config_int, week_monday


def student_dashboard(user_id: int) -> dict:
    today = date.today()
    month_start = today.replace(day=1)

    streak = db.query("SELECT current_streak, longest_streak FROM users WHERE id = %s",
                      (user_id,), one=True)
    month = db.query(
        "SELECT COUNT(*) AS days, COALESCE(SUM(train_volume),0) AS volume, "
        "COALESCE(SUM(duration_min),0) AS duration FROM rehab_logs "
        "WHERE user_id = %s AND checkin_date >= %s",
        (user_id, month_start), one=True)
    total = db.query(
        "SELECT COUNT(*) AS days, COALESCE(SUM(train_volume),0) AS volume "
        "FROM rehab_logs WHERE user_id = %s", (user_id,), one=True)
    today_row = db.query("SELECT id FROM rehab_logs WHERE user_id = %s AND checkin_date = %s",
                         (user_id, today), one=True)

    week_start = week_monday()
    week_rows = db.query(
        "SELECT checkin_date, train_volume, duration_min FROM rehab_logs "
        "WHERE user_id = %s AND checkin_date >= %s ORDER BY checkin_date",
        (user_id, week_start))
    week_map = {r["checkin_date"].isoformat(): r for r in week_rows}
    week_series = []
    for i in range(7):
        d = (week_start + timedelta(days=i))
        r = week_map.get(d.isoformat())
        week_series.append({
            "date": d.isoformat(),
            "volume": r["train_volume"] if r else 0,
            "duration": r["duration_min"] if r else 0,
        })

    body = db.query(
        "SELECT record_date, weight, body_fat FROM body_records "
        "WHERE user_id = %s AND record_date >= %s ORDER BY record_date",
        (user_id, today - timedelta(days=90)))
    weight_change = 0
    if body:
        first, latest = body[0], body[-1]
        if first["weight"] and latest["weight"]:
            weight_change = round(float(latest["weight"]) - float(first["weight"]), 1)

    plans = db.query(
        "SELECT id, title, start_date, end_date FROM rehab_programs "
        "WHERE student_id = %s AND status = 'active' AND start_date <= %s AND end_date >= %s "
        "ORDER BY start_date DESC LIMIT 1",
        (user_id, today, today), one=True)
    today_plan_items = []
    if plans:
        today_plan_items = db.query(
            "SELECT exercise_name, sets, reps, weight_suggest, rest_sec, note "
            "FROM program_items WHERE plan_id = %s AND day_date = %s ORDER BY sort_order, id",
            (plans["id"], today))

    return {
        "checked_today": bool(today_row),
        "current_streak": streak["current_streak"],
        "longest_streak": streak["longest_streak"],
        "month_days": month["days"],
        "month_volume": month["volume"],
        "month_duration": month["duration"],
        "total_days": total["days"],
        "total_volume": total["volume"],
        "weight_change": weight_change,
        "week_series": week_series,
        "body_series": [{"date": r["record_date"].isoformat(), "weight": float(r["weight"]) if r["weight"] else None,
                         "body_fat": float(r["body_fat"]) if r["body_fat"] else None} for r in body],
        "recent_badges": achievement_service.recent_achievements(user_id),
        "today_plan": {"id": plans["id"], "title": plans["title"],
                       "items": today_plan_items} if plans else None,
    }


def body_trend(user_id: int, days: int = 90) -> list:
    rows = db.query(
        "SELECT * FROM body_records WHERE user_id = %s AND record_date >= %s "
        "ORDER BY record_date, id",
        (user_id, date.today() - timedelta(days=days)))
    return [{**r, "record_date": r["record_date"].isoformat(),
             "created_at": str(r["created_at"])} for r in rows]


def _urged_today_ids(coach_id: int) -> set:
    """今天已发过催打卡消息的学员 id 集合。"""
    rows = db.query(
        "SELECT DISTINCT receiver_id FROM messages "
        "WHERE sender_id = %s AND content LIKE %s AND created_at >= CURDATE()",
        (coach_id, "【催打卡】%"))
    return {r["receiver_id"] for r in rows}


def coach_dashboard(coach_id: int) -> dict:
    today = date.today()
    student_ids = [r["student_id"] for r in db.query(
        "SELECT DISTINCT student_id FROM rehab_programs WHERE coach_id = %s", (coach_id,))]
    total_students = len(student_ids)

    active_week = 0
    if student_ids:
        marks = ",".join(["%s"] * len(student_ids))
        active_week = db.query(
            f"SELECT COUNT(DISTINCT user_id) AS cnt FROM rehab_logs "
            f"WHERE user_id IN ({marks}) AND checkin_date >= %s",
            tuple(student_ids) + (today - timedelta(days=7),), one=True)["cnt"]

    trend = []
    trend_map = {}
    if student_ids:
        marks = ",".join(["%s"] * len(student_ids))
        rows = db.query(
            f"SELECT checkin_date, COUNT(DISTINCT user_id) AS cnt FROM rehab_logs "
            f"WHERE user_id IN ({marks}) AND checkin_date >= %s GROUP BY checkin_date",
            tuple(student_ids) + (today - timedelta(days=29),))
        trend_map = {r["checkin_date"]: r["cnt"] for r in rows}
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        checked = trend_map.get(d, 0)
        trend.append({"date": d.isoformat(), "checked": checked,
                      "rate": round(checked / total_students * 100, 1) if total_students else 0})

    avg_rate = round(sum(t["rate"] for t in trend) / len(trend), 1) if trend else 0

    low_rate = []
    if student_ids:
        marks = ",".join(["%s"] * len(student_ids))
        rows = db.query(
            f"SELECT u.id, u.nickname, u.avatar, u.current_streak, "
            f"(SELECT COUNT(*) FROM rehab_logs c WHERE c.user_id = u.id AND c.checkin_date >= %s) AS days_30 "
            f"FROM users u WHERE u.id IN ({marks})",
            (today - timedelta(days=30),) + tuple(student_ids))
        urged = _urged_today_ids(coach_id)
        for r in rows:
            rate = round(r["days_30"] / 30 * 100, 1)
            if rate < 50:
                low_rate.append({**r, "rate_30": rate, "urged_today": r["id"] in urged})

    active_plans = db.query(
        "SELECT COUNT(*) AS cnt FROM rehab_programs WHERE coach_id = %s AND status='active' "
        "AND start_date <= %s AND end_date >= %s",
        (coach_id, today, today), one=True)["cnt"]
    pending_makeups = db.query(
        "SELECT COUNT(*) AS cnt FROM makeup_requests m JOIN rehab_programs p "
        "ON p.student_id = m.user_id WHERE p.coach_id = %s AND m.status = 'pending'",
        (coach_id,), one=True)["cnt"]

    return {
        "total_students": total_students,
        "active_week": active_week,
        "avg_rate_30": avg_rate,
        "checkin_trend": trend,
        "low_rate_students": sorted(low_rate, key=lambda x: x["rate_30"])[:10],
        "active_plans": active_plans,
        "pending_makeups": pending_makeups,
    }


def coach_students(coach_id: int, filter_status: str = None) -> list:
    today = date.today()
    since = today - timedelta(days=30)
    rows = db.query(
        "SELECT DISTINCT u.id, u.nickname, u.avatar, u.phone, u.current_streak, u.longest_streak, "
        "u.anonymous_rank, u.status, u.created_at, "
        "(SELECT COUNT(*) FROM rehab_logs c WHERE c.user_id = u.id AND c.checkin_date = %s) AS checked_today, "
        "(SELECT COUNT(*) FROM rehab_logs c WHERE c.user_id = u.id AND c.checkin_date >= %s) AS days_30, "
        "(SELECT COALESCE(SUM(c.train_volume),0) FROM rehab_logs c WHERE c.user_id = u.id AND c.checkin_date >= %s) AS volume_30, "
        "(SELECT b.weight FROM body_records b WHERE b.user_id = u.id "
        " ORDER BY b.record_date DESC, b.id DESC LIMIT 1) AS latest_weight "
        "FROM users u JOIN rehab_programs p ON p.student_id = u.id "
        "WHERE p.coach_id = %s ORDER BY u.current_streak DESC",
        (today, since, since, coach_id))
    students = []
    urged = _urged_today_ids(coach_id)
    for r in rows:
        rate_30 = round(r["days_30"] / 30 * 100, 1)
        students.append({**r, "created_at": str(r["created_at"]),
                         "checked_today": bool(r["checked_today"]),
                         "days_30": r["days_30"], "volume_30": r["volume_30"],
                         "rate_30": rate_30,
                         "latest_weight": float(r["latest_weight"]) if r["latest_weight"] else None,
                         "urged_today": r["id"] in urged})

    if filter_status == "checked":
        students = [s for s in students if s["checked_today"]]
    elif filter_status == "unchecked":
        students = [s for s in students if not s["checked_today"]]
    elif filter_status == "low":
        students = [s for s in students if s["rate_30"] < 50]
    return students


def admin_overview() -> dict:
    today = date.today()
    users = db.query(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN role='student' THEN 1 ELSE 0 END) AS students, "
        "SUM(CASE WHEN role='coach' THEN 1 ELSE 0 END) AS coaches "
        "FROM users WHERE status = 1", one=True)
    dau = db.query(
        "SELECT COUNT(DISTINCT CASE WHEN last_login_at >= %s THEN id END) AS cnt FROM users",
        (today.strftime("%Y-%m-%d 00:00:00"),), one=True)["cnt"]
    checkins_today = db.query("SELECT COUNT(*) AS cnt FROM rehab_logs WHERE checkin_date = %s",
                              (today,), one=True)["cnt"]
    active_students = db.query(
        "SELECT COUNT(DISTINCT user_id) AS cnt FROM rehab_logs WHERE checkin_date >= %s",
        (today - timedelta(days=30),), one=True)["cnt"]
    pending_coach_reviews = db.query(
        "SELECT COUNT(*) AS cnt FROM therapist_profiles WHERE review_status = 'pending'",
        one=True)["cnt"]
    msg_count = db.query("SELECT COUNT(*) AS cnt FROM messages "
                         "WHERE created_at >= %s", (today - timedelta(days=30),), one=True)["cnt"]

    return {
        "total_users": users["total"], "students": users["students"], "coaches": users["coaches"],
        "dau": dau, "mau": active_students,
        "checkins_today": checkins_today,
        "checkin_rate": round(checkins_today / users["students"] * 100, 1) if users["students"] else 0,
        "pending_coach_reviews": pending_coach_reviews,
        "messages_30d": msg_count,
    }


def admin_trend(days: int = 30) -> list:
    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        next_d = d + timedelta(days=1)
        new_users = db.query(
            "SELECT COUNT(*) AS cnt FROM users WHERE created_at >= %s AND created_at < %s",
            (d.strftime("%Y-%m-%d 00:00:00"), next_d.strftime("%Y-%m-%d 00:00:00")),
            one=True)["cnt"]
        checkins = db.query("SELECT COUNT(*) AS cnt FROM rehab_logs WHERE checkin_date = %s",
                            (d,), one=True)["cnt"]
        result.append({"date": d.isoformat(), "new_users": new_users,
                       "checkins": checkins})
    return result


def rankings(period: str = "week", metric: str = "days", limit: int = 50) -> list:
    """周/月排行榜：打卡天数或训练量，仅前 50 名，支持匿名。"""
    if period not in ("week", "month") or metric not in ("days", "volume"):
        raise ValueError("参数不合法")
    cache_key = f"rank:{period}:{metric}"
    refresh_sec = get_config_int("ranking_refresh_sec", 300)

    cached = cache.get(cache_key)
    if cached:
        import json
        try:
            return json.loads(cached)
        except (TypeError, ValueError):
            pass

    today = date.today()
    start = week_monday() if period == "week" else today.replace(day=1)
    if metric == "days":
        rows = db.query(
            "SELECT c.user_id, COUNT(*) AS score, u.nickname, u.avatar, u.anonymous_rank "
            "FROM rehab_logs c JOIN users u ON u.id = c.user_id "
            "WHERE c.checkin_date >= %s AND u.status = 1 "
            "GROUP BY c.user_id, u.nickname, u.avatar, u.anonymous_rank "
            "ORDER BY score DESC, c.user_id LIMIT %s",
            (start, limit))
    else:
        rows = db.query(
            "SELECT c.user_id, COALESCE(SUM(c.train_volume),0) AS score, u.nickname, u.avatar, "
            "u.anonymous_rank FROM rehab_logs c JOIN users u ON u.id = c.user_id "
            "WHERE c.checkin_date >= %s AND u.status = 1 "
            "GROUP BY c.user_id, u.nickname, u.avatar, u.anonymous_rank "
            "ORDER BY score DESC, c.user_id LIMIT %s",
            (start, limit))

    import json
    data = [{
        "rank": idx + 1,
        "user_id": r["user_id"],
        "nickname": "匿名用户" if r["anonymous_rank"] else r["nickname"],
        "avatar": "" if r["anonymous_rank"] else r["avatar"],
        "score": float(r["score"]),
    } for idx, r in enumerate(rows)]
    cache.set(cache_key, json.dumps(data, ensure_ascii=False), ttl=refresh_sec)
    return data
