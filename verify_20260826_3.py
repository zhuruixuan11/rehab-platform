"""端到端验证（2026-08-26 第三轮：配色/菜单/审核/头像/计划）"""
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
    return body["token"], body["user"]


passed, failed = [], []


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"[PASS] {name}")
    except Exception as e:
        failed.append((name, str(e)))
        print(f"[FAIL] {name}: {e}")


admin_t, admin_u = login("admin", "Admin@123")
coach_t, coach_u = login("coach_li", "Coach@123")
student_t, student_u = login("student_wx", "Student@123")


# 1. 预设头像接口
def t_presets():
    st, body = req("/api/auth/avatar-presets")
    assert st == 200 and len(body) == 6, body
    assert all("path" in p for p in body)
check("Q版预设头像接口(6个)", t_presets)


# 2. 选择预设头像（学员）
def t_set_preset():
    st, body = req("/api/auth/avatar-presets")
    path = body[0]["path"]
    st, r = req("/api/auth/me", "PUT", {"avatar": path}, token=student_t)
    assert st == 200, r
    st, me = req("/api/auth/me", token=student_t)
    assert me["avatar"] == path, me["avatar"]
check("选择预设头像生效", t_set_preset)


# 3. 教练审核四状态筛选
def t_reviews():
    for s, expect_any in (("pending", True), ("approved", True), ("rejected", False), ("", True)):
        st, body = req(f"/api/admin/coach-reviews?status={s}" if s else "/api/admin/coach-reviews", token=admin_t)
        assert st == 200
        if expect_any:
            assert len(body) >= 1, f"status={s} 无数据"
check("教练审核筛选数据完整", t_reviews)


# 4. 教练可选学员含体重/体脂
def t_all_students():
    st, body = req("/api/coach/all-students", token=coach_t)
    assert st == 200 and body
    for k in ("avatar", "latest_weight", "latest_body_fat", "current_streak"):
        assert k in body[0], f"缺少 {k}"
check("计划制定学员信息(体重/体脂)", t_all_students)


# 5. 学员计划含教练信息
def t_student_plans():
    st, body = req("/api/student/plans", token=student_t)
    assert st == 200
    if body:
        for k in ("coach_name", "coach_avatar", "items"):
            assert k in body[0], f"缺少 {k}"
check("学员计划含教练信息", t_student_plans)


# 6. 学员今日打卡详情（未打卡时404是正常响应）
def t_today_checkin():
    from datetime import date
    try:
        st, body = req(f"/api/student/checkins/{date.today().isoformat()}", token=student_t)
        assert st == 200
    except urllib.error.HTTPError as e:
        assert e.code == 404, f"预期404(今日未打卡)，实际 {e.code}"
check("学员今日打卡接口", t_today_checkin)


# 7. 静态资源版本号生效
def t_static():
    for p in ("/js/app.js?v=20260826b", "/css/style.css?v=20260826b"):
        rr = urllib.request.urlopen(BASE + p)
        assert rr.status == 200
    css = urllib.request.urlopen(BASE + "/css/style.css?v=20260826b").read().decode()
    assert "#FF6B00" in css and "#1A1A2E" in css, "配色未更新"
    appjs = urllib.request.urlopen(BASE + "/js/app.js?v=20260826b").read().decode()
    assert "DEFAULT_VIEW" in appjs and '"数据总览"' not in appjs, "菜单未更新"
    assert 'checkin' in appjs, "学员默认页未改"
    coachjs = urllib.request.urlopen(BASE + "/js/coach.js?v=20260826b").read().decode()
    assert '"数据看板"' not in coachjs, "教练数据看板未删"
check("静态资源版本+配色+菜单", t_static)


# 8. 管理端消息明细（上轮功能回归）
def t_messages():
    st, body = req("/api/admin/stats/messages?page=1&page_size=15", token=admin_t)
    assert st == 200 and "total" in body
check("消息明细下钻回归", t_messages)


# 清理：把学员头像恢复为空（不保留测试选择）
db_fix = req("/api/auth/me", "PUT", {"avatar": ""}, token=student_t)
print("(已重置测试头像)")

print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
if failed:
    for n, e in failed:
        print(f"  FAIL: {n} -> {e}")
    raise SystemExit(1)
