from app.database import db

rows = db.query("SELECT id, name, category, is_custom, anim, breathing, muscles IS NULL AS no_muscle FROM rehab_exercises ORDER BY id")
for r in rows:
    print(f"id={r['id']:<3} {r['name']:<12} cat={r['category']:<5} custom={r['is_custom']} anim={r['anim'] or '-':<10} no_muscle={r['no_muscle']}")
print("total:", len(rows))
