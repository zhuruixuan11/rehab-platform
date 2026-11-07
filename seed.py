"""演示数据初始化脚本。

用法（在项目根目录，安装依赖后执行）:
    python seed.py

生成演示账号:
    admin      / Admin@123      管理员
    coach_li   / Coach@123      教练（已认证）
    coach_wang / Coach@123      教练（待审核）
    student_wx / Student@123    学员（高活跃）
    student_zy / Student@123    学员（中活跃）
    student_cj / Student@123    学员（低活跃）
"""
import json
import random
from datetime import date, datetime, timedelta

from app.auth.security import hash_password
from app.database import db

random.seed(42)


def upsert_user(username, password, nickname, role, phone=None, streak=0):
    row = db.query("SELECT id FROM users WHERE username = %s", (username,), one=True)
    if row:
        db.execute("DELETE FROM users WHERE id = %s", (row["id"],))
    user_id = db.insert(
        "INSERT INTO users (username, password_hash, nickname, role, phone, current_streak, longest_streak, last_login_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (username, hash_password(password), nickname, role, phone,
         streak, streak, datetime.now()))
    return user_id


def seed():
    today = date.today()

    admin_id = upsert_user("admin", "Admin@123", "平台管理员", "admin")
    coach_li = upsert_user("coach_li", "Coach@123", "李教练", "coach", "13800000001")
    coach_wang = upsert_user("coach_wang", "Coach@123", "王教练", "coach", "13800000002")
    s_wx = upsert_user("student_wx", "Student@123", "王小星", "student", "13900000001", 12)
    s_zy = upsert_user("student_zy", "Student@123", "张一远", "student", "13900000002", 5)
    s_cj = upsert_user("student_cj", "Student@123", "陈静", "student", "13900000003", 2)
    s_lb = upsert_user("student_lb", "Student@123", "刘博", "student", "13900000004", 8)

    db.execute("DELETE FROM therapist_profiles")
    db.insert(
        "INSERT INTO therapist_profiles (user_id, real_name, bio, specialty, certifications, review_status) "
        "VALUES (%s,%s,%s,%s,%s,'approved')",
        (coach_li, "李强", "从业8年，主管康复治疗师，擅长骨科术后康复与肩膝关节功能重建。",
         "骨科术后/肩膝康复/运动损伤", "中级康复治疗师, 骨科康复认证"))
    db.insert(
        "INSERT INTO therapist_profiles (user_id, real_name, bio, specialty, certifications, review_status) "
        "VALUES (%s,%s,%s,%s,%s,'pending')",
        (coach_wang, "王磊", "康复治疗师，擅长颈腰痛手法治疗与体态矫正。",
         "颈腰痛/体态矫正/平衡训练", "康复治疗师资格证"))

    # ---------- 康复方案 ----------
    students = [(s_wx, coach_li), (s_zy, coach_li), (s_cj, coach_li), (s_lb, coach_li)]
    plan_tpl = {
        s_wx: ("肩袖损伤术后康复 4 周方案", [("肩关节钟摆运动", 2, 10, 0), ("肩前屈主动辅助训练", 3, 10, 0),
                                         ("肩胛后缩训练", 3, 12, 0), ("弹力带肩外旋", 3, 12, 0)]),
        s_zy: ("ACL 重建术后康复 6 周方案", [("踝泵运动", 3, 20, 0), ("股四头肌等长收缩", 3, 10, 0),
                                         ("直腿抬高", 3, 10, 0), ("坐位伸膝", 3, 12, 0)]),
        s_cj: ("慢性颈腰痛 2 周方案", [("颈椎后缩训练", 3, 10, 0), ("猫牛式", 2, 10, 0),
                                     ("臀桥", 3, 12, 0), ("鸟狗式", 3, 8, 0)]),
        s_lb: ("踝关节扭伤恢复 4 周方案", [("提踵", 3, 15, 0), ("单腿站立", 3, 20, 0),
                                        ("蚌式开合", 3, 12, 0), ("足跟脚尖直线行走", 3, 10, 0)]),
    }
    plan_ids = {}
    for sid, cid in students:
        title, items = plan_tpl[sid]
        start = today - timedelta(days=20)
        end = today + timedelta(days=14)
        plan_id = db.insert(
            "INSERT INTO rehab_programs (coach_id, student_id, title, description, start_date, end_date, is_recommended, recommend_weight) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (cid, sid, title, "系统演示计划，可复制修改。", start, end,
             1 if sid == s_wx else 0, 90 if sid == s_wx else 0))
        plan_ids[sid] = plan_id
        for week in range(5):
            day = start + timedelta(days=week * 7 + 1)
            if day > end:
                break
            for idx, it in enumerate(items):
                name, sets_, reps, weight = it
                db.execute(
                    "INSERT INTO program_items (plan_id, day_date, exercise_name, sets, reps, weight_suggest, rest_sec, note, sort_order) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (plan_id, day, name, sets_, reps, weight, 90, "", idx))

    # ---------- 康复日志 ----------
    activity = {s_wx: 0.85, s_zy: 0.6, s_cj: 0.3, s_lb: 0.7}
    exercise_pool = ["踝泵运动", "股四头肌等长收缩", "臀桥", "猫牛式", "鸟狗式", "肩胛后缩训练",
                     "坐位伸膝", "直腿抬高", "提踵", "靠墙静蹲", "缩唇呼吸", "六分钟步行训练"]
    for sid, rate in activity.items():
        for i in range(59, -1, -1):
            d = today - timedelta(days=i)
            if random.random() > rate:
                continue
            volume = random.randint(1500, 8000)
            duration = random.randint(30, 110)
            intensity = min(5, max(1, volume // 2000))
            vas_before = max(0, min(10, 5 - (59 - i) // 20 + random.randint(0, 1)))
            vas_after = max(0, min(10, vas_before - random.randint(0, 1)))
            checkin_id = db.insert(
                "INSERT INTO rehab_logs (user_id, checkin_date, content, plan_id, train_volume, "
                "duration_min, intensity, vas_before, vas_after) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (sid, d, random.choice([
                    "今天完成了康复训练，疼痛比昨天轻一些。", "按治疗师方案完成，动作控制得不错。",
                    "训练后有些酸胀，休息后已缓解。", "完成关节活动度练习，活动范围有进步。",
                    "呼吸训练后感觉放松很多。"]),
                 plan_ids.get(sid), volume, duration, intensity, vas_before, vas_after))
            for name in random.sample(exercise_pool, random.randint(2, 4)):
                sets_ = random.randint(2, 4)
                reps = random.randint(8, 20)
                weight = 0
                db.execute(
                    "INSERT INTO rehab_log_details (checkin_id, exercise_name, sets, reps, weight, rpe, heart_rate, rest_sec) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (checkin_id, name, sets_, reps, weight, random.randint(3, 6),
                     random.randint(75, 115), random.randint(60, 120)))

    # ---------- 身体数据 ----------
    body_base = {s_wx: (72.5, 18.0), s_zy: (65.0, 24.5), s_cj: (55.0, 27.0), s_lb: (80.0, 16.5)}
    for sid, (w0, fat0) in body_base.items():
        for i in range(8, -1, -1):
            d = today - timedelta(days=i * 7)
            w = round(w0 - (8 - i) * random.uniform(0.1, 0.4), 1)
            fat = round(fat0 - (8 - i) * random.uniform(0.05, 0.25), 1)
            db.execute(
                "INSERT INTO body_records (user_id, record_date, weight, body_fat, chest, waist, hip, arm, thigh) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (sid, d, w, fat, round(w * 1.32, 1), round(w * 0.78, 1), round(w * 0.98, 1),
                 round(w * 0.35, 1), round(w * 0.56, 1)))

    # ---------- 社区动态 ----------
    db.execute("DELETE FROM community_posts")
    posts = [
        (s_wx, "术后第 12 天，肩关节前屈比上周多了 10 度，钟摆运动坚持中。", "public"),
        (s_zy, "ACL 术后第 6 周，今天完成靠墙静蹲和坐位伸膝，膝盖比前几天稳定。", "public"),
        (s_cj, "今天腰有点紧，只做了猫牛式和呼吸训练，明天再补上。", "coach"),
        (s_lb, "踝关节扭伤第 3 周，单腿站立能坚持 20 秒了，继续加油。", "public"),
        (coach_li, "康复小知识：做肩胛后缩时想象把肩胛骨「放进后裤兜」，不要耸肩，颈肩会更放松。", "public"),
    ]
    for uid, content, vis in posts:
        db.insert(
            "INSERT INTO community_posts (user_id, content, visibility) VALUES (%s,%s,%s)",
            (uid, content, vis))

    # ---------- 成就 ----------
    db.execute("DELETE FROM milestones")
    for r in db.query("SELECT id, current_streak FROM users WHERE role='student'"):
        if r["current_streak"] >= 7:
            db.execute("INSERT INTO milestones (user_id, badge_code) VALUES (%s,'streak_7')", (r["id"],))
            db.execute("INSERT IGNORE INTO milestones (user_id, badge_code) VALUES (%s,'total_30')", (r["id"],))

    # ---------- 消息 ----------
    db.execute("DELETE FROM messages")
    for sid, _ in students:
        db.execute(
            "INSERT INTO messages (sender_id, receiver_id, msg_type, content) VALUES (%s,%s,'text',%s)",
            (coach_li, sid, "本周康复方案已更新，训练前请做好热身。"))
        db.execute(
            "INSERT INTO messages (sender_id, receiver_id, msg_type, content, is_read) VALUES (NULL,%s,'system',%s,1)",
            (sid, "欢迎使用康衡康复中心，康复训练后记得记录日志！"))

    # ---------- 补签申请 ----------
    db.execute("DELETE FROM makeup_requests")
    db.execute(
        "INSERT INTO makeup_requests (user_id, checkin_date, reason) VALUES (%s,%s,%s)",
        (s_zy, today - timedelta(days=2), "出差漏打卡，实际已完成训练。"))
    db.execute(
        "INSERT INTO makeup_requests (user_id, checkin_date, reason) VALUES (%s,%s,%s)",
        (s_cj, today - timedelta(days=4), "生病休息，补录居家训练。"))

    # ---------- 康复档案 / 评估 / 筛查 ----------
    for table in ("followups", "appointments", "treatment_cards", "therapist_schedules",
                  "rehab_screenings", "rehab_assessments", "rehab_cases"):
        db.execute(f"DELETE FROM {table}")

    cases = [
        (s_wx, "肩袖损伤术后", "骨科术后", "右", 45, "恢复期",
         "右肩抬举疼痛、夜间痛，梳头受限", "肩袖缝合术后，肩关节活动度受限",
         "12 周内恢复肩关节无痛前屈 150°、外旋 60°，回归日常与轻量训练"),
        (s_zy, "ACL 重建术后", "骨科术后", "左", 42, "恢复期",
         "左膝肿胀、上下楼不稳，屈伸受限", "前交叉韧带重建术后",
         "24 周内恢复对称伸膝、单腿跳稳定，回归跑步"),
        (s_cj, "慢性颈腰痛", "慢性疼痛", None, 180, "维持期",
         "久坐后颈腰酸胀，偶有下肢放射感", "非特异性颈腰痛，核心稳定不足",
         "8 周内疼痛 VAS ≤ 2，核心耐力提升，恢复每周 3 次运动"),
    ]
    case_ids = {}
    for (pid, name, ctype, side, days, stage, complaint, diagnosis, goal) in cases:
        cid = db.insert(
            "INSERT INTO rehab_cases (patient_id, therapist_id, condition_name, condition_type, "
            "injured_side, onset_date, stage, chief_complaint, diagnosis, goal, status) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')",
            (pid, coach_li, name, ctype, side, today - timedelta(days=days), stage,
             complaint, diagnosis, goal))
        case_ids[pid] = cid

    assess_tpl = {
        s_wx: [
            (42, 6, 40, 17.5, 14.8, None, None, 45, 50, 45, 55, '{"肩前屈":85,"肩外旋":20}', '{"冈上肌":3}'),
            (28, 4, 47, 15.0, 12.2, None, None, 58, 62, 55, 68, '{"肩前屈":105,"肩外旋":30}', '{"冈上肌":4}'),
            (14, 3, 52, 12.8, 10.4, None, None, 70, 72, 62, 78, '{"肩前屈":125,"肩外旋":40}', '{"冈上肌":4}'),
        ],
        s_zy: [
            (40, 7, 32, 18.6, 15.2, None, 58, 45, 52, 48, 50, '{"膝屈曲":95,"膝伸展":-10}', '{"股四头肌":3}'),
            (26, 5, 41, 15.8, 12.6, None, 52, 58, 62, 58, 62, '{"膝屈曲":112,"膝伸展":-5}', '{"股四头肌":4}'),
            (12, 3, 50, 12.9, 9.7, None, 44, 70, 74, 70, 76, '{"膝屈曲":128,"膝伸展":0}', '{"股四头肌":4}'),
        ],
        s_cj: [
            (30, 6, None, None, None, 38, None, 50, 55, 50, 52, '{"腰椎前屈":60}', '{"竖脊肌":3}'),
            (16, 4, None, None, None, 26, None, 62, 65, 58, 66, '{"腰椎前屈":72}', '{"竖脊肌":4}'),
            (5, 2, None, None, None, 16, None, 74, 76, 68, 78, '{"腰椎前屈":82}', '{"竖脊肌":4}'),
        ],
    }
    for pid, rows in assess_tpl.items():
        for (days_ago, vas, berg, tug, walk, odi, womac, bal, gait, posture, adl, rom, mmt) in rows:
            db.insert(
                "INSERT INTO rehab_assessments (patient_id, case_id, assess_date, assessor_id, "
                "pain_vas, berg_score, tug_sec, walk10m_sec, odi_score, womac_score, "
                "rom_json, mmt_json, balance_score, gait_score, posture_score, adl_score, notes) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (pid, case_ids[pid], today - timedelta(days=days_ago), coach_li, vas,
                 berg, tug, walk, odi, womac, rom, mmt, bal, gait, posture, adl,
                 "复评：疼痛与功能较前改善，继续当前阶段训练。"))

    db.execute(
        "INSERT INTO rehab_screenings (patient_id, case_id, assessor_id, items_json, has_red_flag, notes) "
        "VALUES (%s,%s,%s,%s,0,%s)",
        (s_wx, case_ids[s_wx], coach_li,
         json.dumps({"fever": False, "night_pain": False, "saddle": False, "weakness": False,
                     "trauma": False, "cardiopulmonary": False, "wound": False,
                     "dizziness": False}), "无红旗征，可按计划训练"))
    db.execute(
        "INSERT INTO rehab_screenings (patient_id, case_id, assessor_id, items_json, has_red_flag, notes) "
        "VALUES (%s,%s,%s,%s,1,%s)",
        (s_zy, case_ids[s_zy], coach_li,
         json.dumps({"fever": False, "night_pain": True, "saddle": False, "weakness": False,
                     "trauma": False, "cardiopulmonary": False, "wound": False,
                     "dizziness": False}), "夜间静息痛明显，建议骨科复查排除感染/血栓"))

    # ---------- 排班 / 预约 / 疗程卡 / 随访 ----------
    for coach_id in (coach_li, coach_wang):
        for i in range(1, 8):
            d = today + timedelta(days=i)
            if d.weekday() >= 5 and coach_id == coach_wang:
                continue
            db.insert(
                "INSERT INTO therapist_schedules (coach_id, work_date, start_time, end_time, "
                "slot_min, capacity, location, note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (coach_id, d, "09:00", "12:00", 30, 2,
                 "康衡康复中心 · 治疗区", "上午门诊评估/治疗"))

    db.insert(
        "INSERT INTO appointments (patient_id, coach_id, appt_date, start_time, end_time, "
        "appt_type, status, note) VALUES (%s,%s,%s,%s,%s,%s,'booked',%s)",
        (s_wx, coach_li, today + timedelta(days=1), "09:30", "10:00", "门诊评估", "肩关节活动度复评"))
    db.insert(
        "INSERT INTO appointments (patient_id, coach_id, appt_date, start_time, end_time, "
        "appt_type, status, note) VALUES (%s,%s,%s,%s,%s,%s,'completed',%s)",
        (s_zy, coach_li, today - timedelta(days=1), "10:00", "10:30", "手法治疗", "膝关节松动+训练"))

    db.insert(
        "INSERT INTO treatment_cards (patient_id, case_id, title, total_sessions, used_sessions, "
        "valid_from, valid_to, status, note) VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s)",
        (s_wx, case_ids[s_wx], "肩袖术后康复疗程卡（12次）", 12, 4,
         today - timedelta(days=30), today + timedelta(days=60), "含评估与手法治疗"))
    db.insert(
        "INSERT INTO treatment_cards (patient_id, case_id, title, total_sessions, used_sessions, "
        "valid_from, valid_to, status, note) VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s)",
        (s_zy, case_ids[s_zy], "ACL 术后康复疗程卡（10次）", 10, 3,
         today - timedelta(days=20), today + timedelta(days=70), "含评估、理疗与训练指导"))

    db.insert(
        "INSERT INTO followups (patient_id, coach_id, case_id, due_date, content, status) "
        "VALUES (%s,%s,%s,%s,%s,'pending')",
        (s_cj, coach_li, case_ids[s_cj], today,
         "近一周未记录康复日志，请回访了解腰痛情况并提醒复评。"))

    # ---------- 操作日志 ----------
    db.execute("DELETE FROM operation_logs")
    db.execute(
        "INSERT INTO operation_logs (admin_id, module, action, detail) VALUES (%s,'系统','初始化','seed.py 生成演示数据')",
        (admin_id,))

    # 重新计算连续打卡
    from app.services.checkin_service import recompute_streak
    for sid, _ in students:
        recompute_streak(sid)

    print("演示数据初始化完成。")
    print("账号: admin/Admin@123, coach_li/Coach@123, coach_wang/Coach@123, "
          "student_wx/Student@123, student_zy/Student@123, student_cj/Student@123")


if __name__ == "__main__":
    seed()
