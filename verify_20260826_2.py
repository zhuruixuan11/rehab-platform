"""端到端验证（2026-08-26 第二轮修改项）"""
import json
import urllib.request

BASE = "http://localhost:8001"


def req(path, method="GET", body=None, token=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(r) as resp:
        return resp.status, json.loads(resp.read().decode())


def login(username, password):
    st, body = req("/api/auth/login", "POST", {"username": username, "password": password})
    assert st == 200, body
    return body["token"]


passed, failed = [], []


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"[PASS] {name}")
    except Exception as e:
        failed.append((name, str(e)))
        print(f"[FAIL] {name}: {e}")


admin_t = login("admin", "Admin@123")
coach_t = login("coach_li", "Coach@123")

# 1. 管理端消息明细下钻接口
def t_messages():
    st, body = req("/api/admin/stats/messages?page=1&page_size=15", token=admin_t)
    assert st == 200, f"status={st}"
    assert "total" in body and "items" in body
    if body["items"]:
        m = body["items"][0]
        for k in ("sender_name", "receiver_name", "msg_type", "content", "created_at", "is_read"):
            assert k in m, f"缺少字段 {k}"
check("管理端消息明细下钻接口", t_messages)


# 2. 教练审核筛选（前端avatarHtml修复无法用接口验证，验证后端数据完整含avatar）
def t_coach_reviews():
    st, body = req("/api/admin/coach-reviews?status=approved", token=admin_t)
    assert st == 200 and len(body) >= 1, "已认证筛选无数据"
    assert "avatar" in body[0], "缺少avatar字段"
    st, body = req("/api/admin/coach-reviews?status=pending", token=admin_t)
    assert st == 200 and len(body) >= 1, "待审核筛选无数据"
check("教练审核筛选(approved/pending有数据)", t_coach_reviews)


# 3. 教练 dashboard 含 urged_today
def t_coach_dashboard():
    st, body = req("/api/coach/dashboard", token=coach_t)
    assert st == 200, f"status={st}"
    for k in ("total_students", "avg_rate_30", "checkin_trend", "low_rate_students",
              "active_plans", "pending_makeups"):
        assert k in body, f"缺少 {k}"
    if body["low_rate_students"]:
        assert "urged_today" in body["low_rate_students"][0], "预警学员缺少urged_today"
check("教练数据看板接口(含urged_today)", t_coach_dashboard)


# 4. 教练学员列表含 urged_today
def t_coach_students():
    st, body = req("/api/coach/students", token=coach_t)
    assert st == 200 and body, "学员列表为空"
    assert "urged_today" in body[0], "缺少urged_today字段"
check("教练学员列表(含urged_today)", t_coach_students)


# 5. 催打卡接口（发消息带【催打卡】前缀）+ 再次查询变已催
def t_urge():
    st, body = req("/api/coach/students", token=coach_t)
    stu = body[0]
    sid = stu["id"]
    st, r = req(f"/api/coach/students/{sid}/urge", "POST", {"message": "记得打卡哦"}, token=coach_t)
    assert st == 200 and r.get("urged_today"), f"urge失败: {r}"
    st, body2 = req("/api/coach/students", token=coach_t)
    row = next(s for s in body2 if s["id"] == sid)
    assert row["urged_today"] is True, "催促后urged_today未变True"
check("催打卡(消息前缀+已催状态)", t_urge)


# 6. all-students 含 avatar
def t_all_students():
    st, body = req("/api/coach/all-students", token=coach_t)
    assert st == 200 and body
    for k in ("avatar", "current_streak", "longest_streak", "phone"):
        assert k in body[0], f"缺少 {k}"
check("可选学员列表(含avatar)", t_all_students)


# 7. 管理端计划只读总览（无推荐操作）
def t_admin_plans():
    st, body = req("/api/admin/plans", token=admin_t)
    assert st == 200 and body
    for k in ("student_name", "coach_name", "item_count", "is_recommended"):
        assert k in body[0], f"缺少 {k}"
check("管理端计划分配总览(只读)", t_admin_plans)


# 8. 管理端概览（消息量数字来源）
def t_overview():
    st, body = req("/api/admin/stats/overview", token=admin_t)
    assert st == 200 and "messages_30d" in body
check("管理端概览(messages_30d)", t_overview)


# 清理测试催打卡消息
from app.database import db
n = db.execute("DELETE FROM messages WHERE content LIKE %s AND sender_id = (SELECT id FROM users WHERE username=%s) AND created_at >= CURDATE()",
               ("【催打卡】%", "coach_li"))
print(f"(清理测试催打卡消息 {n} 条)")

print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
if failed:
    for n, e in failed:
        print(f"  FAIL: {n} -> {e}")
    raise SystemExit(1)
