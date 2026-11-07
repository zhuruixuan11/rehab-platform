"""P1/P2 变现功能接口：AI点评 / 邀请裂变 / 优惠券 / 教练收益提现 / 营收看板 / 会员内容墙。"""
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user, require_role
from app.config import settings
from app.database import db
from app.routers.member import user_is_member, get_active_subscription
from app.utils.email import send_email, is_configured, checkin_reminder_html

router = APIRouter(prefix="/api/features", tags=["变现功能"])


# ==================== P1-6 AI姿势点评 ====================
class AIEvaluateIn(BaseModel):
    image_url: str
    checkin_id: int | None = None


@router.post("/ai-evaluate")
def ai_evaluate(data: AIEvaluateIn, user: dict = Depends(get_current_user)):
    """上传打卡图片，AI姿势点评（会员专属）。Mock返回模拟分析，真实上线接百度AI人体关键点。"""
    if not user_is_member(user["id"]):
        raise HTTPException(403, "AI姿势点评为会员专属功能")
    # 模拟AI评分（真实接百度AI: https://aip.baidubce.com/rest/2.0/image-classify/v1/body_analysis）
    import random
    score = random.randint(65, 95)
    analysis = {
        "score": score,
        "pose": "深蹲" if "squat" in (data.image_url or "") else "综合动作",
        "issues": [
            "膝盖略微超过脚尖，建议重心后移",
            "背部微弓，注意收紧核心保持挺直",
        ] if score < 85 else ["动作标准，保持！"],
        "tips": "建议每组间休息60秒，注意呼吸节奏"
    }
    db.execute("INSERT INTO ai_evaluations (user_id, checkin_id, image_url, score, analysis) VALUES (%s,%s,%s,%s,%s)",
               (user["id"], data.checkin_id, data.image_url, score, str(analysis)))
    eid = db.query("SELECT LAST_INSERT_ID() id", one=True)["id"]
    return {"id": eid, "score": score, "analysis": analysis}


@router.get("/ai-evaluations")
def list_evaluations(page: int = 1, page_size: int = 10, user: dict = Depends(get_current_user)):
    offset = (page - 1) * page_size
    rows = db.query("SELECT * FROM ai_evaluations WHERE user_id=%s ORDER BY id DESC LIMIT %s OFFSET %s",
                    (user["id"], page_size, offset))
    for r in rows:
        try: r["analysis"] = eval(r["analysis"])
        except: pass
    return rows


# ==================== P1-8 邀请裂变 ====================
@router.get("/invite/info")
def invite_info(user: dict = Depends(get_current_user)):
    """获取我的邀请码、邀请链接、已邀请人数和获得的奖励。"""
    total = db.query("SELECT COUNT(*) c FROM invitations WHERE inviter_id=%s AND status='claimed'", (user["id"],), one=True)["c"]
    list_inv = db.query("SELECT i.*, u.nickname FROM invitations i JOIN users u ON u.id=i.invitee_id "
                        "WHERE i.inviter_id=%s ORDER BY i.id DESC LIMIT 20", (user["id"],))
    return {
        "invite_code": user.get("invite_code") or "",
        "invite_link": f"http://localhost:8002/register?code={user.get('invite_code','')}",
        "invited_count": total,
        "reward_days_total": total * 7,
        "list": list_inv,
    }


@router.post("/invite/claim")
def invite_claim(code: str, user: dict = Depends(get_current_user)):
    """新用户注册后填写邀请码，邀请人得7天会员。"""
    inviter = db.query("SELECT id FROM users WHERE invite_code=%s", (code,), one=True)
    if not inviter:
        raise HTTPException(400, "邀请码无效")
    if inviter["id"] == user["id"]:
        raise HTTPException(400, "不能邀请自己")
    exists = db.query("SELECT id FROM invitations WHERE invitee_id=%s", (user["id"],), one=True)
    if exists:
        raise HTTPException(400, "你已填写过邀请码")
    # 记录邀请
    db.execute("INSERT INTO invitations (inviter_id, invitee_id, code, reward_days, status) VALUES (%s,%s,%s,7,'claimed')",
               (inviter["id"], user["id"], code))
    # 给邀请人加7天会员
    today = date.today()
    sub = get_active_subscription(inviter["id"])
    start = sub["expire_date"] if sub else today
    expire = start + timedelta(days=7)
    db.execute("INSERT INTO subscriptions (user_id, plan, order_no, amount, status, start_date, expire_date, notes) "
               "VALUES (%s,'monthly', %s, 0, 'paid', %s, %s, '邀请好友奖励')",
               (inviter["id"], f"INV_{user['id']}", start, expire))
    return {"ok": True, "msg": "邀请成功！邀请人获得7天会员"}


# ==================== P1-10 优惠券 ====================
@router.get("/coupons")
def list_coupons(user: dict = Depends(get_current_user)):
    """可用优惠券列表（未过期、active）。"""
    today = date.today()
    return db.query("SELECT * FROM coupons WHERE status='active' AND (start_date IS NULL OR start_date<=%s) "
                    "AND (end_date IS NULL OR end_date>=%s) ORDER BY id DESC",
                    (today, today))


@router.post("/coupons/{coupon_id}/claim")
def claim_coupon(coupon_id: int, user: dict = Depends(get_current_user)):
    c = db.query("SELECT * FROM coupons WHERE id=%s AND status='active'", (coupon_id,), one=True)
    if not c:
        raise HTTPException(404, "优惠券不存在或已失效")
    try:
        db.execute("INSERT INTO user_coupons (user_id, coupon_id) VALUES (%s,%s)", (user["id"], coupon_id))
    except:
        raise HTTPException(400, "你已领取过该优惠券")
    db.execute("UPDATE coupons SET used_count=used_count+1 WHERE id=%s", (coupon_id,))
    return {"ok": True}


@router.get("/coupons/mine")
def my_coupons(user: dict = Depends(get_current_user)):
    return db.query("SELECT uc.*, c.name, c.type, c.value, c.min_amount, c.max_discount, c.end_date "
                    "FROM user_coupons uc JOIN coupons c ON c.id=uc.coupon_id "
                    "WHERE uc.user_id=%s ORDER BY uc.id DESC", (user["id"],))


# ==================== P2-11 营收看板（管理员） ====================
@router.get("/revenue/dashboard")
def revenue_dashboard(user: dict = Depends(require_role("admin"))):
    total_rev = db.query("SELECT COALESCE(SUM(amount),0) t FROM subscriptions WHERE status='paid'", one=True)["t"]
    month_rev = db.query("SELECT COALESCE(SUM(amount),0) t FROM subscriptions WHERE status='paid' AND MONTH(paid_at)=MONTH(NOW()) AND YEAR(paid_at)=YEAR(NOW())", one=True)["t"]
    today_rev = db.query("SELECT COALESCE(SUM(amount),0) t FROM subscriptions WHERE status='paid' AND DATE(paid_at)=CURDATE()", one=True)["t"]
    member_cnt = db.query("SELECT COUNT(DISTINCT user_id) c FROM subscriptions WHERE status='paid' AND expire_date>=CURDATE()", one=True)["c"]
    plan_orders = db.query("SELECT COUNT(*) c FROM subscriptions WHERE plan='paid_plan'", one=True)["c"]
    bootcamp_orders = db.query("SELECT COUNT(*) c FROM subscriptions WHERE plan='bootcamp'", one=True)["c"]
    # 近30天营收趋势
    trend = db.query("SELECT DATE(paid_at) d, COALESCE(SUM(amount),0) amount FROM subscriptions "
                     "WHERE status='paid' AND paid_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) GROUP BY DATE(paid_at) ORDER BY d")
    return {
        "total_revenue": float(total_rev),
        "month_revenue": float(month_rev),
        "today_revenue": float(today_rev),
        "active_members": member_cnt,
        "paid_plan_orders": plan_orders,
        "bootcamp_orders": bootcamp_orders,
        "trend": [{"date": str(r["d"]), "amount": float(r["amount"])} for r in trend],
    }


# ==================== P2-12 教练收益 + 提现 ====================
def _coach_balance(coach_id: int) -> dict:
    """教练收益余额：付费定制抽成收入 - 已提现 - 待审核。"""
    rows = db.query("SELECT s.amount, cp.commission_rate FROM subscriptions s "
                    "JOIN therapist_profiles cp ON cp.user_id=s.coach_id "
                    "WHERE s.coach_id=%s AND s.plan='paid_plan' AND s.status='paid'", (coach_id,))
    total_earned = 0.0
    for r in rows:
        rate = float(r["commission_rate"] or 15)
        total_earned += float(r["amount"]) * (100 - rate) / 100
    withdrawn = float(db.query("SELECT COALESCE(SUM(amount),0) t FROM withdrawals WHERE coach_id=%s AND status IN ('approved','paid')",
                               (coach_id,), one=True)["t"])
    pending = float(db.query("SELECT COALESCE(SUM(amount),0) t FROM withdrawals WHERE coach_id=%s AND status='pending'",
                             (coach_id,), one=True)["t"])
    return {"total_earned": round(total_earned, 2), "withdrawn": round(withdrawn, 2),
            "pending": round(pending, 2), "available": round(total_earned - withdrawn - pending, 2)}


@router.get("/coach/earnings")
def coach_earnings(user: dict = Depends(require_role("coach"))):
    """教练收益：付费定制抽成收入、提现记录。"""
    bal = _coach_balance(user["id"])
    bal["withdrawals"] = db.query("SELECT * FROM withdrawals WHERE coach_id=%s ORDER BY id DESC", (user["id"],))
    return bal


class WithdrawIn(BaseModel):
    amount: float
    bank_name: str
    bank_account: str
    remark: str | None = None


@router.post("/coach/withdraw")
def coach_withdraw(data: WithdrawIn, user: dict = Depends(require_role("coach"))):
    if data.amount <= 0:
        raise HTTPException(400, "金额必须大于0")
    available = _coach_balance(user["id"])["available"]
    if data.amount > available:
        raise HTTPException(400, f"超出可提现余额 ¥{available:.2f}")
    db.execute("INSERT INTO withdrawals (coach_id, amount, bank_name, bank_account, remark) VALUES (%s,%s,%s,%s,%s)",
               (user["id"], data.amount, data.bank_name, data.bank_account, data.remark))
    return {"ok": True, "msg": "提现申请已提交，等待管理员审核"}


@router.get("/admin/withdrawals")
def admin_withdrawals(status: str = None, user: dict = Depends(require_role("admin"))):
    where = "1=1"
    params = []
    if status:
        where = "w.status=%s"
        params.append(status)
    rows = db.query(f"SELECT w.*, u.nickname AS coach_name FROM withdrawals w JOIN users u ON u.id=w.coach_id "
                    f"WHERE {where} ORDER BY w.id DESC", tuple(params))
    return rows


@router.post("/admin/withdrawals/{wid}/process")
def process_withdraw(wid: int, action: str, user: dict = Depends(require_role("admin"))):
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action必须是approve或reject")
    st = "approved" if action == "approve" else "rejected"
    db.execute("UPDATE withdrawals SET status=%s, processed_at=NOW() WHERE id=%s", (st, wid))
    return {"ok": True}


# ==================== P2-13 会员内容墙 ====================
@router.get("/member-content")
def list_member_content(user: dict = Depends(get_current_user)):
    """会员内容墙。非会员只看标题+封面，不显示正文。"""
    rows = db.query("SELECT mc.*, u.nickname AS author_name FROM member_content mc JOIN users u ON u.id=mc.author_id "
                    "WHERE mc.status='published' ORDER BY mc.id DESC")
    is_member = user_is_member(user["id"])
    result = []
    for r in rows:
        item = {k: r[k] for k in ("id", "author_id", "author_name", "title", "cover_url", "category", "view_count", "created_at")}
        if is_member:
            item["content"] = r["content"]
        else:
            item["content"] = "🔒 开通会员后查看完整内容"
            item["is_locked"] = True
        result.append(item)
    return result


@router.get("/member-content/{cid}")
def member_content_detail(cid: int, user: dict = Depends(get_current_user)):
    r = db.query("SELECT mc.*, u.nickname AS author_name FROM member_content mc JOIN users u ON u.id=mc.author_id WHERE mc.id=%s",
                 (cid,), one=True)
    if not r:
        raise HTTPException(404, "内容不存在")
    is_member = user_is_member(user["id"])
    db.execute("UPDATE member_content SET view_count=view_count+1 WHERE id=%s", (cid,))
    item = {k: r[k] for k in ("id", "author_id", "author_name", "title", "cover_url", "category", "view_count", "created_at")}
    if is_member:
        item["content"] = r["content"]
    else:
        item["content"] = r["content"][:100] + "...\n\n🔒 开通会员后查看完整内容"
        item["is_locked"] = True
    return item


# ==================== P3-15 邮件推送 ====================
class PushSettingsIn(BaseModel):
    email_push: int = 1
    email: str | None = None


@router.get("/push/settings")
def get_push_settings(user: dict = Depends(get_current_user)):
    r = db.query("SELECT * FROM push_settings WHERE user_id=%s", (user["id"],), one=True)
    if not r:
        db.execute("INSERT INTO push_settings (user_id, email_push, email) VALUES (%s,1,%s)",
                   (user["id"], None))
        r = db.query("SELECT * FROM push_settings WHERE user_id=%s", (user["id"],), one=True)
    return {
        "email_push": bool(r["email_push"]),
        "email": r["email"],
        "smtp_configured": is_configured(),
    }


@router.put("/push/settings")
def update_push_settings(data: PushSettingsIn, user: dict = Depends(get_current_user)):
    exists = db.query("SELECT id FROM push_settings WHERE user_id=%s", (user["id"],), one=True)
    if exists:
        db.execute("UPDATE push_settings SET email_push=%s, email=%s WHERE user_id=%s",
                   (data.email_push, data.email, user["id"]))
    else:
        db.execute("INSERT INTO push_settings (user_id, email_push, email) VALUES (%s,%s,%s)",
                   (user["id"], data.email_push, data.email))
    return {"ok": True}


@router.post("/push/test-email")
def send_test_email(user: dict = Depends(get_current_user)):
    """给当前用户绑定的邮箱发送一封测试邮件。"""
    ps = db.query("SELECT email FROM push_settings WHERE user_id=%s", (user["id"],), one=True)
    to = (ps and ps["email"]) or user.get("email")
    if not to:
        raise HTTPException(400, "请先在推送设置中填写邮箱")
    ok = send_email(to, "健持 - 邮件推送测试",
                    "<div style='padding:20px'><h2>📬 邮件推送已生效</h2>"
                    "<p>这是一封来自健持的测试邮件，说明你的 SMTP 配置正确。</p></div>")
    if not ok:
        raise HTTPException(500, "邮件发送失败，请检查 SMTP 配置")
    return {"ok": True}


@router.post("/push/remind-checkin")
def remind_checkin(user: dict = Depends(require_role("admin"))):
    """管理员手动触发：给所有开启邮件推送且今日未打卡的学员发送打卡提醒。
    也可配置系统 cron 定时调用此接口实现每日自动提醒。"""
    today = date.today().isoformat()
    rows = db.query(
        "SELECT u.id, u.nickname, u.current_streak, ps.email FROM users u "
        "JOIN push_settings ps ON ps.user_id=u.id "
        "LEFT JOIN rehab_logs c ON c.user_id=u.id AND c.checkin_date=%s AND c.is_makeup=0 "
        "WHERE u.role='student' AND ps.email_push=1 AND ps.email IS NOT NULL AND c.id IS NULL",
        (today,))
    sent = 0
    for r in rows:
        if send_email(r["email"], "⏰ 健持打卡提醒", checkin_reminder_html(r["nickname"], r["current_streak"] or 0)):
            sent += 1
    return {"target": len(rows), "sent": sent}


@router.get("/push/smtp-status")
def smtp_status(user: dict = Depends(require_role("admin"))):
    return {"configured": is_configured(), "host": settings.SMTP_HOST if is_configured() else None}
