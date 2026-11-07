"""P1/P2/P3 功能数据库迁移 2026-11-06。"""
from app.database import db

# ============ P1 ============
# AI姿势点评记录
db.execute("""
    CREATE TABLE IF NOT EXISTS ai_evaluations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        checkin_id INT,
        image_url VARCHAR(500) NOT NULL,
        score INT NOT NULL DEFAULT 0 COMMENT '0-100评分',
        analysis TEXT COMMENT 'AI分析结果(JSON/文本)',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ ai_evaluations")

# 邀请关系
db.execute("""
    CREATE TABLE IF NOT EXISTS invitations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        inviter_id INT NOT NULL,
        invitee_id INT NOT NULL,
        code VARCHAR(20) NOT NULL,
        reward_days INT NOT NULL DEFAULT 7 COMMENT '邀请人奖励会员天数',
        status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/claimed/expired',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_invitee (invitee_id),
        INDEX idx_inviter (inviter_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ invitations")

# 连续打卡奖励记录（防重复发放）
db.execute("""
    CREATE TABLE IF NOT EXISTS streak_rewards (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        streak_days INT NOT NULL COMMENT '达到的连续天数阈值',
        reward_days INT NOT NULL COMMENT '奖励会员天数',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_user_streak (user_id, streak_days)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ streak_rewards")

# 优惠券模板
db.execute("""
    CREATE TABLE IF NOT EXISTS coupons (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(32) UNIQUE NOT NULL,
        name VARCHAR(50) NOT NULL,
        type VARCHAR(10) NOT NULL COMMENT 'percent/fixed',
        value DECIMAL(10,2) NOT NULL COMMENT 'percent:折扣; fixed:减金额',
        min_amount DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '满减门槛',
        max_discount DECIMAL(10,2) COMMENT 'percent类型最大抵扣',
        start_date DATE,
        end_date DATE,
        max_usage INT NOT NULL DEFAULT 0 COMMENT '0=无限',
        used_count INT NOT NULL DEFAULT 0,
        status VARCHAR(10) NOT NULL DEFAULT 'active' COMMENT 'active/inactive',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ coupons")

# 用户优惠券领取/使用记录
db.execute("""
    CREATE TABLE IF NOT EXISTS user_coupons (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        coupon_id INT NOT NULL,
        status VARCHAR(10) NOT NULL DEFAULT 'unused' COMMENT 'unused/used/expired',
        used_at DATETIME,
        order_no VARCHAR(32),
        claimed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uniq_user_coupon (user_id, coupon_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ user_coupons")

# ============ P2 ============
# 教练提现申请
db.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        coach_id INT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected/paid',
        bank_name VARCHAR(50),
        bank_account VARCHAR(50),
        remark VARCHAR(200),
        processed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_coach (coach_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ withdrawals")

# 会员专属内容（教练/管理员发布的付费内容）
db.execute("""
    CREATE TABLE IF NOT EXISTS member_content (
        id INT AUTO_INCREMENT PRIMARY KEY,
        author_id INT NOT NULL,
        title VARCHAR(100) NOT NULL,
        content TEXT NOT NULL,
        cover_url VARCHAR(500),
        category VARCHAR(20) DEFAULT 'article' COMMENT 'article/video/course',
        view_count INT NOT NULL DEFAULT 0,
        status VARCHAR(10) NOT NULL DEFAULT 'published' COMMENT 'published/draft',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_author (author_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ member_content")

# ============ P3 ============
# 用户推送设置
db.execute("""
    CREATE TABLE IF NOT EXISTS push_settings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL UNIQUE,
        email_push TINYINT(1) NOT NULL DEFAULT 1,
        wechat_push TINYINT(1) NOT NULL DEFAULT 0,
        email VARCHAR(100)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ push_settings")

# 给学员加邀请码字段
try:
    db.execute("ALTER TABLE users ADD COLUMN invite_code VARCHAR(12) UNIQUE COMMENT '邀请码'")
except Exception as e:
    if "Duplicate" not in str(e):
        print(f"⚠ invite_code: {e}")
# 给所有用户生成邀请码
from app.database import db as _db
import random, string
def gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
users = _db.query("SELECT id FROM users WHERE invite_code IS NULL OR invite_code=''")
for u in users:
    _db.execute("UPDATE users SET invite_code=%s WHERE id=%s", (gen_code(), u["id"]))
print(f"✓ 已生成 {len(users)} 个邀请码")

# 给训练营加价格字段
try:
    db.execute("ALTER TABLE rehab_camps ADD COLUMN price DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '0=免费'")
    db.execute("ALTER TABLE rehab_camps ADD COLUMN is_paid TINYINT(1) NOT NULL DEFAULT 0")
except Exception as e:
    if "Duplicate" not in str(e):
        print(f"⚠ camps price: {e}")

# ============ 预置优惠券 ============
try:
    db.execute("""
        INSERT INTO coupons (code, name, type, value, min_amount, max_discount, start_date, end_date, max_usage, status)
        VALUES
        ('NEW50', '新人首单5折', 'percent', 50.00, 19.90, 50.00, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 90 DAY), 0, 'active'),
        ('OFF50', '满199减50', 'fixed', 50.00, 199.00, NULL, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 30 DAY), 0, 'active'),
        ('VIP80', 'VIP续费8折', 'percent', 80.00, 199.00, 60.00, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 60 DAY), 0, 'active')
    """)
except Exception as e:
    if "Duplicate" not in str(e):
        print(f"⚠ coupons seed: {e}")

# ============ 预置会员内容 ============
try:
    db.execute("""
        INSERT INTO member_content (author_id, title, content, category)
        VALUES
        (1, '7天减脂入门指南', '## 第一周：适应期\\n\\n1. 每天快走30分钟\\n2. 控制碳水摄入，主食减半\\n3. 蛋白质摄入：每公斤体重1.2g\\n\\n## 第二周：进阶\\n\\n1. 加入力量训练（徒手深蹲、俯卧撑）\\n2. 每周3次，每次20分钟\\n3. 热量缺口保持300-500大卡', 'article'),
        (1, '新手健身避坑指南', '很多新手健身2周就放弃，90%是因为犯了这5个错误：\\n\\n1. 一开始强度太大，全身酸痛3天\\n2. 只做有氧不做力量，代谢没提升\\n3. 饮食不控制，练完喝杯奶茶白练\\n4. 不记录数据，看不到进步\\n5. 没有计划，想到啥练啥\\n\\n解决：从健持开始，每天打卡记录，跟着教练计划走。', 'article')
    """)
except Exception as e:
    if "Duplicate" not in str(e):
        print(f"⚠ content seed: {e}")

print("\n========== P1/P2/P3 迁移完成 ==========")
