"""一次性迁移脚本（2026-08-27）：
训练营模块：新增 camps / camp_members / camp_messages 三张表，
training_plans 增加 camp_id 列，并写入营期消息模板。

用法：在项目根目录执行  python migrate_20260827.py
"""
from app.database import db

TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS rehab_camps (
      id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      coach_id     BIGINT UNSIGNED NOT NULL,
      title        VARCHAR(100) NOT NULL COMMENT '如：21天减脂训练营第3期',
      description  VARCHAR(500) DEFAULT '',
      cover_path   VARCHAR(255) DEFAULT '',
      start_date   DATE NOT NULL,
      end_date     DATE NOT NULL,
      capacity     INT DEFAULT 30 COMMENT '人数上限',
      invite_code  CHAR(8) NOT NULL UNIQUE COMMENT '学员自助加入用',
      status       ENUM('draft','recruiting','ongoing','ended') DEFAULT 'draft',
      report_json  JSON DEFAULT NULL COMMENT '结营报告',
      created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_camps_coach (coach_id, status),
      CONSTRAINT fk_camp_coach FOREIGN KEY (coach_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS rehab_camp_members (
      id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      camp_id    BIGINT UNSIGNED NOT NULL,
      user_id    BIGINT UNSIGNED NOT NULL,
      joined_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
      status     ENUM('active','quit') DEFAULT 'active',
      UNIQUE KEY uq_camp_member (camp_id, user_id),
      INDEX idx_camp_members_user (user_id),
      CONSTRAINT fk_cm_camp FOREIGN KEY (camp_id) REFERENCES camps(id) ON DELETE CASCADE,
      CONSTRAINT fk_cm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS rehab_camp_messages (
      id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      camp_id    BIGINT UNSIGNED NOT NULL,
      sender_id  BIGINT UNSIGNED DEFAULT NULL COMMENT 'NULL为系统消息',
      msg_type   ENUM('text','image','voice','video','system') DEFAULT 'text',
      content    VARCHAR(2000) DEFAULT '',
      media_path VARCHAR(255) DEFAULT '',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      INDEX idx_camp_msg (camp_id, id),
      CONSTRAINT fk_cmsg_camp FOREIGN KEY (camp_id) REFERENCES camps(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]

TEMPLATES = [
    ("营期开营通知", "【{camp_title}】今天正式开营啦！为期{camp_days}天，跟着计划练，营内排行榜等你来冲！", "训练营"),
    ("营期打卡提醒", "{nickname}，【{camp_title}】今天还没打卡哦，距结营还剩{camp_days_left}天，加油！", "训练营"),
    ("营期结营通知", "【{camp_title}】圆满结营！快来看看你的结营报告和营内最终排名吧。", "训练营"),
]


def migrate():
    for sql in TABLES_SQL:
        try:
            db.execute(sql)
        except Exception as exc:
            if "already exists" in str(exc):
                continue
            raise
    print("[OK] camps / camp_members / camp_messages 表已就绪")

    cols = db.query("SHOW COLUMNS FROM rehab_programs LIKE 'camp_id'")
    if not cols:
        db.execute("ALTER TABLE rehab_programs "
                   "ADD COLUMN camp_id BIGINT UNSIGNED DEFAULT NULL COMMENT '所属营期，NULL为普通1v1计划', "
                   "ADD INDEX idx_plans_camp (camp_id)")
        print("[OK] training_plans 已增加 camp_id 列")
    else:
        print("[SKIP] training_plans.camp_id 已存在")

    added = 0
    for title, content, category in TEMPLATES:
        exists = db.query("SELECT id FROM message_templates WHERE title = %s", (title,), one=True)
        if exists:
            continue
        db.execute("INSERT INTO message_templates (coach_id, title, content, category) "
                   "VALUES (NULL,%s,%s,%s)", (title, content, category))
        added += 1
    print(f"[OK] 营期消息模板新增 {added} 个（已存在则跳过）")


if __name__ == "__main__":
    migrate()
