"""训练营模块端到端验证：创建→招生→入营→开营→计划→群聊→排行→结营报告。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path, method="GET", token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def main():
    ok = fail = 0

    def check(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"[PASS] {name} {extra}")
        else:
            fail += 1
            print(f"[FAIL] {name} {extra}")

    _, coach = call("/api/auth/login", "POST", body={"username": "coach_li", "password": "Coach@123"})
    _, student = call("/api/auth/login", "POST", body={"username": "student_wx", "password": "Student@123"})
    ct, st = coach["token"], student["token"]

    # 清理旧测试营
    _, camps = call("/api/camps", token=ct)
    for c in camps:
        call(f"/api/camps/{c['id']}/transition?action=finish", "POST", ct)

    # 1. 创建营
    s, camp = call("/api/camps", "POST", ct, {"title": "E2E验证营", "description": "端到端测试",
                                              "start_date": "2026-08-20", "end_date": "2026-09-10",
                                              "capacity": 10})
    check("创建营期", s == 201 and camp.get("id"), f"id={camp.get('id')}")
    cid = camp["id"]

    # 2. 未发布招生时学员不能加入
    s, r = call("/api/camps/join", "POST", st, {"invite_code": "XXXXXXXX"})
    check("无效邀请码被拒", s == 400, r.get("detail", ""))

    # 3. 发布招生
    s, r = call(f"/api/camps/{cid}/transition?action=start", "POST", ct)
    check("发布招生", s == 200, str(r))
    _, camp = call(f"/api/camps/{cid}", token=ct)
    code = camp["invite_code"]

    # 4. 学员邀请码入营
    s, r = call("/api/camps/join", "POST", st, {"invite_code": code.lower()})
    check("学员入营（小写码兼容）", s == 200 and r.get("id") == cid, str(r)[:80])

    # 5. 重复加入被拒
    s, r = call("/api/camps/join", "POST", st, {"invite_code": code})
    check("重复入营被拒", s == 400, r.get("detail", ""))

    # 6. 非成员访问详情被拒（用另一个新学员）
    _, other = call("/api/auth/register", "POST",
                    body={"username": "e2e_tmp_student", "password": "Temp@123", "nickname": "临时学员"})
    s, r = call(f"/api/camps/{cid}", token=other["token"])
    check("非成员访问详情被拒", s == 403, r.get("detail", ""))

    # 7. 开营
    s, r = call(f"/api/camps/{cid}/transition?action=open", "POST", ct)
    check("开营", s == 200, str(r))

    # 8. 批量生成计划（以教练现有计划为模板）
    _, plans = call("/api/coach/plans", token=ct)
    if plans:
        s, r = call(f"/api/camps/{cid}/generate-plans", "POST", ct,
                    {"template_plan_id": plans[0]["id"], "title": "E2E营期计划"})
        check("批量生成计划", s == 200 and r.get("created", 0) >= 1, str(r))
        _, my_plans = call("/api/student/plans", token=st)
        camp_plans = [p for p in my_plans if p.get("camp_id") == cid]
        check("学员可见营期计划", len(camp_plans) >= 1, f"count={len(camp_plans)}")
    else:
        print("[SKIP] 教练暂无模板计划，跳过计划生成")

    # 9. 群聊历史（含入营系统消息）
    s, msgs = call(f"/api/camps/{cid}/messages", token=st)
    check("群聊历史", s == 200 and any(m["msg_type"] == "system" for m in msgs),
          f"count={len(msgs)}")

    # 10. 排行榜
    s, board = call(f"/api/camps/{cid}/leaderboard", token=st)
    check("营内排行榜", s == 200 and len(board) >= 1, f"rows={len(board)}")

    # 11. 营期看板
    s, dash = call(f"/api/camps/{cid}/dashboard", token=ct)
    check("营期看板", s == 200 and "trend" in dash and "member_stats" in dash,
          f"members={dash.get('active_member_count')}")

    # 12. 学员无权访问教练看板
    s, r = call(f"/api/camps/{cid}/dashboard", token=st)
    check("学员访问看板被拒", s == 403, "")

    # 13. 催打卡
    s, r = call(f"/api/camps/{cid}/urge", "POST", ct, {"message": "E2E催打卡"})
    check("营内催打卡", s == 200 and "sent" in r, str(r))

    # 14. 结营报告
    s, r = call(f"/api/camps/{cid}/transition?action=finish", "POST", ct)
    check("结营", s == 200, str(r))
    s, report = call(f"/api/camps/{cid}/report", token=st)
    check("结营报告", s == 200 and "checkin_rate" in report and "top3" in report,
          f"rate={report.get('checkin_rate')}%")

    # 15. 学员我的营列表
    s, my = call("/api/camps/my", token=st)
    check("我的训练营列表", s == 200 and any(c["id"] == cid for c in my), f"count={len(my)}")

    # 清理临时学员
    call("/api/camps/join", "POST", st, {"invite_code": "cleanup"})
    print(f"\n结果: {ok} 通过, {fail} 失败")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
