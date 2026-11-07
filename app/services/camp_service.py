"""训练营（营期）业务逻辑：创建/成员/排行/看板/结营报告/营内群聊。"""
import json
import secrets
from datetime import date, timedelta

from app.database import db
from app.services import message_service
from app.services.ws_manager import manager

INVITE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 排除 0/O/1/I 等易混淆字符
CAMP_STATUS_LABEL = {"draft": "筹备中", "recruiting": "招生中", "ongoing": "进行中", "ended": "已结营"}


def gen_invite_code() -> str:
    while True:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        if not db.query("SELECT id FROM rehab_camps WHERE invite_code = %s", (code,), one=True):
            return code


def serialize_camp(camp: dict) -> dict:
    days_total = (camp["end_date"] - camp["start_date"]).days + 1
    today = date.today()
    days_left = max(0, (camp["end_date"] - today).days)
    return {**camp,
            "status_label": CAMP_STATUS_LABEL.get(camp["status"], camp["status"]),
            "start_date": camp["start_date"].isoformat(),
            "end_date": camp["end_date"].isoformat(),
            "days_total": days_total,
            "days_left": days_left,
            "created_at": str(camp["created_at"])}


def get_camp(camp_id: int) -> dict | None:
    return db.query(
        "SELECT c.*, u.nickname AS coach_name, u.avatar AS coach_avatar "
        "FROM rehab_camps c JOIN users u ON u.id = c.coach_id WHERE c.id = %s",
        (camp_id,), one=True)


def member_ids(camp_id: int, only_active: bool = True) -> list:
    sql = "SELECT user_id FROM rehab_camp_members WHERE camp_id = %s"
    if only_active:
        sql += " AND status = 'active'"
    return [r["user_id"] for r in db.query(sql, (camp_id,))]


def is_member(camp_id: int, user_id: int) -> bool:
    return db.query(
        "SELECT id FROM rehab_camp_members WHERE camp_id = %s AND user_id = %s AND status = 'active'",
        (camp_id, user_id), one=True) is not None


def create_camp(coach_id: int, data) -> int:
    if data.end_date < data.start_date:
        raise ValueError("结束日期不能早于开始日期")
    return db.insert(
        "INSERT INTO rehab_camps (coach_id, title, description, start_date, end_date, capacity, invite_code) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (coach_id, data.title, data.description, data.start_date, data.end_date,
         data.capacity, gen_invite_code()))


def update_camp(coach_id: int, camp_id: int, data) -> tuple[bool, str]:
    camp = db.query("SELECT id FROM rehab_camps WHERE id = %s AND coach_id = %s",
                    (camp_id, coach_id), one=True)
    if not camp:
        return False, "营期不存在或无权操作"
    if data.end_date < data.start_date:
        return False, "结束日期不能早于开始日期"
    db.execute(
        "UPDATE rehab_camps SET title=%s, description=%s, start_date=%s, end_date=%s, capacity=%s WHERE id=%s",
        (data.title, data.description, data.start_date, data.end_date, data.capacity, camp_id))
    return True, ""


STATUS_FLOW = {"draft": "recruiting", "recruiting": "ongoing", "ongoing": "ended"}


def transition_status(coach_id: int, camp_id: int, action: str) -> tuple[bool, str]:
    camp = db.query("SELECT * FROM rehab_camps WHERE id = %s AND coach_id = %s",
                    (camp_id, coach_id), one=True)
    if not camp:
        return False, "营期不存在或无权操作"
    target = "ended" if action == "finish" else STATUS_FLOW.get(camp["status"])
    if target is None:
        return False, "当前状态不支持该操作"
    if camp["status"] == target:
        return False, f"营期已是{CAMP_STATUS_LABEL[target]}状态"

    if target == "ended":
        report = json.dumps(build_camp_report(camp_id), ensure_ascii=False)
        db.execute("UPDATE rehab_camps SET status=%s, report_json=%s WHERE id=%s",
                   (target, report, camp_id))
    else:
        db.execute("UPDATE rehab_camps SET status=%s WHERE id=%s", (target, camp_id))
    _system_camp_message(camp_id, {"draft": "开始招生", "recruiting": "正式开营",
                                    "ongoing": "结营"}.get(camp["status"], "状态变更"))
    if target == "ended":
        for uid in member_ids(camp_id):
            message_service.system_notify(uid, f"【{camp['title']}】已结营，快去查看你的结营报告！")
    elif target == "ongoing":
        for uid in member_ids(camp_id):
            message_service.system_notify(uid, f"【{camp['title']}】今天正式开营啦，跟着计划练起来！")
    return True, ""


def add_member(coach_id: int, camp_id: int, user_id: int) -> tuple[bool, str]:
    camp = db.query("SELECT * FROM rehab_camps WHERE id = %s AND coach_id = %s",
                    (camp_id, coach_id), one=True)
    if not camp:
        return False, "营期不存在或无权操作"
    student = db.query("SELECT id, nickname, role, status FROM users WHERE id = %s",
                       (user_id,), one=True)
    if not student or student["role"] != "student" or student["status"] != 1:
        return False, "学员不存在或不可用"
    if len(member_ids(camp_id)) >= camp["capacity"]:
        return False, f"营期人数已满（上限 {camp['capacity']} 人）"
    existing = db.query("SELECT id, status FROM rehab_camp_members WHERE camp_id = %s AND user_id = %s",
                        (camp_id, user_id), one=True)
    if existing:
        if existing["status"] == "active":
            return False, "该学员已在营中"
        db.execute("UPDATE rehab_camp_members SET status='active', joined_at=NOW() WHERE id=%s",
                   (existing["id"],))
    else:
        db.execute("INSERT INTO rehab_camp_members (camp_id, user_id) VALUES (%s,%s)",
                   (camp_id, user_id))
    _system_camp_message(camp_id, f"{student['nickname']} 加入了训练营")
    message_service.system_notify(user_id, f"你已加入【{camp['title']}】，开营后记得每天打卡！")
    return True, ""


def join_by_code(user_id: int, invite_code: str) -> tuple[dict | None, str]:
    camp = db.query("SELECT * FROM rehab_camps WHERE invite_code = %s", (invite_code.strip().upper(),),
                    one=True)
    if not camp:
        return None, "邀请码无效"
    if camp["status"] not in ("recruiting", "ongoing"):
        return None, "该营期当前不可加入"
    if camp["end_date"] < date.today():
        return None, "该营期已结束"
    # P1-7 付费训练营：检查是否已付费
    if camp.get("is_paid") and camp["price"] and camp["price"] > 0:
        paid = db.query("SELECT id FROM subscriptions WHERE user_id=%s AND bootcamp_id=%s AND status='paid'",
                        (user_id, camp["id"]), one=True)
        if not paid:
            return None, f"该营期为付费营，需先支付 ¥{camp['price']} 才能加入"
    if len(member_ids(camp["id"])) >= camp["capacity"]:
        return None, f"营期人数已满（上限 {camp['capacity']} 人）"
    existing = db.query("SELECT id, status FROM rehab_camp_members WHERE camp_id = %s AND user_id = %s",
                        (camp["id"], user_id), one=True)
    if existing:
        if existing["status"] == "active":
            return None, "你已在该营中"
        db.execute("UPDATE rehab_camp_members SET status='active', joined_at=NOW() WHERE id=%s",
                   (existing["id"],))
    else:
        db.execute("INSERT INTO rehab_camp_members (camp_id, user_id) VALUES (%s,%s)",
                   (camp["id"], user_id))
    user = db.query("SELECT nickname FROM users WHERE id = %s", (user_id,), one=True)
    _system_camp_message(camp["id"], f"{user['nickname']} 加入了训练营")
    return serialize_camp(camp), ""


def remove_member(coach_id: int, camp_id: int, user_id: int) -> tuple[bool, str]:
    camp = db.query("SELECT id FROM rehab_camps WHERE id = %s AND coach_id = %s",
                    (camp_id, coach_id), one=True)
    if not camp:
        return False, "营期不存在或无权操作"
    affected = db.execute(
        "UPDATE rehab_camp_members SET status='quit' WHERE camp_id = %s AND user_id = %s AND status='active'",
        (camp_id, user_id))
    if not affected:
        return False, "该学员不在营中"
    user = db.query("SELECT nickname FROM users WHERE id = %s", (user_id,), one=True)
    _system_camp_message(camp_id, f"{user['nickname']} 退出了训练营")
    return True, ""


def _camp_date_range(camp: dict) -> tuple:
    """统计窗口：营期起点 ~ min(营期终点, 今天)。"""
    return camp["start_date"], min(camp["end_date"], date.today())


def camp_leaderboard(camp_id: int, metric: str = "days", limit: int = 50) -> list:
    """营内排行榜：days=打卡天数 / volume=训练量。"""
    camp = db.query("SELECT * FROM rehab_camps WHERE id = %s", (camp_id,), one=True)
    if not camp:
        return []
    start, end = _camp_date_range(camp)
    agg = "COUNT(c.id)" if metric == "days" else "COALESCE(SUM(c.train_volume),0)"
    rows = db.query(
        f"SELECT cm.user_id, {agg} AS score, u.nickname, u.avatar, u.anonymous_rank, "
        f"u.current_streak FROM rehab_camp_members cm JOIN users u ON u.id = cm.user_id "
        f"LEFT JOIN rehab_logs c ON c.user_id = cm.user_id AND c.checkin_date BETWEEN %s AND %s "
        f"WHERE cm.camp_id = %s AND cm.status = 'active' "
        f"GROUP BY cm.user_id, u.nickname, u.avatar, u.anonymous_rank, u.current_streak "
        f"ORDER BY score DESC, u.current_streak DESC LIMIT %s",
        (start, end, camp_id, limit))
    return [{"rank": i + 1, "user_id": r["user_id"], "nickname": r["nickname"],
             "avatar": r["avatar"], "anonymous": bool(r["anonymous_rank"]),
             "score": int(r["score"]), "current_streak": r["current_streak"]}
            for i, r in enumerate(rows)]


def coach_camps(coach_id: int) -> list:
    camps = db.query(
        "SELECT c.*, u.nickname AS coach_name, u.avatar AS coach_avatar FROM rehab_camps c "
        "JOIN users u ON u.id = c.coach_id WHERE c.coach_id = %s ORDER BY c.created_at DESC",
        (coach_id,))
    result = []
    today = date.today()
    for camp in camps:
        data = serialize_camp(camp)
        active = member_ids(camp["id"])
        data["member_count"] = len(active)
        checked = 0
        if active and camp["start_date"] <= today <= camp["end_date"]:
            marks = ",".join(["%s"] * len(active))
            checked = db.query(
                f"SELECT COUNT(DISTINCT user_id) AS cnt FROM rehab_logs "
                f"WHERE user_id IN ({marks}) AND checkin_date = %s",
                tuple(active) + (today,), one=True)["cnt"]
        data["checked_today"] = checked
        result.append(data)
    return result


def my_camps(user_id: int) -> list:
    camps = db.query(
        "SELECT c.*, u.nickname AS coach_name, u.avatar AS coach_avatar FROM rehab_camp_members cm "
        "JOIN rehab_camps c ON c.id = cm.camp_id JOIN users u ON u.id = c.coach_id "
        "WHERE cm.user_id = %s AND cm.status = 'active' ORDER BY c.start_date DESC",
        (user_id,))
    result = []
    for camp in camps:
        data = serialize_camp(camp)
        data["member_count"] = len(member_ids(camp["id"]))
        data["my_rank"] = 0
        for row in camp_leaderboard(camp["id"]):
            if row["user_id"] == user_id:
                data["my_rank"] = row["rank"]
                break
        checked = db.query("SELECT id FROM rehab_logs WHERE user_id = %s AND checkin_date = %s",
                           (user_id, date.today()), one=True)
        data["checked_today"] = bool(checked)
        result.append(data)
    return result


def camp_detail(camp_id: int) -> dict | None:
    camp = get_camp(camp_id)
    if not camp:
        return None
    data = serialize_camp(camp)
    data["member_count"] = len(member_ids(camp_id))
    return data


def camp_members_detail(camp_id: int) -> list:
    """营员列表：含今日打卡、营内打卡天数、营内训练量、连续天数。"""
    camp = db.query("SELECT * FROM rehab_camps WHERE id = %s", (camp_id,), one=True)
    if not camp:
        return []
    start, end = _camp_date_range(camp)
    today = date.today()
    in_window = camp["start_date"] <= today <= camp["end_date"]
    rows = db.query(
        "SELECT u.id, u.nickname, u.avatar, u.phone, u.current_streak, u.longest_streak, "
        "(SELECT COUNT(*) FROM rehab_logs c WHERE c.user_id = u.id "
        "  AND c.checkin_date BETWEEN %s AND %s) AS camp_days, "
        "(SELECT COALESCE(SUM(c.train_volume),0) FROM rehab_logs c WHERE c.user_id = u.id "
        "  AND c.checkin_date BETWEEN %s AND %s) AS camp_volume, "
        "(SELECT id FROM rehab_logs c WHERE c.user_id = u.id AND c.checkin_date = %s) AS checked_today "
        "FROM rehab_camp_members cm JOIN users u ON u.id = cm.user_id "
        "WHERE cm.camp_id = %s AND cm.status = 'active' ORDER BY camp_days DESC, u.nickname",
        (start, end, start, end, today, camp_id))
    return [{**r, "camp_volume": int(r["camp_volume"]),
             "checked_today": r["checked_today"] is not None and in_window} for r in rows]


def generate_camp_plans(coach_id: int, camp_id: int, template_plan_id: int,
                        title: str) -> tuple[int, str]:
    """以模板计划为蓝本，为全体在营学员批量生成营期计划（日期平移到营期起点）。"""
    camp = db.query("SELECT * FROM rehab_camps WHERE id = %s AND coach_id = %s",
                    (camp_id, coach_id), one=True)
    if not camp:
        return 0, "营期不存在或无权操作"
    template = db.query("SELECT * FROM rehab_programs WHERE id = %s AND coach_id = %s",
                        (template_plan_id, coach_id), one=True)
    if not template:
        return 0, "模板计划不存在或不属于你"
    items = db.query("SELECT * FROM program_items WHERE plan_id = %s ORDER BY day_date, sort_order, id",
                     (template_plan_id,))
    if not items:
        return 0, "模板计划没有动作明细，请先完善"
    members = member_ids(camp_id)
    if not members:
        return 0, "营内暂无学员"

    offset = (camp["start_date"] - template["start_date"]).days
    created = 0
    with db.transaction() as cursor:
        for uid in members:
            cursor.execute(
                "INSERT INTO rehab_programs (coach_id, student_id, title, description, "
                "start_date, end_date, camp_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (coach_id, uid, title, template["description"],
                 camp["start_date"], camp["end_date"], camp_id))
            new_plan_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO program_items (plan_id, day_date, exercise_name, sets, reps, "
                "weight_suggest, rest_sec, note, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(new_plan_id, timedelta(days=offset) + i["day_date"], i["exercise_name"],
                  i["sets"], i["reps"], i["weight_suggest"], i["rest_sec"], i["note"],
                  i["sort_order"]) for i in items])
            created += 1
    _system_camp_message(camp_id, f"教练已发布营期训练计划【{title}】，去计划页查看")
    for uid in members:
        message_service.system_notify(uid, f"【{camp['title']}】训练计划已发布：{title}")
    return created, ""


def camp_checkin_trend(camp_id: int, days: int = 30) -> list:
    """营期每日打卡率趋势（营期开始日 ~ 今天）。"""
    camp = db.query("SELECT * FROM rehab_camps WHERE id = %s", (camp_id,), one=True)
    if not camp:
        return []
    members = member_ids(camp_id)
    if not members:
        return []
    marks = ",".join(["%s"] * len(members))
    today = date.today()
    start = max(camp["start_date"], today - timedelta(days=min(max(days, 1), 90)))
    end = min(camp["end_date"], today)
    if start > end:
        return []
    rows = db.query(
        f"SELECT checkin_date, COUNT(DISTINCT user_id) AS cnt FROM rehab_logs "
        f"WHERE user_id IN ({marks}) AND checkin_date BETWEEN %s AND %s "
        f"GROUP BY checkin_date ORDER BY checkin_date",
        tuple(members) + (start, end))
    rate_map = {r["checkin_date"]: r["cnt"] for r in rows}
    trend = []
    d = start
    while d <= end:
        cnt = rate_map.get(d, 0)
        trend.append({"date": d.isoformat(),
                      "rate": round(cnt * 100 / len(members), 1), "checked": cnt})
        d += timedelta(days=1)
    return trend


def build_camp_report(camp_id: int) -> dict:
    """结营报告：打卡率、人均训练量、平均体重变化、徽章数、Top3。"""
    camp = get_camp(camp_id)
    if not camp:
        return {}
    members = member_ids(camp_id)
    start, end = _camp_date_range(camp)
    total_days = (end - start).days + 1 if end >= start else 0
    member_count = len(members)
    report = {
        "title": camp["title"],
        "start_date": start.isoformat(),
        "end_date": camp["end_date"].isoformat(),
        "member_count": member_count,
        "total_days": total_days,
        "total_checkins": 0,
        "checkin_rate": 0,
        "avg_volume": 0,
        "weight_change_avg": 0,
        "badges_unlocked": 0,
        "top3": [],
    }
    if member_count and total_days:
        marks = ",".join(["%s"] * len(members))
        row = db.query(
            f"SELECT COUNT(*) AS cnt, COALESCE(SUM(train_volume),0) AS vol FROM rehab_logs "
            f"WHERE user_id IN ({marks}) AND checkin_date BETWEEN %s AND %s",
            tuple(members) + (start, end), one=True)
        report["total_checkins"] = row["cnt"]
        report["checkin_rate"] = round(row["cnt"] * 100 / (member_count * total_days), 1)
        report["avg_volume"] = round(int(row["vol"]) / member_count)

        weights = []
        for uid in members:
            body = db.query(
                "SELECT weight FROM body_records WHERE user_id = %s AND weight IS NOT NULL "
                "AND record_date BETWEEN %s AND %s ORDER BY record_date, id",
                (uid, start, end))
            if len(body) >= 2:
                weights.append(float(body[-1]["weight"]) - float(body[0]["weight"]))
        if weights:
            report["weight_change_avg"] = round(sum(weights) / len(weights), 1)

        report["badges_unlocked"] = db.query(
            f"SELECT COUNT(*) AS cnt FROM milestones WHERE user_id IN ({marks}) "
            f"AND unlocked_at BETWEEN %s AND %s",
            tuple(members) + (start, end), one=True)["cnt"]

    for row in camp_leaderboard(camp_id, limit=3):
        report["top3"].append({
            "rank": row["rank"], "user_id": row["user_id"],
            "nickname": "匿名学员" if row["anonymous"] else row["nickname"],
            "score": row["score"]})
    return report


def get_camp_report(camp_id: int) -> dict | None:
    camp = db.query("SELECT report_json FROM rehab_camps WHERE id = %s", (camp_id,), one=True)
    if not camp or not camp["report_json"]:
        return None
    try:
        return json.loads(camp["report_json"])
    except (TypeError, ValueError):
        return None


# ---------------- 营内群聊 ----------------

def camp_chat_history(camp_id: int, limit: int = 100) -> list:
    rows = db.query(
        "SELECT m.*, u.nickname AS sender_nickname, u.avatar AS sender_avatar "
        "FROM rehab_camp_messages m LEFT JOIN users u ON u.id = m.sender_id "
        "WHERE m.camp_id = %s ORDER BY m.id DESC LIMIT %s",
        (camp_id, min(max(limit, 1), 200)))
    return [{**r, "created_at": str(r["created_at"])} for r in reversed(rows)]


async def broadcast_camp_message(camp_id: int, payload: dict) -> None:
    """广播给全体在营成员 + 营教练。"""
    camp = db.query("SELECT coach_id FROM rehab_camps WHERE id = %s", (camp_id,), one=True)
    uids = member_ids(camp_id)
    if camp and camp["coach_id"] not in uids:
        uids.append(camp["coach_id"])
    for uid in uids:
        await manager.send_to_user(uid, payload)


def send_camp_message(camp_id: int, sender_id: int, msg_type: str, content: str,
                      media_path: str = "") -> dict:
    msg_id = db.insert(
        "INSERT INTO rehab_camp_messages (camp_id, sender_id, msg_type, content, media_path) "
        "VALUES (%s,%s,%s,%s,%s)",
        (camp_id, sender_id, msg_type, content, media_path))
    return get_camp_message(msg_id)


def get_camp_message(msg_id: int) -> dict | None:
    row = db.query(
        "SELECT m.*, u.nickname AS sender_nickname, u.avatar AS sender_avatar "
        "FROM rehab_camp_messages m LEFT JOIN users u ON u.id = m.sender_id WHERE m.id = %s",
        (msg_id,), one=True)
    if not row:
        return None
    return {**row, "created_at": str(row["created_at"])}


def _system_camp_message(camp_id: int, content: str) -> None:
    send_camp_message(camp_id, None, "system", content)
