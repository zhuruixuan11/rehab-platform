"""清理训练营测试数据，并创建一个进行中的演示营。"""
from datetime import date, timedelta

from app.database import db
from app.models.schemas import CampIn
from app.services import camp_service

db.execute("DELETE FROM rehab_programs WHERE camp_id IN (SELECT id FROM rehab_camps)")
db.execute("DELETE FROM rehab_camps")
db.execute("DELETE FROM users WHERE username = 'e2e_tmp_student'")

camp_id = camp_service.create_camp(
    2, CampIn(title="21天减脂训练营·第1期",
              description="线上私教带练演示营：按计划打卡、营内排行、群聊互动，结营自动生成报告。",
              start_date=date.today() - timedelta(days=5),
              end_date=date.today() + timedelta(days=16), capacity=30))
camp_service.transition_status(2, camp_id, "start")
camp_service.add_member(2, camp_id, 4)
camp_service.transition_status(2, camp_id, "open")
camp = camp_service.get_camp(camp_id)
print(f"演示营: id={camp_id} 状态={camp['status']} 邀请码={camp['invite_code']}")
print("当前营数:", db.query("SELECT COUNT(*) AS c FROM rehab_camps")[0]["c"])
