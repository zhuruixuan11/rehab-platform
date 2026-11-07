"""Docker 启动初始化：等待数据库就绪，按需执行迁移与种子数据（幂等，可随容器反复重启）。"""
import subprocess
import sys
import time

from app.database import db


def wait_for_db(retries=60, delay=2):
    for i in range(retries):
        try:
            db.query("SELECT 1 AS ok", one=True)
            print("[init] 数据库连接就绪")
            return True
        except Exception:
            if i == retries - 1:
                return False
            time.sleep(delay)
    return False


def wait_for_schema(retries=30, delay=2):
    for i in range(retries):
        if table_exists("users"):
            return True
        time.sleep(delay)
    return False


def table_exists(name):
    row = db.query(
        "SELECT COUNT(*) AS c FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s", (name,), one=True)
    return row and row["c"] > 0


def column_exists(table, column):
    row = db.query(
        "SELECT COUNT(*) AS c FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column), one=True)
    return row and row["c"] > 0


def run_script(path):
    print(f"[init] 执行 {path}")
    result = subprocess.run([sys.executable, path])
    if result.returncode != 0:
        raise RuntimeError(f"{path} 执行失败")


def main():
    if not wait_for_db():
        print("[init] 错误: 等待数据库超时")
        sys.exit(1)

    if not wait_for_schema():
        print("[init] 错误: users 表不存在，请确认 mysql 容器首次启动时加载了 sql/init.sql"
              "（如数据卷是旧的，请 docker compose down -v 后重试）")
        sys.exit(1)

    if db.query("SELECT id FROM rehab_exercises WHERE name = %s", ("双杠臂屈伸",), one=True) is None:
        run_script("migrate_20260826.py")
    else:
        print("[init] 动作库扩充已应用，跳过")

    if not table_exists("camps"):
        run_script("migrate_20260827.py")
    else:
        print("[init] 训练营表已存在，跳过")

    if not column_exists("exercises", "muscles"):
        run_script("migrate_20260828.py")
    else:
        print("[init] 动作可视化字段已存在，跳过")

    if db.query("SELECT id FROM users WHERE username = %s", ("admin",), one=True) is None:
        run_script("seed.py")
    else:
        print("[init] 演示账号已存在，跳过 seed")

    if db.query("SELECT COUNT(*) AS c FROM rehab_camps", one=True)["c"] == 0:
        try:
            run_script("seed_camp_demo.py")
        except Exception as exc:
            print(f"[init] 演示营创建失败（不影响启动）: {exc}")
    else:
        print("[init] 已存在营期数据，保留现有数据")

    print("[init] 初始化完成，启动服务")


if __name__ == "__main__":
    main()
