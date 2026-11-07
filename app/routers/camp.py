from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user, require_role
from app.models.schemas import CampIn, CampJoinIn, CampMemberIn, CampPlanGenIn, CampUrgeIn
from app.services import camp_service, message_service

router = APIRouter(prefix="/api/camps", tags=["训练营"])


def _get_camp_or_404(camp_id: int) -> dict:
    camp = camp_service.get_camp(camp_id)
    if not camp:
        raise HTTPException(status_code=404, detail="营期不存在")
    return camp


def _require_camp_access(camp_id: int, user: dict) -> dict:
    """营详情可见：在营成员 / 营教练 / 管理员。"""
    camp = _get_camp_or_404(camp_id)
    if user["role"] == "admin" or camp["coach_id"] == user["id"]:
        return camp
    if camp_service.is_member(camp_id, user["id"]):
        return camp
    raise HTTPException(status_code=403, detail="你不是该训练营成员")


def _require_camp_owner(camp_id: int, user: dict) -> dict:
    camp = _get_camp_or_404(camp_id)
    if camp["coach_id"] != user["id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="只有营期教练可以操作")
    return camp


# ---------------- 学员端（静态路径需先于 /{camp_id} 声明） ----------------
@router.get("/my")
def my_camps(user: dict = Depends(get_current_user)):
    return camp_service.my_camps(user["id"])


@router.post("/join")
def join_camp(data: CampJoinIn, user: dict = Depends(require_role("student"))):
    camp, err = camp_service.join_by_code(user["id"], data.invite_code)
    if not camp:
        raise HTTPException(status_code=400, detail=err)
    return camp


@router.get("/{camp_id}")
def camp_detail(camp_id: int, user: dict = Depends(get_current_user)):
    camp = _require_camp_access(camp_id, user)
    return camp_service.camp_detail(camp_id)


@router.get("/{camp_id}/leaderboard")
def camp_leaderboard(camp_id: int, metric: str = "days",
                     user: dict = Depends(get_current_user)):
    _require_camp_access(camp_id, user)
    if metric not in ("days", "volume"):
        raise HTTPException(status_code=400, detail="metric 仅支持 days/volume")
    return camp_service.camp_leaderboard(camp_id, metric)


@router.get("/{camp_id}/members")
def camp_members(camp_id: int, user: dict = Depends(get_current_user)):
    _require_camp_access(camp_id, user)
    return camp_service.camp_members_detail(camp_id)


@router.get("/{camp_id}/messages")
def camp_messages(camp_id: int, limit: int = 100, user: dict = Depends(get_current_user)):
    _require_camp_access(camp_id, user)
    return camp_service.camp_chat_history(camp_id, limit)


@router.get("/{camp_id}/report")
def camp_report(camp_id: int, user: dict = Depends(get_current_user)):
    camp = _require_camp_access(camp_id, user)
    if camp["status"] != "ended":
        raise HTTPException(status_code=400, detail="营期尚未结营")
    report = camp_service.get_camp_report(camp_id)
    if not report:
        raise HTTPException(status_code=404, detail="结营报告尚未生成")
    return report


# ---------------- 教练端 ----------------
@router.get("")
def coach_camps(user: dict = Depends(require_role("coach"))):
    return camp_service.coach_camps(user["id"])


@router.post("", status_code=201)
def create_camp(data: CampIn, user: dict = Depends(require_role("coach"))):
    try:
        camp_id = camp_service.create_camp(user["id"], data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": camp_id}


@router.put("/{camp_id}")
def update_camp(camp_id: int, data: CampIn, user: dict = Depends(require_role("coach"))):
    ok, err = camp_service.update_camp(user["id"], camp_id, data)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


@router.post("/{camp_id}/transition")
def transition_camp(camp_id: int, action: str, user: dict = Depends(require_role("coach"))):
    """action: start=发布招生 / open=开营 / finish=结营（结营自动生成报告）。"""
    if action not in ("start", "open", "finish"):
        raise HTTPException(status_code=400, detail="action 仅支持 start/open/finish")
    ok, err = camp_service.transition_status(user["id"], camp_id, action)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


@router.post("/{camp_id}/members")
def add_camp_member(camp_id: int, data: CampMemberIn,
                    user: dict = Depends(require_role("coach"))):
    ok, err = camp_service.add_member(user["id"], camp_id, data.user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


@router.delete("/{camp_id}/members/{member_id}")
def remove_camp_member(camp_id: int, member_id: int,
                       user: dict = Depends(require_role("coach"))):
    ok, err = camp_service.remove_member(user["id"], camp_id, member_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"ok": True}


@router.post("/{camp_id}/generate-plans")
def generate_plans(camp_id: int, data: CampPlanGenIn,
                   user: dict = Depends(require_role("coach"))):
    created, err = camp_service.generate_camp_plans(user["id"], camp_id,
                                                    data.template_plan_id, data.title)
    if not created:
        raise HTTPException(status_code=400, detail=err)
    return {"created": created}


@router.get("/{camp_id}/dashboard")
def camp_dashboard(camp_id: int, user: dict = Depends(require_role("coach"))):
    camp = _require_camp_owner(camp_id, user)
    from datetime import date as _date
    detail = camp_service.camp_detail(camp_id)
    members = camp_service.camp_members_detail(camp_id)
    trend = camp_service.camp_checkin_trend(camp_id)
    today = _date.today()
    days_elapsed = max(1, (min(camp["end_date"], today) - camp["start_date"]).days + 1)
    low_active = [{"id": m["id"], "nickname": m["nickname"],
                   "rate": round(m["camp_days"] * 100 / days_elapsed, 1)}
                  for m in members if m["camp_days"] * 100 / days_elapsed < 50]
    detail.update({
        "trend": trend,
        "unchecked_today": [m["id"] for m in members if not m["checked_today"]],
        "low_active": low_active,
        "member_stats": members,
        "active_member_count": len(members),
        "days_elapsed": days_elapsed,
    })
    return detail


@router.post("/{camp_id}/urge")
def urge_camp(camp_id: int, data: CampUrgeIn, user: dict = Depends(require_role("coach"))):
    """对营内今日未打卡学员批量催打卡。"""
    _require_camp_owner(camp_id, user)
    members = camp_service.camp_members_detail(camp_id)
    sent = 0
    for m in members:
        if not m["checked_today"]:
            message_service.send_message(user["id"], m["id"], "text",
                                         f"【{data.message}】")
            sent += 1
    return {"sent": sent}
