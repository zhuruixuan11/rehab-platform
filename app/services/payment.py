"""沙箱支付：显式订单状态机 + HMAC 签名回调 + 幂等入账。

状态机：pending --(签名回调)--> paid
        pending --(过期/取消)--> expired

不接真实支付渠道。`/api/member/sandbox/pay` 只负责“模拟网关”生成签名并投递回调，
真正的入账逻辑统一走 `handle_notify`，与将来替换成微信/支付宝回调时保持同一入口。
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from app.config import settings
from app.database import db


def new_order_no(user_id: int) -> str:
    return f"ORD{datetime.now():%Y%m%d%H%M%S}{user_id:04d}{uuid.uuid4().hex[:4].upper()}"


def new_flow_no(prefix: str = "PAY") -> str:
    return f"{prefix}{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}"


def sign(order_no: str, amount: float, timestamp: int) -> str:
    """HMAC-SHA256(order_no|amount|timestamp)，amount 固定两位小数。"""
    payload = f"{order_no}|{amount:.2f}|{timestamp}"
    return hmac.new(settings.SANDBOX_PAY_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_order(user_id: int, plan: str, amount: float, duration_days: int,
                 coach_id: int | None = None, bootcamp_id: int | None = None,
                 notes: str = "sandbox 下单") -> dict:
    """创建 pending 订单（订阅 + 支付流水），返回订单号与金额。"""
    order_no = new_order_no(user_id)
    today = date.today()
    existing = db.query(
        "SELECT expire_date FROM subscriptions WHERE user_id=%s AND status='paid' AND expire_date>=%s "
        "ORDER BY expire_date DESC LIMIT 1", (user_id, today), one=True)
    start = existing["expire_date"] if existing and plan in ("monthly", "yearly") else today
    expire = start + timedelta(days=duration_days)

    with db.transaction() as cursor:
        cursor.execute("""
            INSERT INTO subscriptions (user_id, plan, order_no, amount, status, start_date, expire_date,
                                       coach_id, bootcamp_id, notes)
            VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s)
        """, (user_id, plan, order_no, amount, start, expire, coach_id, bootcamp_id, notes))
        sub_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO user_payments (user_id, type, item_id, amount, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (user_id, plan, sub_id, amount))
    return {"order_no": order_no, "amount": round(float(amount), 2), "status": "pending",
            "expire_date": str(expire), "sandbox": True}


def handle_notify(order_no: str, amount: float, timestamp: int, sign_value: str) -> dict:
    """校验签名并幂等入账；重复回调返回 duplicate，不重复写账。"""
    now = int(time.time())
    if abs(now - int(timestamp)) > settings.SANDBOX_PAY_SIGN_TTL:
        raise HTTPException(400, "回调时间戳已过期")
    if not hmac.compare_digest(sign(order_no, float(amount), int(timestamp)), sign_value or ""):
        raise HTTPException(400, "回调签名校验失败")

    sub = db.query("SELECT * FROM subscriptions WHERE order_no=%s", (order_no,), one=True)
    if not sub:
        raise HTTPException(404, "订单不存在")
    if abs(float(sub["amount"]) - float(amount)) > 0.01:
        raise HTTPException(400, "回调金额与订单不一致")
    if sub["status"] == "paid":
        return {"ok": True, "duplicate": True, "order_no": order_no, "expire_date": str(sub["expire_date"])}
    if sub["status"] != "pending":
        raise HTTPException(400, f"订单状态 {sub['status']} 不可支付")

    flow_no = new_flow_no()
    affected = db.execute(
        "UPDATE subscriptions SET status='paid', paid_at=NOW(), notes=CONCAT(COALESCE(notes,''), %s) "
        "WHERE id=%s AND status='pending'",
        (f" | sandbox:{flow_no}", sub["id"]))
    if affected == 0:
        # 并发回调：另一个请求已完成入账，按幂等处理
        return {"ok": True, "duplicate": True, "order_no": order_no}
    db.execute("UPDATE user_payments SET status='paid' WHERE item_id=%s AND type=%s AND status='pending'",
               (sub["id"], sub["plan"]))

    plan_id = None
    if sub["plan"] == "paid_plan" and sub["coach_id"]:
        student = db.query("SELECT nickname FROM users WHERE id=%s", (sub["user_id"],), one=True)
        plan_id = db.insert("""
            INSERT INTO rehab_programs (student_id, coach_id, title, start_date, end_date, status, is_recommended)
            VALUES (%s, %s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 30 DAY), 'active', 1)
        """, (sub["user_id"], sub["coach_id"], f"【付费定制】{student['nickname']}的专属计划"))
        from app.services.message_service import send_message
        send_message(sub["user_id"], sub["coach_id"], "text",
                     f"🎉 学员 {student['nickname']} 付费 ¥{float(sub['amount']):.2f} 购买了你的定制计划，请尽快在「计划制定」中填充内容～")

    return {"ok": True, "duplicate": False, "order_no": order_no, "flow_no": flow_no,
            "expire_date": str(sub["expire_date"]), "plan_id": plan_id}


def sandbox_pay(order_no: str, user_id: int) -> dict:
    """模拟网关：取订单金额并生成签名，走与真实回调相同的校验入口。"""
    sub = db.query("SELECT * FROM subscriptions WHERE order_no=%s AND user_id=%s", (order_no, user_id), one=True)
    if not sub:
        raise HTTPException(404, "订单不存在")
    ts = int(time.time())
    return handle_notify(order_no, float(sub["amount"]), ts, sign(order_no, float(sub["amount"]), ts))
