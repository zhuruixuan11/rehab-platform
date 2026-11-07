from datetime import timedelta

from app.database import db
from app.models.schemas import PlanIn


def create_plan(coach_id: int, data: PlanIn) -> int:
    if data.end_date < data.start_date:
        raise ValueError("结束日期不能早于开始日期")
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO rehab_programs (coach_id, student_id, title, description, start_date, end_date) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (coach_id, data.student_id, data.title, data.description,
             data.start_date, data.end_date),
        )
        plan_id = cursor.lastrowid
        if data.items:
            cursor.executemany(
                "INSERT INTO program_items (plan_id, day_date, exercise_name, sets, reps, "
                "weight_suggest, rest_sec, note, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(plan_id, i.day_date, i.exercise_name, i.sets, i.reps,
                  i.weight_suggest, i.rest_sec, i.note, i.sort_order) for i in data.items],
            )
    return plan_id


def update_plan(coach_id: int, plan_id: int, data: PlanIn) -> tuple[bool, str]:
    plan = db.query("SELECT id FROM rehab_programs WHERE id = %s AND coach_id = %s",
                    (plan_id, coach_id), one=True)
    if not plan:
        return False, "计划不存在或无权修改"
    if data.end_date < data.start_date:
        return False, "结束日期不能早于开始日期"
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE rehab_programs SET student_id=%s, title=%s, description=%s, start_date=%s, "
            "end_date=%s, status='active' WHERE id=%s",
            (data.student_id, data.title, data.description, data.start_date,
             data.end_date, plan_id),
        )
        cursor.execute("DELETE FROM program_items WHERE plan_id = %s", (plan_id,))
        if data.items:
            cursor.executemany(
                "INSERT INTO program_items (plan_id, day_date, exercise_name, sets, reps, "
                "weight_suggest, rest_sec, note, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(plan_id, i.day_date, i.exercise_name, i.sets, i.reps,
                  i.weight_suggest, i.rest_sec, i.note, i.sort_order) for i in data.items],
            )
    return True, ""


def delete_plan(coach_id: int, plan_id: int) -> tuple[bool, str]:
    row = db.query("SELECT id FROM rehab_programs WHERE id = %s AND coach_id = %s",
                   (plan_id, coach_id), one=True)
    if not row:
        return False, "计划不存在或无权删除"
    db.execute("DELETE FROM rehab_programs WHERE id = %s", (plan_id,))
    return True, ""


def copy_plan(coach_id: int, plan_id: int, new_start, new_end=None) -> tuple[int | None, str]:
    plan = db.query("SELECT * FROM rehab_programs WHERE id = %s AND coach_id = %s",
                    (plan_id, coach_id), one=True)
    if not plan:
        return None, "计划不存在或无权复制"
    days = (plan["end_date"] - plan["start_date"]).days
    new_end = new_end or (new_start + timedelta(days=days))
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO rehab_programs (coach_id, student_id, title, description, start_date, end_date) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (coach_id, plan["student_id"], plan["title"] + " (副本)", plan["description"],
             new_start, new_end),
        )
        new_plan_id = cursor.lastrowid
        items = db.query("SELECT * FROM program_items WHERE plan_id = %s ORDER BY day_date, sort_order",
                         (plan_id,))
        offset = (new_start - plan["start_date"]).days
        if items:
            cursor.executemany(
                "INSERT INTO program_items (plan_id, day_date, exercise_name, sets, reps, "
                "weight_suggest, rest_sec, note, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(new_plan_id, timedelta(days=offset) + i["day_date"],
                  i["exercise_name"], i["sets"], i["reps"], i["weight_suggest"],
                  i["rest_sec"], i["note"], i["sort_order"]) for i in items],
            )
    return new_plan_id, ""


def serialize_plan(plan: dict, with_items: bool = True) -> dict:
    data = {**plan,
            "start_date": plan["start_date"].isoformat(),
            "end_date": plan["end_date"].isoformat(),
            "created_at": str(plan["created_at"])}
    if with_items:
        items = db.query(
            "SELECT * FROM program_items WHERE plan_id = %s ORDER BY day_date, sort_order, id",
            (plan["id"],))
        data["items"] = [{**i, "day_date": i["day_date"].isoformat()} for i in items]
    return data


def get_student_plans(student_id: int, only_active: bool = True) -> list:
    sql = ("SELECT p.*, c.nickname AS coach_name, c.avatar AS coach_avatar "
           "FROM rehab_programs p JOIN users c ON c.id = p.coach_id "
           "WHERE p.student_id = %s")
    params = [student_id]
    if only_active:
        sql += " AND p.status = 'active'"
    sql += " ORDER BY p.start_date DESC"
    plans = db.query(sql, tuple(params))
    return [serialize_plan(p) for p in plans]


def get_coach_plans(coach_id: int, student_id: int | None = None) -> list:
    sql = ("SELECT p.*, u.nickname AS student_name FROM rehab_programs p "
           "JOIN users u ON u.id = p.student_id WHERE p.coach_id = %s")
    params = [coach_id]
    if student_id:
        sql += " AND p.student_id = %s"
        params.append(student_id)
    sql += " ORDER BY p.created_at DESC"
    plans = db.query(sql, tuple(params))
    return [serialize_plan(p) for p in plans]


def get_plan_detail(plan_id: int) -> dict | None:
    plan = db.query(
        "SELECT p.*, s.nickname AS student_name, c.nickname AS coach_name "
        "FROM rehab_programs p JOIN users s ON s.id = p.student_id "
        "JOIN users c ON c.id = p.coach_id WHERE p.id = %s",
        (plan_id,), one=True)
    if not plan:
        return None
    return serialize_plan(plan)


def recommended_plans(limit: int = 10) -> list:
    plans = db.query(
        "SELECT p.*, s.nickname AS student_name, c.nickname AS coach_name "
        "FROM rehab_programs p JOIN users s ON s.id = p.student_id "
        "JOIN users c ON c.id = p.coach_id "
        "WHERE p.is_recommended = 1 AND p.status = 'active' "
        "ORDER BY p.recommend_weight DESC, p.created_at DESC LIMIT %s",
        (limit,))
    return [serialize_plan(p, with_items=False) for p in plans]


def coach_student_ids(coach_id: int) -> list:
    rows = db.query("SELECT DISTINCT student_id FROM rehab_programs WHERE coach_id = %s",
                    (coach_id,))
    return [r["student_id"] for r in rows]
