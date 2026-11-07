import sys

sys.path.insert(0, ".")
from app.database import db

rows = db.query(
    "SELECT name, category, muscles, breathing, anim FROM rehab_exercises ORDER BY id")
total = len(rows)
missing = [r["name"] for r in rows if not (r["anim"] or "").strip()
           or not (r["muscles"] or "").strip() or not (r["breathing"] or "").strip()]
print(f"total={total} complete={total - len(missing)}")
if missing:
    print("MISSING:", missing)
else:
    print("ALL COMPLETE")
    for r in rows:
        print(f"  {r['name']:<12} {r['anim']:<12} 肌群={r['muscles']}")
