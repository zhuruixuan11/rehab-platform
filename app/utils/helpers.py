import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from app.config import settings
from app.database import db

logger = logging.getLogger("fitness")

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/quicktime", "video/webm", "video/x-msvideo", "video/x-matroska"}


def today_str() -> str:
    return date.today().isoformat()


def month_range(year: int, month: int):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end - timedelta(days=1)


def week_monday(d: date = None) -> date:
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def parse_date(value: str, default: date = None) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return default or date.today()


def clamp_page(page: int, page_size: int, max_size: int = 100):
    page = max(1, page or 1)
    page_size = min(max(1, page_size or 20), max_size)
    return (page - 1) * page_size, page_size


def log_operation(admin_id, module: str, action: str, detail: str = "", ip: str = ""):
    try:
        db.execute(
            "INSERT INTO operation_logs (admin_id, module, action, detail, ip) VALUES (%s,%s,%s,%s,%s)",
            (admin_id, module, action, str(detail)[:1000], ip[:50]),
        )
    except Exception as exc:
        logger.warning("写操作日志失败: %s", exc)


def get_config(key: str, default: str = "") -> str:
    row = db.query("SELECT config_value FROM system_configs WHERE config_key = %s", (key,), one=True)
    return row["config_value"] if row else default


def get_config_int(key: str, default: int = 0) -> int:
    try:
        return int(get_config(key, str(default)))
    except ValueError:
        return default


def safe_filename(subdir: str, original_name: str, kind: str = "image") -> str:
    """生成不含用户输入的存储相对路径 uploads/<subdir>/<uuid>.<ext>"""
    ext = Path(original_name or "").suffix.lower()
    if kind == "image" and ext not in ALLOWED_IMAGE_EXT:
        ext = ".jpg"
    if kind == "video" and ext not in ALLOWED_VIDEO_EXT:
        ext = ".mp4"
    return f"{subdir}/{uuid.uuid4().hex}{ext}"


def validate_upload(filename: str, content_type: str, size: int, kind: str) -> str | None:
    """返回错误信息，None 表示通过。"""
    ext = Path(filename or "").suffix.lower()
    if kind == "image":
        if ext not in ALLOWED_IMAGE_EXT or (content_type and content_type not in ALLOWED_IMAGE_MIME):
            return "仅支持 jpg/png/gif/webp 图片"
        if size > settings.MAX_IMAGE_SIZE:
            return f"图片大小超出限制({settings.MAX_IMAGE_SIZE // 1024 // 1024}MB)"
    else:
        if ext not in ALLOWED_VIDEO_EXT or (content_type and content_type not in ALLOWED_VIDEO_MIME):
            return "仅支持 mp4/mov/webm/avi/mkv 视频"
        if size > settings.MAX_VIDEO_SIZE:
            return f"视频大小超出限制({settings.MAX_VIDEO_SIZE // 1024 // 1024}MB)"
    return None


async def save_upload_file(file, subdir: str, kind: str = "image") -> tuple[str | None, str]:
    """读取 UploadFile 并保存，返回 (相对路径或None, 错误信息)。"""
    content_type = file.content_type or ""
    filename = file.filename or ""
    data = await file.read()
    err = validate_upload(filename, content_type, len(data), kind)
    if err:
        return None, err
    rel_path = safe_filename(subdir, filename, kind)
    abs_path = settings.UPLOAD_DIR / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)
    return rel_path, ""


def json_dumps(obj) -> str:
    def default(o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        raise TypeError

    return json.dumps(obj, ensure_ascii=False, default=default)


def mask_sensitive(text: str) -> str:
    return re.sub(r"(password|token|secret)['\"]?\s*[:=]\s*['\"]?[^,'\"]+", r"\1=***", str(text), flags=re.I)
