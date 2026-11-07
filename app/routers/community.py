from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user
from app.database import db
from app.models.schemas import PostCommentIn, PostIn
from app.services.message_service import send_message
from app.utils.helpers import clamp_page

router = APIRouter(prefix="/api/community", tags=["社区动态"])

VIS_LABEL = {"public": "公开", "coach": "仅教练可见", "private": "仅自己可见"}


def _get_post(post_id: int) -> dict | None:
    return db.query(
        "SELECT id, user_id, visibility FROM community_posts WHERE id = %s",
        (post_id,), one=True)


def _can_see(post: dict, user: dict) -> bool:
    if post["user_id"] == user["id"] or user["role"] == "admin":
        return True
    if post["visibility"] == "public":
        return True
    if post["visibility"] == "coach":
        return user["role"] == "coach"
    return False


@router.get("/posts")
def list_posts(scope: str = "feed", page: int = 1, page_size: int = 10,
               user: dict = Depends(get_current_user)):
    params = []
    if scope == "mine":
        where = "p.user_id = %s"
        params.append(user["id"])
    elif user["role"] == "admin":
        where = "1=1"
    elif user["role"] == "coach":
        where = "(p.visibility IN ('public','coach') OR p.user_id = %s)"
        params.append(user["id"])
    else:
        where = "(p.visibility = 'public' OR p.user_id = %s)"
        params.append(user["id"])

    offset, size = clamp_page(page, page_size)
    total = db.query(f"SELECT COUNT(*) AS cnt FROM community_posts p WHERE {where}",
                     tuple(params), one=True)["cnt"]
    rows = db.query(
        f"SELECT p.id, p.user_id, p.content, p.media_paths, p.visibility, p.created_at, "
        f"u.nickname, u.avatar, u.role AS author_role, "
        f"(SELECT COUNT(*) FROM community_likes l WHERE l.post_id = p.id) AS like_count, "
        f"(SELECT COUNT(*) FROM community_likes l WHERE l.post_id = p.id AND l.user_id = %s) AS liked, "
        f"(SELECT COUNT(*) FROM community_comments c WHERE c.post_id = p.id) AS comment_count "
        f"FROM community_posts p JOIN users u ON u.id = p.user_id "
        f"WHERE {where} ORDER BY p.created_at DESC LIMIT %s OFFSET %s",
        (user["id"],) + tuple(params) + (size, offset))
    items = [{
        "id": r["id"], "user_id": r["user_id"], "nickname": r["nickname"],
        "avatar": r["avatar"], "author_role": r["author_role"],
        "content": r["content"],
        "media_paths": [m for m in (r["media_paths"] or "").split(",") if m],
        "visibility": r["visibility"], "visibility_label": VIS_LABEL[r["visibility"]],
        "like_count": r["like_count"], "liked": bool(r["liked"]),
        "comment_count": r["comment_count"], "created_at": str(r["created_at"]),
    } for r in rows]
    return {"total": total, "items": items, "page": page, "page_size": size}


@router.post("/posts", status_code=201)
def create_post(data: PostIn, user: dict = Depends(get_current_user)):
    if user["role"] not in ("student", "coach"):
        raise HTTPException(status_code=403, detail="仅学员和教练可发布动态")
    for p in data.media_paths[:9]:
        if ".." in p or p.startswith("/"):
            raise HTTPException(status_code=400, detail="非法图片路径")
    post_id = db.insert(
        "INSERT INTO community_posts (user_id, content, media_paths, visibility) "
        "VALUES (%s,%s,%s,%s)",
        (user["id"], data.content.strip(), ",".join(data.media_paths[:9]), data.visibility))
    return {"id": post_id}


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, user: dict = Depends(get_current_user)):
    post = _get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="动态不存在")
    if post["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能删除自己的动态")
    db.execute("DELETE FROM community_posts WHERE id = %s", (post_id,))
    return {"ok": True}


@router.post("/posts/{post_id}/like")
def toggle_like(post_id: int, user: dict = Depends(get_current_user)):
    post = _get_post(post_id)
    if not post or not _can_see(post, user):
        raise HTTPException(status_code=404, detail="动态不存在")
    existing = db.query("SELECT id FROM community_likes WHERE post_id = %s AND user_id = %s",
                        (post_id, user["id"]), one=True)
    if existing:
        db.execute("DELETE FROM community_likes WHERE id = %s", (existing["id"],))
        liked = False
    else:
        db.insert("INSERT INTO community_likes (post_id, user_id) VALUES (%s,%s)",
                  (post_id, user["id"]))
        liked = True
    cnt = db.query("SELECT COUNT(*) AS cnt FROM community_likes WHERE post_id = %s",
                   (post_id,), one=True)["cnt"]
    return {"liked": liked, "like_count": cnt}


@router.get("/posts/{post_id}/comments")
def list_comments(post_id: int, user: dict = Depends(get_current_user)):
    post = _get_post(post_id)
    if not post or not _can_see(post, user):
        raise HTTPException(status_code=404, detail="动态不存在")
    rows = db.query(
        "SELECT c.id, c.user_id, c.content, c.created_at, u.nickname, u.avatar, "
        "u.role AS author_role FROM community_comments c "
        "JOIN users u ON u.id = c.user_id WHERE c.post_id = %s "
        "ORDER BY c.created_at LIMIT 200", (post_id,))
    return [{**r, "created_at": str(r["created_at"])} for r in rows]


@router.post("/posts/{post_id}/comments", status_code=201)
def add_comment(post_id: int, data: PostCommentIn, user: dict = Depends(get_current_user)):
    post = _get_post(post_id)
    if not post or not _can_see(post, user):
        raise HTTPException(status_code=404, detail="动态不存在")
    comment_id = db.insert(
        "INSERT INTO community_comments (post_id, user_id, content) VALUES (%s,%s,%s)",
        (post_id, user["id"], data.content.strip()))
    if post["user_id"] != user["id"]:
        send_message(user["id"], post["user_id"], "text",
                     f"{user['nickname']} 评论了你的社区动态：{data.content[:80]}")
    return {"id": comment_id}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user: dict = Depends(get_current_user)):
    row = db.query("SELECT user_id FROM community_comments WHERE id = %s",
                   (comment_id,), one=True)
    if not row:
        raise HTTPException(status_code=404, detail="评论不存在")
    if row["user_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只能删除自己的评论")
    db.execute("DELETE FROM community_comments WHERE id = %s", (comment_id,))
    return {"ok": True}
