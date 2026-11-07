import logging
from logging.handlers import TimedRotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin, auth, camp, coach, community, features, member, messages, rehab, student, upload, ws


def setup_logging():
    log_dir = settings.BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    file_handler = TimedRotatingFileHandler(log_dir / "app.log", when="midnight",
                                            backupCount=30, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)


setup_logging()
logger = logging.getLogger("fitness")

app = FastAPI(
    title="康衡康复中心 - 全周期康复管理平台",
    description="患者/康复治疗师/管理员一体化运动康复管理平台，支持康复档案、康复评估与中医体质辨识",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")] if settings.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_control_middleware(request, call_next):
    """HTML 不缓存（改版即生效）；js/css 走协商缓存；媒体文件长缓存"""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path.startswith(("/js/", "/css/")):
        response.headers["Cache-Control"] = "no-cache"
    elif path.startswith(("/videos/", "/images/", "/uploads/")):
        response.headers["Cache-Control"] = "public, max-age=604800"
    return response

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(coach.router)
app.include_router(admin.router)
app.include_router(community.router)
app.include_router(camp.router)
app.include_router(messages.router)
app.include_router(upload.router)
app.include_router(ws.router)
app.include_router(member.router)
app.include_router(features.router)
app.include_router(rehab.router)

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
for sub in ("checkin", "avatars"):
    (settings.UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(settings.BASE_DIR / "static"), html=True), name="static")


@app.on_event("startup")
async def startup():
    from app.database import db
    try:
        db.query("SELECT 1 AS ok", one=True)
        logger.info("数据库连接正常: %s@%s/%s", settings.DB_USER, settings.DB_HOST, settings.DB_NAME)
    except Exception as exc:
        logger.error("数据库连接失败，请检查 MySQL 与 .env 配置: %s", exc)
    from app.redis_client import cache
    logger.info("Redis 状态: %s", "在线" if cache.available else "离线(内存缓存降级)")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
