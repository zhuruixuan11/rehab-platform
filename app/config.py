import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


class Settings:
    BASE_DIR = BASE_DIR

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "rehab_tracker")
    DB_USER = os.getenv("DB_USER", "fitness_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "8"))

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "") or None
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
    if not UPLOAD_DIR.is_absolute():
        UPLOAD_DIR = BASE_DIR / UPLOAD_DIR
    MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", str(10 * 1024 * 1024)))
    MAX_VIDEO_SIZE = int(os.getenv("MAX_VIDEO_SIZE", str(500 * 1024 * 1024)))

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    BCRYPT_ROUNDS = 12

    # 邮件推送（SMTP）
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", "")
    SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "1") == "1"


settings = Settings()
