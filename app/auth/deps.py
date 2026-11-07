from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_token
from app.database import db

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_LABEL = {"student": "学员", "coach": "教练", "admin": "管理员"}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未登录或缺少 Token")
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    user = db.query(
        "SELECT id, username, nickname, role, phone, gender, avatar, reminder_time, "
        "anonymous_rank, current_streak, longest_streak, status, invite_code FROM users WHERE id = %s",
        (user_id,),
        one=True,
    )
    if not user or user["status"] != 1:
        raise HTTPException(status_code=401, detail="账号不存在或已被禁用")
    return user


def require_role(*roles: str):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"需要 {('/'.join(ROLE_LABEL.get(r, r) for r in roles))} 权限")
        return user

    return checker
