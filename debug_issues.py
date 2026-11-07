import requests
import traceback

BASE = "http://localhost:8001"


def login(u, p):
    r = requests.post(BASE + "/api/auth/login", json={"username": u, "password": p})
    return {"Authorization": "Bearer " + r.json()["token"]}, r.json()["user"]


try:
    sh, su = login("student_wx", "Student@123")
    print("== 学员成就/排行 ==")
    for ep, params in [
        ("/api/student/achievements", None),
        ("/api/student/rankings", {"period": "week"}),
        ("/api/student/rankings", {"period": "month", "metric": "volume"}),
    ]:
        try:
            r = requests.get(BASE + ep, headers=sh, params=params)
            print(ep, params, "->", r.status_code, r.text[:200])
        except Exception as e:
            print(ep, "EXC:", e)
except Exception:
    traceback.print_exc()

try:
    ah, au = login("admin", "Admin@123")
    print("\n== 管理端教练审核 ==")
    r = requests.get(BASE + "/api/admin/coach-reviews", headers=ah)
    print("coach-reviews ->", r.status_code, r.text[:800])
    print("\n== 管理端计划 ==")
    r = requests.get(BASE + "/api/admin/plans", headers=ah)
    print("plans ->", r.status_code, r.text[:600])
    print("\n== 看板 ==")
    for ep in ["/api/admin/stats/overview", "/api/admin/stats/trend?days=7",
               "/api/admin/stats/checkins", "/api/admin/stats/active-users"]:
        r = requests.get(BASE + ep, headers=ah)
        print(ep, "->", r.status_code, r.text[:150])
except Exception:
    traceback.print_exc()

try:
    ch, cu = login("coach_li", "Coach@123")
    print("\n== 教练计划制定 ==")
    r = requests.get(BASE + "/api/coach/all-students", headers=ch)
    print("all-students ->", r.status_code, r.text[:300])
    r = requests.get(BASE + "/api/coach/plans", headers=ch)
    print("plans ->", r.status_code, r.text[:300])
    r = requests.get(BASE + "/api/coach/students", headers=ch)
    print("students ->", r.status_code, r.text[:200])
except Exception:
    traceback.print_exc()

print("\n== 学员头像字段 ==")
r = requests.get(BASE + "/api/auth/me", headers=sh)
print("me ->", r.text[:300])
