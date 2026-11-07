from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.deps import bearer_scheme, get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.database import db
from app.models.schemas import LoginIn, PasswordChangeIn, ProfileUpdateIn, RegisterIn

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register")
def register(data: RegisterIn):
    exists = db.query("SELECT id FROM users WHERE username = %s", (data.username,), one=True)
    if exists:
        raise HTTPException(status_code=400, detail="用户名已被注册")
    user_id = db.insert(
        "INSERT INTO users (username, password_hash, nickname, role, phone) VALUES (%s,%s,%s,%s,%s)",
        (data.username, hash_password(data.password), data.nickname, data.role, data.phone))
    if data.role == "coach":
        db.insert(
            "INSERT INTO therapist_profiles (user_id, review_status) VALUES (%s,'pending')",
            (user_id,))
    user = db.query("SELECT id, username, nickname, role FROM users WHERE id = %s",
                    (user_id,), one=True)
    return {"token": create_access_token(user_id, data.role), "user": user}


@router.post("/login")
def login(data: LoginIn):
    user = db.query("SELECT * FROM users WHERE username = %s", (data.username,), one=True)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user["status"] != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    db.execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))
    token = create_access_token(user["id"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"], "username": user["username"], "nickname": user["nickname"],
            "role": user["role"], "avatar": user["avatar"],
            "current_streak": user["current_streak"],
        },
    }


@router.get("/avatar-presets")
def avatar_presets():
    """系统内置 Q 版卡通头像（无需登录即可选择）。"""
    from app.config import settings
    folder = settings.UPLOAD_DIR / "avatars"
    presets = []
    if folder.exists():
        for f in sorted(folder.glob("preset_*.*")):
            rel = f"avatars/{f.name}"
            presets.append({"path": rel, "url": f"/uploads/{rel}", "name": f.stem})
    return presets


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    profile = {k: v for k, v in user.items()}
    # 会员状态注入（所有角色都能拿）
    from app.routers.member import get_active_subscription, user_is_member
    profile["is_member"] = user_is_member(user["id"])
    sub = get_active_subscription(user["id"])
    profile["member_until"] = str(sub["expire_date"]) if sub else None
    profile["member_plan"] = sub["plan"] if sub else None
    if profile.get("reminder_time"):
        profile["reminder_time"] = str(profile["reminder_time"])
    if user["role"] == "coach":
        cp = db.query("SELECT real_name, bio, specialty, certifications, review_status, review_note, "
                      "accept_paid_plan, paid_plan_price, commission_rate, is_gold_cert "
                      "FROM therapist_profiles WHERE user_id = %s", (user["id"],), one=True)
        profile["coach_profile"] = cp
    profile["unread_messages"] = db.query(
        "SELECT COUNT(*) AS cnt FROM messages WHERE receiver_id = %s AND is_read = 0",
        (user["id"],), one=True)["cnt"]
    return profile


@router.put("/me")
def update_me(data: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    fields = {}
    if data.nickname is not None:
        fields["nickname"] = data.nickname
    if data.phone is not None:
        fields["phone"] = data.phone
    if data.gender is not None:
        fields["gender"] = data.gender
    if data.avatar is not None:
        fields["avatar"] = data.avatar
    if data.reminder_time is not None:
        fields["reminder_time"] = data.reminder_time
    if data.anonymous_rank is not None:
        fields["anonymous_rank"] = data.anonymous_rank
    if fields:
        sets = ", ".join(f"{k} = %s" for k in fields)
        db.execute(f"UPDATE users SET {sets} WHERE id = %s",
                   tuple(fields.values()) + (user["id"],))
    if user["role"] == "coach" and (data.coach_bio is not None or data.coach_specialty is not None):
        db.execute(
            "UPDATE therapist_profiles SET bio = COALESCE(%s, bio), specialty = COALESCE(%s, specialty) "
            "WHERE user_id = %s",
            (data.coach_bio, data.coach_specialty, user["id"]))
    return {"ok": True}


@router.put("/password")
def change_password(data: PasswordChangeIn, user: dict = Depends(get_current_user)):
    row = db.query("SELECT password_hash FROM users WHERE id = %s", (user["id"],), one=True)
    if not verify_password(data.old_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")
    db.execute("UPDATE users SET password_hash = %s WHERE id = %s",
               (hash_password(data.new_password), user["id"]))
    return {"ok": True}


@router.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    # JWT 无状态，登出由客户端丢弃 Token 即可
    return {"ok": True}
