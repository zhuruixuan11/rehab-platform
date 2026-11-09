"""A4 清雷：邮件 outbox 表 + 提现流水号字段（幂等迁移，可重复执行）。"""
import pymysql

from app.config import settings


def main():
    conn = pymysql.connect(host=settings.DB_HOST, port=settings.DB_PORT, database=settings.DB_NAME,
                           user=settings.DB_USER, password=settings.DB_PASSWORD, charset="utf8mb4",
                           autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS email_outbox (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  to_addr VARCHAR(120) NOT NULL,
                  subject VARCHAR(200) NOT NULL,
                  html MEDIUMTEXT,
                  status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/sent/failed',
                  attempts INT DEFAULT 0,
                  last_error VARCHAR(500),
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  sent_at DATETIME,
                  INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邮件待发箱'
            """)
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema=%s AND table_name='withdrawals' AND column_name='flow_no'
            """, (settings.DB_NAME,))
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE withdrawals ADD COLUMN flow_no VARCHAR(32) DEFAULT NULL "
                            "COMMENT '提现流水号' AFTER status")
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema=%s AND table_name='withdrawals' AND index_name='idx_flow_no'
            """, (settings.DB_NAME,))
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE withdrawals ADD UNIQUE INDEX idx_flow_no (flow_no)")
        print("A4 migration done")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
