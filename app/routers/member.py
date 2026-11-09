"""变现相关接口（订阅/会员/教练付费定制/订单）。"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import get_current_user, require_role
from app.database import db
from app.services import payment

router = APIRouter(prefix="/api/member", tags=["会员/变现"])


# ---------- 数据模型 ----------
class SubscribeIn(BaseModel):
    plan: str           # monthly / yearly / paid_plan / bootcamp
    months: int = 1     # monthly 时可选 1/3/6/12
    coach_id: int | None = None   # paid_plan 时必填
    bootcamp_id: int | None = None


# ---------- 会员状态 ----------
def user_is_member(user_id: int) -> bool:
    today = date.today()
    row = db.query(
        "SELECT 1 FROM subscriptions WHERE user_id = %s AND status = 'paid' AND expire_date >= %s AND plan IN ('monthly','yearly') "
        "ORDER BY expire_date DESC LIMIT 1",
        (user_id, today), one=True)
    return bool(row)


def get_active_subscription(user_id: int):
    today = date.today()
    return db.query(
        "SELECT * FROM subscriptions WHERE user_id = %s AND status = 'paid' AND expire_date >= %s "
        "ORDER BY expire_date DESC LIMIT 1",
        (user_id, today), one=True)


@router.get("/status")
def member_status(user: dict = Depends(get_current_user)):
    """返回当前用户会员状态、可用功能、教练付费定制列表。"""
    sub = get_active_subscription(user["id"])
    coach_list = []
    if user["role"] == "student":
        coach_list = db.query("""
            SELECT u.id AS user_id, u.nickname, u.avatar, cp.paid_plan_price, cp.specialty, cp.bio, cp.commission_rate
            FROM therapist_profiles cp JOIN users u ON u.id = cp.user_id
            WHERE cp.review_status = 'approved' AND cp.accept_paid_plan = 1
        """)
    payments = db.query(
        "SELECT p.*, s.notes FROM user_payments p LEFT JOIN subscriptions s ON s.id = p.item_id "
        "WHERE p.user_id = %s ORDER BY p.created_at DESC LIMIT 20", (user["id"],))
    return {
        "is_member": bool(sub),
        "subscription": {
            "plan": sub["plan"] if sub else None,
            "start_date": str(sub["start_date"]) if sub else None,
            "expire_date": str(sub["expire_date"]) if sub else None,
        },
        "member_until": str(sub["expire_date"]) if sub else None,
        "paid_coaches": coach_list,
        "payments": payments,
        "plans": [
            {"key": "monthly", "title": "月度会员", "price": 19.9, "unit": "月", "desc": "无限教练计划、全部动作库、AI姿态点评、专属徽章"},
            {"key": "yearly", "title": "年度会员", "price": 199.0, "unit": "年", "desc": "享月度全部权益，合¥16.6/月（省¥40）", "hot": True},
            {"key": "paid_plan", "title": "教练1v1定制计划", "price": 49.0, "unit": "次", "desc": "认证教练1对1根据你的身体数据定制30天训练方案"},
        ],
    }


# ---------- 订阅/下单（沙箱支付） ----------
@router.post("/subscribe")
def subscribe(data: SubscribeIn, user: dict = Depends(get_current_user)):
    """创建 pending 订单并返回沙箱收银台参数；支付成功以签名回调为准。"""
    if user["role"] != "student":
        raise HTTPException(403, "仅学员可以订阅")

    prices = {"monthly": 19.90, "yearly": 199.00}
    months_map = {1: 19.90, 3: 49.90, 6: 89.90, 12: 159.00}

    if data.plan == "monthly":
        amount = months_map.get(data.months, 19.90)
        duration_days = 30 * data.months
    elif data.plan == "yearly":
        amount = prices["yearly"]
        duration_days = 365
    elif data.plan == "paid_plan":
        if not data.coach_id:
            raise HTTPException(400, "请选择教练")
        coach = db.query("SELECT paid_plan_price, accept_paid_plan FROM therapist_profiles WHERE user_id=%s AND accept_paid_plan=1",
                         (data.coach_id,), one=True)
        if not coach:
            raise HTTPException(404, "该教练未开放付费定制")
        amount = float(coach["paid_plan_price"])
        duration_days = 30
    elif data.plan == "bootcamp":
        if not data.bootcamp_id:
            raise HTTPException(400, "请选择训练营")
        camp = db.query("SELECT id, title, price, is_paid FROM rehab_camps WHERE id=%s", (data.bootcamp_id,), one=True)
        if not camp or not camp["is_paid"]:
            raise HTTPException(404, "训练营不存在或非付费营")
        amount = float(camp["price"])
        duration_days = 30
    else:
        raise HTTPException(400, "不支持的计划类型")

    order = payment.create_order(user["id"], data.plan, amount, duration_days,
                                 coach_id=data.coach_id, bootcamp_id=data.bootcamp_id)
    order["pay_url"] = f"/api/member/sandbox/pay"
    return {"ok": True, **order}


class NotifyIn(BaseModel):
    order_no: str
    amount: float
    timestamp: int
    sign: str


@router.post("/notify")
def pay_notify(data: NotifyIn):
    """沙箱支付回调：HMAC 验签 + 时间戳窗口 + 幂等入账。"""
    return payment.handle_notify(data.order_no, data.amount, data.timestamp, data.sign)


class SandboxPayIn(BaseModel):
    order_no: str


@router.post("/sandbox/pay")
def sandbox_pay(data: SandboxPayIn, user: dict = Depends(get_current_user)):
    """模拟网关发起回调（仅用于演示，不接真实渠道）。"""
    return payment.sandbox_pay(data.order_no, user["id"])


# ---------- 兼容旧前端的支付入口：内部仍走签名回调 ----------
@router.post("/pay-success/{order_no}")
def pay_success(order_no: str, user: dict = Depends(get_current_user)):
    return payment.sandbox_pay(order_no, user["id"])


# ---------- 教练：付费定制开关 ----------
class CoachPaidSwitch(BaseModel):
    accept_paid_plan: bool
    paid_plan_price: float = 49.0
    commission_rate: float = 15.0


@router.put("/coach-paid-setting")
def coach_paid_setting(data: CoachPaidSwitch, user: dict = Depends(get_current_user)):
    if user["role"] != "coach":
        raise HTTPException(403, "仅教练可以设置")
    if not data.accept_paid_plan:
        data.paid_plan_price = 0
    db.execute("""
        UPDATE therapist_profiles SET accept_paid_plan=%s, paid_plan_price=%s, commission_rate=%s
        WHERE user_id=%s
    """, (data.accept_paid_plan, max(0, data.paid_plan_price), max(5, min(50, data.commission_rate)), user["id"]))
    return {"ok": True}


# ---------- 支付成功回调（mock）----------
@router.post("/pay-success/{order_no}")
def pay_success(order_no: str, user: dict = Depends(get_current_user)):
    row = db.query("SELECT * FROM subscriptions WHERE order_no=%s AND user_id=%s",
                   (order_no, user["id"]), one=True)
    if not row:
        raise HTTPException(404, "订单不存在")
    if row["status"] == "paid":
        return {"ok": True, "note": "已支付"}
    db.execute("UPDATE subscriptions SET status='paid', paid_at=NOW() WHERE id=%s", (row["id"],))
    return {"ok": True, "expire_date": str(row["expire_date"])}


# ---------- 学员端：付费教练详情 ----------
@router.get("/paid-coaches")
def paid_coaches(q: str = None, user: dict = Depends(require_role("student"))):
    where = ["cp.review_status='approved'", "cp.accept_paid_plan=1"]
    params = []
    if q:
        where.append("(u.nickname LIKE %s OR cp.specialty LIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    rows = db.query(f"""
        SELECT u.id AS user_id, u.nickname, u.avatar, cp.paid_plan_price, cp.specialty, cp.bio,
               cp.commission_rate, cp.is_gold_cert,
               (SELECT COUNT(*) FROM rehab_programs tp WHERE tp.coach_id=u.id) AS plan_count
        FROM therapist_profiles cp JOIN users u ON u.id = cp.user_id
        WHERE {' AND '.join(where)}
        ORDER BY cp.is_gold_cert DESC, plan_count DESC
    """, tuple(params))
    return rows


# ---------- 权限检查依赖（可用于其他接口）----------
def require_member(user: dict = Depends(get_current_user)):
    """依赖项：需要会员才能访问的接口加上这个。"""
    if not user_is_member(user["id"]):
        raise HTTPException(403, "该功能为会员专属，请先前往会员中心开通")
    return user
