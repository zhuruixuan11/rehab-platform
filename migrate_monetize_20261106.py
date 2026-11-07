from app.database import db

# ============ 变现数据库迁移 2026-11-06 ============
# 目标：加订阅/订单/教练付费开关，为第一笔收入铺路

# 1. coach_profiles 加付费定制字段
db.execute("""
    ALTER TABLE therapist_profiles
        ADD COLUMN accept_paid_plan TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否接受付费定制计划',
        ADD COLUMN paid_plan_price DECIMAL(8,2) NOT NULL DEFAULT 49.00 COMMENT '定制计划定价(元)',
        ADD COLUMN commission_rate DECIMAL(5,2) NOT NULL DEFAULT 15.00 COMMENT '平台抽佣比例(%%)',
        ADD COLUMN is_gold_cert TINYINT(1) NOT NULL DEFAULT 0 COMMENT '黄金认证'
""")
print("✓ coach_profiles 加付费字段")

# 2. 用户订阅表
db.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        plan VARCHAR(20) NOT NULL DEFAULT 'monthly' COMMENT 'monthly/yearly/paid_plan/bootcamp',
        order_no VARCHAR(32) UNIQUE NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/refunded/expired',
        start_date DATE,
        expire_date DATE,
        coach_id INT COMMENT '关联教练(付费定制)',
        bootcamp_id INT COMMENT '关联训练营',
        notes TEXT,
        paid_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user (user_id),
        INDEX idx_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户订阅/订单'
""")
print("✓ subscriptions 表")

# 3. exercises 加付费/视频字段
db.execute("""
    ALTER TABLE rehab_exercises
        ADD COLUMN video_url VARCHAR(500) COMMENT 'B站教学视频URL',
        ADD COLUMN is_member_only TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否会员专属',
        ADD COLUMN sort_order INT NOT NULL DEFAULT 0 COMMENT '排序权重'
""")
print("✓ exercises 加视频/会员字段")

# 4. 用户消费记录表（给个人中心看）
db.execute("""
    CREATE TABLE IF NOT EXISTS user_payments (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        type VARCHAR(20) NOT NULL COMMENT 'membership/paid_plan/bootcamp',
        item_id INT COMMENT '关联subscriptions.id',
        amount DECIMAL(10,2) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'paid',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""")
print("✓ user_payments 表")

# 5. 给所有现有用户开1个月会员（迁移期福利，让老用户先体验会员功能）
import datetime
now = datetime.datetime.now()
expire = now + datetime.timedelta(days=30)
db.execute("""
    INSERT INTO subscriptions (user_id, plan, order_no, amount, status, start_date, expire_date, paid_at, notes)
    SELECT id, 'yearly', CONCAT('WELCOME_', id), 0.00, 'paid', CURDATE(), DATE_ADD(CURDATE(), INTERVAL 30 DAY), NOW(), '老用户迁移福利'
    FROM users
    WHERE role = 'student' AND id NOT IN (SELECT user_id FROM subscriptions WHERE status = 'paid')
""")
print("✓ 老用户迁移：所有学员送30天会员")

# 6. 给教练开付费定制开关（方便你手动推第一批教练）
coach_ids = [2, 3]  # coach_li, coach_wang
for cid in coach_ids:
    db.execute("""
        UPDATE therapist_profiles SET accept_paid_plan = 1, paid_plan_price = 49.00, commission_rate = 15.00
        WHERE user_id = %s
    """, (cid,))
print("✓ 已给2位教练开启付费定制开关")

# 7. 给现有exercises加B站视频链接 + 会员标识
video_map = {
    "杠铃卧推": "https://search.bilibili.com/all?keyword=%E6%9D%A0%E9%93%83%E5%8D%A7%E6%8E%A8%E6%95%99%E5%AD%A6",
    "高位下拉": "https://search.bilibili.com/all?keyword=%E9%AB%98%E4%BD%8D%E4%B8%8B%E6%8B%89%E6%95%99%E5%AD%A6",
    "平板支撑": "https://search.bilibili.com/all?keyword=%E5%B9%B3%E6%9D%BF%E6%94%AF%E6%92%91%E6%95%99%E5%AD%A6",
    "深蹲": "https://search.bilibili.com/all?keyword=%E6%B7%B1%E8%B8%AA%E6%95%99%E5%AD%A6",
    "硬拉": "https://search.bilibili.com/all?keyword=%E7%A1%AC%E6%8B%89%E6%95%99%E5%AD%A6",
    "俯卧撑": "https://search.bilibili.com/all?keyword=%E4%BF%AF%E5%8D%A7%E6%92%91%E6%95%99%E5%AD%A6",
    "引体向上": "https://search.bilibili.com/all?keyword=%E5%BC%95%E4%BD%93%E5%90%91%E4%B8%8A%E6%95%99%E5%AD%A6",
    "哑铃推举": "https://search.bilibili.com/all?keyword=%E9%93%83%E9%93%83%E6%8E%A8%E4%B8%BE%E6%95%99%E5%AD%A6",
    "保加利亚分腿蹲": "https://search.bilibili.com/all?keyword=%E4%BF%9D%E5%8A%A0%E5%88%A9%E5%88%86%E8%85%BF%E8%B8%A2%E6%95%99%E5%AD%A6",
    "悬垂举腿": "https://search.bilibili.com/all?keyword=%E6%82%AC%E5%9E%82%E4%B8%BE%E8%85%BF%E6%95%99%E5%AD%A6",
}
for name, url in video_map.items():
    db.execute("UPDATE rehab_exercises SET video_url = %s WHERE name = %s", (url, name))
# 超过10个的动作标记为会员专属（免费版限10个）
db.execute("""
    UPDATE rehab_exercises SET is_member_only = 1 WHERE id > 10
""")
print(f"✓ exercises 已加视频链接和会员标记")

print("\n========== 迁移完成 ==========")
print(f"  subscriptions: 已有 {db.query('SELECT COUNT(*) c FROM subscriptions', one=True)['c']} 条老用户福利订阅")
print(f"  教练付费开关: 已打开 {db.query('SELECT COUNT(*) c FROM therapist_profiles WHERE accept_paid_plan=1', one=True)['c']} 位")
print(f"  会员专属动作: {db.query('SELECT COUNT(*) c FROM rehab_exercises WHERE is_member_only=1', one=True)['c']} / {db.query('SELECT COUNT(*) c FROM rehab_exercises', one=True)['c']}")
