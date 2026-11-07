"""端到端验证（2026-08-26 修改项）"""
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


admin_t, _ = login("admin", "Admin@123")
coach_t, _ = login("coach_li", "Coach@123")
student_t, student = login("student_wx", "Student@123")


# 1. 排行 volume 指标（之前500 Decimal错误）
def t_rank_volume():
    st, body = req("/api/student/rankings?period=month&metric=volume", token=student_t)
    assert st == 200, f"status={st}"
    items = body["items"] if isinstance(body, dict) else body
    assert items, "排行无数据"
    assert isinstance(items[0]["score"], (int, float)), "score非数值类型"
check("排行volume接口(Decimal修复)", t_rank_volume)


# 2. 成就接口：新徽章+进度字段
def t_achievements():
    st, body = req("/api/student/achievements", token=student_t)
    assert st == 200, f"status={st}"
    codes = [b["code"] for b in body]
    for c in ("streak_3", "streak_7", "streak_14", "streak_30", "streak_365"):
        assert c in codes, f"缺少徽章 {c}, 现有: {codes}"
    locked = next(b for b in body if not b["unlocked"])
    assert "progress" in locked and "target" in locked and "percent" in locked, "缺少进度字段"
check("成就系统(新徽章+进度)", t_achievements)


# 3. 动作库33个
def t_exercises():
    st, body = req("/api/student/exercises", token=student_t)
    assert st == 200
    names = [e["name"] for e in body]
    assert len(body) >= 33, f"动作数 {len(body)} < 33"
    for n in ("双杠臂屈伸", "罗马尼亚硬拉", "保加利亚分腿蹲", "哑铃侧平举", "面拉",
              "锤式弯举", "悬垂举腿", "俄罗斯转体", "跳绳", "蝴蝶机夹胸"):
        assert n in names, f"缺少动作 {n}"
check(f"动作库扩充(33个)", t_exercises)


# 4. 教练计划列表含推荐字段 + 推荐接口
def t_coach_recommend():
    st, body = req("/api/coach/plans", token=coach_t)
    assert st == 200
    plans = body if isinstance(body, list) else body.get("items", body.get("plans"))
    assert plans, "教练无计划"
    p = plans[0]
    for k in ("is_recommended", "recommend_weight"):
        assert k in p, f"计划缺少字段 {k}: {list(p.keys())}"
    # 取一个未推荐的计划测试推荐/取消
    plan = next((x for x in plans if not x["is_recommended"]), None)
    if plan:
        st, _ = req(f"/api/coach/plans/{plan['id']}/recommend", "POST", token=coach_t)
        assert st == 200, f"推荐失败 status={st}"
        st, _ = req(f"/api/coach/plans/{plan['id']}/recommend", "POST", token=coach_t)
        assert st == 200, f"取消推荐失败 status={st}"
check("教练推荐计划接口", t_coach_recommend)


# 5. 学员计划列表展示推荐标记
def t_student_plans():
    st, body = req("/api/student/plans", token=student_t)
    assert st == 200
    plans = body if isinstance(body, list) else body.get("items", body.get("plans"))
    assert plans, "学员无计划"
    assert "is_recommended" in plans[0], f"缺少推荐标记: {list(plans[0].keys())}"
check("学员计划(推荐标记)", t_student_plans)


# 6. 管理端计划页为只读分配视图
def t_admin_plans():
    st, body = req("/api/admin/plans", token=admin_t)
    assert st == 200
    items = body if isinstance(body, list) else body.get("items", body.get("plans"))
    assert items, "无计划数据"
    for k in ("student_name", "coach_name", "item_count"):
        assert k in items[0], f"缺少字段 {k}: {list(items[0].keys())}"
check("管理端计划分配总览", t_admin_plans)


# 7. 管理端教练审核列表（状态字段）
def t_coach_reviews():
    st, body = req("/api/admin/coach-reviews", token=admin_t)
    assert st == 200
    reviews = body if isinstance(body, list) else body.get("items", body.get("reviews"))
    assert reviews, "无教练审核数据"
    assert "review_status" in reviews[0], f"缺少状态字段: {list(reviews[0].keys())}"
check("教练审核列表(状态区分)", t_coach_reviews)


# 8. 管理端统计看板
def t_admin_stats():
    st, body = req("/api/admin/stats/overview", token=admin_t)
    assert st == 200
    for k in ("total_users", "students", "coaches", "dau", "mau",
              "checkins_today", "pending_coach_reviews"):
        assert k in body, f"缺少 {k}"
check("管理端统计看板", t_admin_stats)


# 9. 头像字段存在于用户信息
def t_avatar():
    st, body = req("/api/auth/me", token=student_t)
    assert st == 200 and "avatar" in body
    st, body = req("/api/coach/students", token=coach_t)
    assert st == 200
    items = body if isinstance(body, list) else body.get("items", body.get("students"))
    assert items and "avatar" in items[0], "学员列表缺少头像字段"
check("头像字段(学员/教练列表)", t_avatar)


# 10. 教练看板数据
def t_coach_dashboard():
    st, body = req("/api/coach/students", token=coach_t)
    assert st == 200
check("教练端数据看板接口", t_coach_dashboard)


print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
if failed:
    for n, e in failed:
        print(f"  FAIL: {n} -> {e}")
    raise SystemExit(1)
