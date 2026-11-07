"""康复平台 2026-11-07 迁移：标准量表、红旗征筛查、运动禁忌、排班预约、疗程卡、随访与演示数据。

执行：python migrate_rehab_20261107.py
"""
from datetime import date, timedelta

from app.database import db


def has_column(table: str, column: str) -> bool:
    row = db.query(
        "SELECT 1 ok FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (table, column), one=True)
    return row is not None


def has_table(table: str) -> bool:
    row = db.query(
        "SELECT 1 ok FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", (table,), one=True)
    return row is not None


def add_column(table: str, column: str, ddl: str):
    if not has_column(table, column):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        print(f"  + {table}.{column}")


def migrate_schema():
    print("[1/3] 扩展表结构…")
    for col, ddl in [
        ("berg_score", "TINYINT DEFAULT NULL COMMENT 'Berg平衡量表 0-56'"),
        ("tug_sec", "DECIMAL(5,1) DEFAULT NULL COMMENT '起立行走TUG秒'"),
        ("walk10m_sec", "DECIMAL(5,1) DEFAULT NULL COMMENT '10米步行秒'"),
        ("odi_score", "TINYINT DEFAULT NULL COMMENT 'ODI功能障碍指数 0-100'"),
        ("womac_score", "TINYINT DEFAULT NULL COMMENT 'WOMAC骨关节炎指数 0-100'"),
    ]:
        add_column("rehab_assessments", col, ddl)

    add_column("rehab_exercises", "contraindications", "TEXT COMMENT '运动禁忌/不宜进行的情况'")
    add_column("rehab_exercises", "alternatives", "TEXT COMMENT '替代动作建议'")

    db.execute("""
        CREATE TABLE IF NOT EXISTS rehab_screenings (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          patient_id BIGINT UNSIGNED NOT NULL,
          case_id BIGINT UNSIGNED DEFAULT NULL,
          assessor_id BIGINT UNSIGNED DEFAULT NULL,
          items_json TEXT COMMENT '筛查项 {key: true/false}',
          has_red_flag TINYINT DEFAULT 0,
          notes TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_patient (patient_id), KEY idx_case (case_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='红旗征筛查'
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS therapist_schedules (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          coach_id BIGINT UNSIGNED NOT NULL,
          work_date DATE NOT NULL,
          start_time VARCHAR(5) NOT NULL,
          end_time VARCHAR(5) NOT NULL,
          slot_min INT DEFAULT 30 COMMENT '每个号源分钟数',
          capacity INT DEFAULT 1 COMMENT '同时可预约人数',
          location VARCHAR(100) DEFAULT '康衡康复中心',
          note VARCHAR(255) DEFAULT '',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_coach_date (coach_id, work_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='治疗师排班'
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          patient_id BIGINT UNSIGNED NOT NULL,
          coach_id BIGINT UNSIGNED NOT NULL,
          schedule_id BIGINT UNSIGNED DEFAULT NULL,
          appt_date DATE NOT NULL,
          start_time VARCHAR(5) NOT NULL,
          end_time VARCHAR(5) DEFAULT '',
          appt_type VARCHAR(30) DEFAULT '门诊评估',
          status VARCHAR(20) DEFAULT 'booked' COMMENT 'booked/completed/cancelled',
          note VARCHAR(500) DEFAULT '',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_patient (patient_id), KEY idx_coach_date (coach_id, appt_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='康复预约'
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS treatment_cards (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          patient_id BIGINT UNSIGNED NOT NULL,
          case_id BIGINT UNSIGNED DEFAULT NULL,
          title VARCHAR(100) NOT NULL,
          total_sessions INT DEFAULT 10,
          used_sessions INT DEFAULT 0,
          valid_from DATE DEFAULT NULL,
          valid_to DATE DEFAULT NULL,
          status VARCHAR(20) DEFAULT 'active' COMMENT 'active/finished/expired',
          note VARCHAR(255) DEFAULT '',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_patient (patient_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='疗程卡'
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS followups (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          patient_id BIGINT UNSIGNED NOT NULL,
          coach_id BIGINT UNSIGNED NOT NULL,
          case_id BIGINT UNSIGNED DEFAULT NULL,
          due_date DATE DEFAULT NULL,
          content VARCHAR(500) DEFAULT '',
          status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/sent',
          sent_at DATETIME DEFAULT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          KEY idx_patient (patient_id), KEY idx_coach (coach_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='随访提醒'
    """)
    print("  表结构就绪")


EXERCISE_SAFETY = {
    "肩部": ("急性肩袖撕裂、肩关节脱位未复位、术后未获医生许可的主动抬臂训练。",
             "钟摆运动、肩胛后缩训练、被动前屈（治疗师辅助）。"),
    "肘腕": ("骨折未愈合、急性腱鞘炎红肿热痛期、腕管综合征急性麻木加重期。",
             "无痛范围腕关节活动度训练、握力等长收缩。"),
    "颈腰椎": ("脊柱骨折、马尾综合征（鞍区麻木/大小便障碍）、进行性下肢无力。",
              "腹式呼吸、臀桥；伸展方向训练需先由治疗师评估。"),
    "胸背": ("胸椎骨折、严重骨质疏松、胸部术后伤口未愈合。",
             "呼吸训练、肩胛后缩、坐位胸廓活动度训练。"),
    "核心躯干": ("腹主动脉瘤、疝气急性期、产后早期腹直肌分离未评估。",
               "腹式呼吸核心激活、改良平板支撑（跪姿）。"),
    "髋部": ("髋关节置换术后脱位风险期、髋部骨折未愈合。",
             "臀肌等长收缩、踝泵运动、无痛范围被动活动。"),
    "膝部": ("急性韧带撕裂、膝关节红肿发热期、术后负重限制期。",
             "股四头肌等长收缩、直腿抬高、踝泵运动。"),
    "踝足": ("踝部骨折未愈合、跟腱断裂急性期、急性严重肿胀。",
             "踝泵运动、无负重踝关节活动度训练。"),
    "平衡步态": ("严重眩晕发作期、跌倒高风险且无人陪护、视力严重受损未矫正。",
               "坐位平衡训练、扶稳双足并拢站立。"),
    "心肺全身": ("不稳定心绞痛、静息状态气促、未控制的高血压（>180/110mmHg）。",
               "缩唇呼吸、放松腹式呼吸、坐位低强度活动。"),
}


def migrate_exercise_safety():
    print("[2/3] 写入动作运动禁忌与替代方案…")
    for cat, (contra, alt) in EXERCISE_SAFETY.items():
        db.execute(
            "UPDATE rehab_exercises SET contraindications=%s, alternatives=%s "
            "WHERE is_custom=0 AND category=%s", (contra, alt, cat))


def seed_demo():
    print("[3/3] 补充演示数据…")
    today = date.today()

    # 3 个病例补齐标准量表：为已有评估补 Berg/TUG/10米步行/ODI/WOMAC
    fill = {
        1: [(48, 14.2, 10.5, None, None), (50, 13.0, 9.6, None, None),
            (52, 11.8, 8.9, None, None), (54, 10.9, 8.2, None, None)],
        2: [(44, 16.5, 12.4, 34, None), (47, 15.1, 11.2, 29, None),
            (50, 13.9, 10.1, 24, None), (52, 12.8, 9.4, 20, None)],
    }
    for case_id, values in fill.items():
        rows = db.query(
            "SELECT id FROM rehab_assessments WHERE case_id=%s ORDER BY assess_date DESC, id DESC LIMIT 4",
            (case_id,))
        for row, (berg, tug, walk, odi, womac) in zip(rows, values):
            db.execute(
                "UPDATE rehab_assessments SET berg_score=%s, tug_sec=%s, walk10m_sec=%s, "
                "odi_score=%s, womac_score=%s WHERE id=%s",
                (berg, tug, walk, odi, womac, row["id"]))

    # 病例 3（ACL 重建术后）补齐 3 次评估
    case3 = db.query("SELECT id, patient_id FROM rehab_cases WHERE id=3", one=True)
    if case3:
        exists = db.query("SELECT COUNT(*) c FROM rehab_assessments WHERE case_id=3", one=True)["c"]
        if not exists:
            demo = [
                (today - timedelta(days=42), 7, 32, 18.6, 15.2, None, 58, 45, 52, 48,
                 '{"膝屈曲":95,"膝伸展":-10}', '{"股四头肌":3}', "术后早期，疼痛明显，屈膝受限"),
                (today - timedelta(days=28), 5, 41, 15.8, 12.6, None, 52, 58, 62, 58,
                 '{"膝屈曲":112,"膝伸展":-5}', '{"股四头肌":4}', "肿胀减轻，可部分负重"),
                (today - timedelta(days=14), 3, 50, 12.9, 9.7, None, 44, 70, 74, 70,
                 '{"膝屈曲":128,"膝伸展":0}', '{"股四头肌":4}', "可上下楼，准备进入强化期"),
            ]
            for (d, vas, berg, tug, walk, odi, womac, bal, gait, adl, rom, mmt, notes) in demo:
                db.insert(
                    "INSERT INTO rehab_assessments (patient_id, case_id, assess_date, assessor_id, "
                    "pain_vas, berg_score, tug_sec, walk10m_sec, odi_score, womac_score, "
                    "rom_json, mmt_json, balance_score, gait_score, posture_score, adl_score, notes) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (case3["patient_id"], 3, d, 2, vas, berg, tug, walk, odi, womac,
                     rom, mmt, bal, gait, bal, adl, notes))

    # 给最近日志补练前/练后 VAS（趋势改善）
    for uid, base in ((4, 4), (5, 5), (6, 6), (7, 5)):
        rows = db.query(
            "SELECT id FROM rehab_logs WHERE user_id=%s "
            "ORDER BY checkin_date DESC, id DESC LIMIT 14", (uid,))
        for idx, row in enumerate(reversed(rows)):
            before = max(0, base - idx // 3)
            after = max(0, before - (1 if idx % 4 else 0))
            db.execute("UPDATE rehab_logs SET vas_before=%s, vas_after=%s WHERE id=%s",
                       (before, after, row["id"]))

    # 病例 3 患者近 6 天补 3 条带 VAS 的康复日志
    if case3:
        for offset, (before, after) in ((6, (5, 4)), (3, (4, 3)), (1, (3, 2))):
            d = today - timedelta(days=offset)
            exists = db.query("SELECT id FROM rehab_logs WHERE user_id=%s AND checkin_date=%s",
                              (case3["patient_id"], d), one=True)
            if not exists:
                db.insert(
                    "INSERT INTO rehab_logs (user_id, checkin_date, content, duration_min, intensity, "
                    "vas_before, vas_after) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (case3["patient_id"], d, "按方案完成膝周训练，疼痛较前减轻。", 55, 3, before, after))

    # 近一周训练日志（保证依从率与 VAS 趋势可演示）
    for uid, base in ((4, 3),):
        for offset in range(1, 7):
            d = today - timedelta(days=offset)
            exists = db.query("SELECT id FROM rehab_logs WHERE user_id=%s AND checkin_date=%s",
                              (uid, d), one=True)
            if exists:
                continue
            before = min(10, base + offset // 2)
            after = max(0, before - 1)
            db.insert(
                "INSERT INTO rehab_logs (user_id, checkin_date, content, duration_min, intensity, "
                "vas_before, vas_after) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (uid, d, "按康复方案完成训练，疼痛较前减轻，动作控制稳定。", 50, 3, before, after))

    # 保留一条练后疼痛加重记录，用于演示「练后 VAS 异常」预警
    bad = db.query("SELECT id FROM rehab_logs WHERE user_id=5 "
                   "ORDER BY checkin_date DESC, id DESC LIMIT 1", one=True)
    if bad:
        db.execute("UPDATE rehab_logs SET vas_before=3, vas_after=7 WHERE id=%s", (bad["id"],))

    # 红旗征筛查演示
    if not db.query("SELECT COUNT(*) c FROM rehab_screenings", one=True)["c"]:
        db.insert(
            "INSERT INTO rehab_screenings (patient_id, case_id, assessor_id, items_json, has_red_flag, notes) "
            "VALUES (%s,%s,%s,%s,0,%s)",
            (4, 1, 2, '{"fever":false,"night_pain":false,"saddle":false,"weakness":false,'
                      '"trauma":false,"cardiopulmonary":false,"wound":false,"dizziness":false}',
             "无红旗征，可按计划训练"))
        db.insert(
            "INSERT INTO rehab_screenings (patient_id, case_id, assessor_id, items_json, has_red_flag, notes) "
            "VALUES (%s,%s,%s,%s,1,%s)",
            (5, 3, 2, '{"fever":false,"night_pain":true,"saddle":false,"weakness":false,'
                      '"trauma":false,"cardiopulmonary":false,"wound":false,"dizziness":false}',
             "夜间静息痛明显，建议先骨科复查排除感染/血栓"))

    # 排班（未来 7 天）
    if not db.query("SELECT COUNT(*) c FROM therapist_schedules", one=True)["c"]:
        for coach_id in (2, 3):
            for i in range(1, 8):
                d = today + timedelta(days=i)
                if d.weekday() >= 5 and coach_id == 3:
                    continue
                db.insert(
                    "INSERT INTO therapist_schedules (coach_id, work_date, start_time, end_time, "
                    "slot_min, capacity, location, note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (coach_id, d, "09:00", "12:00", 30, 2,
                     "康衡康复中心 · 治疗区", "上午门诊评估/治疗"))

    # 疗程卡
    if not db.query("SELECT COUNT(*) c FROM treatment_cards", one=True)["c"]:
        db.insert(
            "INSERT INTO treatment_cards (patient_id, case_id, title, total_sessions, used_sessions, "
            "valid_from, valid_to, status, note) VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s)",
            (4, 1, "肩袖术后康复疗程卡（12次）", 12, 4,
             today - timedelta(days=30), today + timedelta(days=60), "含评估与手法治疗"))
        db.insert(
            "INSERT INTO treatment_cards (patient_id, case_id, title, total_sessions, used_sessions, "
            "valid_from, valid_to, status, note) VALUES (%s,%s,%s,%s,%s,%s,%s,'active',%s)",
            (5, 3, "ACL 术后康复疗程卡（10次）", 10, 3,
             today - timedelta(days=20), today + timedelta(days=70), "含评估、理疗与训练指导"))

    # 预约
    if not db.query("SELECT COUNT(*) c FROM appointments", one=True)["c"]:
        db.insert(
            "INSERT INTO appointments (patient_id, coach_id, appt_date, start_time, end_time, "
            "appt_type, status, note) VALUES (%s,%s,%s,%s,%s,%s,'booked',%s)",
            (4, 2, today + timedelta(days=1), "09:30", "10:00", "门诊评估", "肩关节活动度复评"))
        db.insert(
            "INSERT INTO appointments (patient_id, coach_id, appt_date, start_time, end_time, "
            "appt_type, status, note) VALUES (%s,%s,%s,%s,%s,%s,'completed',%s)",
            (5, 2, today - timedelta(days=1), "10:00", "10:30", "手法治疗", "膝关节松动+训练"))

    # 随访提醒
    if not db.query("SELECT COUNT(*) c FROM followups", one=True)["c"]:
        db.insert(
            "INSERT INTO followups (patient_id, coach_id, case_id, due_date, content, status) "
            "VALUES (%s,%s,%s,%s,%s,'pending')",
            (6, 2, 2, today, "近一周未记录康复日志，请回访了解腰痛情况并提醒复评。"))
        db.insert(
            "INSERT INTO followups (patient_id, coach_id, case_id, due_date, content, status, sent_at) "
            "VALUES (%s,%s,%s,%s,%s,'sent',NOW())",
            (7, 2, None, today - timedelta(days=2), "踝关节恢复情况回访。"))

    try:
        from app.services.checkin_service import recompute_streak
        for row in db.query("SELECT DISTINCT patient_id FROM rehab_cases"):
            recompute_streak(row["patient_id"])
    except Exception as exc:
        print(f"  跳过连续天数重算：{exc}")

    print("  演示数据完成")


if __name__ == "__main__":
    migrate_schema()
    migrate_exercise_safety()
    seed_demo()
    print("迁移完成。")
