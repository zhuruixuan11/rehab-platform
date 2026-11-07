from app.database import db
from app.services.message_service import system_notify

BADGES = [
    {"code": "streak_3", "name": "三日入门", "icon": "🌱", "color": "#10B981",
     "type": "streak", "target": 3, "desc": "连续打卡 3 天"},
    {"code": "streak_7", "name": "七日之约", "icon": "🔥", "color": "#F59E0B",
     "type": "streak", "target": 7, "desc": "连续打卡 7 天"},
    {"code": "streak_14", "name": "半月坚持", "icon": "🎯", "color": "#06B6C4",
     "type": "streak", "target": 14, "desc": "连续打卡 14 天"},
    {"code": "streak_30", "name": "月度坚持", "icon": "🏅", "color": "#06B6C4",
     "type": "streak", "target": 30, "desc": "连续打卡 30 天"},
    {"code": "streak_100", "name": "百日筑基", "icon": "💎", "color": "#8B5CF6",
     "type": "streak", "target": 100, "desc": "连续打卡 100 天"},
    {"code": "streak_365", "name": "全年无休", "icon": "👑", "color": "#10B981",
     "type": "streak", "target": 365, "desc": "连续打卡 365 天"},
    {"code": "total_30", "name": "三十而立", "icon": "💪", "color": "#06B6C4",
     "type": "total", "target": 30, "desc": "累计打卡 30 次"},
    {"code": "total_100", "name": "百炼成钢", "icon": "⚡", "color": "#F59E0B",
     "type": "total", "target": 100, "desc": "累计打卡 100 次"},
    {"code": "total_365", "name": "全年习惯", "icon": "📆", "color": "#10B981",
     "type": "total", "target": 365, "desc": "累计打卡 365 次"},
    {"code": "volume_10000", "name": "万斤之力", "icon": "🏋️", "color": "#EF4444",
     "type": "volume", "target": 10000, "desc": "累计训练量 10 吨"},
    {"code": "volume_50000", "name": "半百吨俱乐部", "icon": "🚀", "color": "#8B5CF6",
     "type": "volume", "target": 50000, "desc": "累计训练量 50 吨"},
    {"code": "volume_100000", "name": "百吨传奇", "icon": "🏆", "color": "#F59E0B",
     "type": "volume", "target": 100000, "desc": "累计训练量 100 吨"},
]

BADGE_MAP = {b["code"]: b for b in BADGES}


def _user_stats(user_id: int) -> dict:
    user = db.query("SELECT current_streak, longest_streak FROM users WHERE id = %s",
                    (user_id,), one=True)
    stats = db.query(
        "SELECT COUNT(*) AS total_days, COALESCE(SUM(train_volume),0) AS total_volume "
        "FROM rehab_logs WHERE user_id = %s",
        (user_id,), one=True)
    return {"user": user, "stats": stats}


def _badge_progress(badge: dict, user: dict, stats: dict) -> int:
    """返回徽章当前进度值。"""
    if badge["type"] == "streak":
        return max(user["current_streak"], user["longest_streak"])
    if badge["type"] == "total":
        return stats["total_days"]
    return float(stats["total_volume"])


def check_and_unlock(user_id: int) -> list:
    """检查并解锁新成就，返回新解锁徽章列表。"""
    ctx = _user_stats(user_id)
    owned = {r["badge_code"] for r in db.query(
        "SELECT badge_code FROM milestones WHERE user_id = %s", (user_id,))}

    new_badges = []
    for badge in BADGES:
        if badge["code"] in owned:
            continue
        if _badge_progress(badge, ctx["user"], ctx["stats"]) >= badge["target"]:
            db.execute(
                "INSERT IGNORE INTO milestones (user_id, badge_code) VALUES (%s,%s)",
                (user_id, badge["code"]))
            new_badges.append(badge)
            system_notify(user_id, f"恭喜解锁成就【{badge['name']}】{badge['icon']} —— {badge['desc']}！继续保持！")

    return new_badges


def list_achievements(user_id: int) -> list:
    ctx = _user_stats(user_id)
    rows = db.query("SELECT badge_code, unlocked_at FROM milestones WHERE user_id = %s",
                    (user_id,))
    unlocked = {r["badge_code"]: r["unlocked_at"] for r in rows}
    result = []
    for badge in BADGES:
        current = _badge_progress(badge, ctx["user"], ctx["stats"])
        result.append({**badge,
                       "unlocked": badge["code"] in unlocked,
                       "unlocked_at": str(unlocked[badge["code"]]) if badge["code"] in unlocked else None,
                       "progress": min(int(current), badge["target"]),
                       "percent": round(min(current / badge["target"] * 100, 100), 1)})
    return result


def recent_achievements(user_id: int, limit: int = 3) -> list:
    rows = db.query(
        "SELECT badge_code, unlocked_at FROM milestones WHERE user_id = %s "
        "ORDER BY unlocked_at DESC LIMIT %s",
        (user_id, limit))
    return [{**BADGE_MAP.get(r["badge_code"], {"name": r["badge_code"], "icon": "🏅"}),
             "unlocked_at": str(r["unlocked_at"])} for r in rows]
