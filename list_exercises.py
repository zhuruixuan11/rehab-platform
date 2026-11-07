from app.database import db

rows = db.query("SELECT name, category, difficulty FROM rehab_exercises WHERE is_custom = 0 ORDER BY category, name")
for r in rows:
    print(r["category"], "|", r["name"], "| 难度", r["difficulty"])
print("总数:", len(rows))
