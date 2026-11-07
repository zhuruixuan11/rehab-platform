"""一次性迁移脚本（2026-08-28）：
动作库可视化系统：exercises 表新增 muscles（发力肌群 JSON）、breathing（呼吸节奏）、
anim（动作演示动画模式）三个字段，并为全部内置动作填充数据。

用法：在项目根目录执行  python migrate_20260828.py
"""
import json

from app.database import db

MUSCLE_LABELS = {
    "chest": "胸大肌", "lats": "背阔肌", "traps": "斜方肌", "delts": "三角肌",
    "delt_ant": "三角肌前束", "delt_post": "三角肌后束", "biceps": "肱二头肌",
    "triceps": "肱三头肌", "forearm": "前臂肌群", "abs": "腹直肌", "obliques": "腹斜肌",
    "lowerback": "竖脊肌", "glutes": "臀大肌", "quads": "股四头肌", "hams": "腘绳肌",
    "calves": "小腿三头肌",
}

# anim 模式：squat深蹲 deadlift硬拉 bench卧推 fly飞鸟 ohp推举 pulldown下拉
# row划船 legpress腿举 curl弯举 pushdown下压 plank平板 crunch卷腹
# run跑步 bike骑行 elliptical椭圆机
UPDATES = [
    ("杠铃卧推", "bench", "下放时吸气2-3秒，触胸后呼气爆发推起，顶端换气",
     ["chest"], ["delt_ant", "triceps"]),
    ("哑铃飞鸟", "fly", "张开双臂时吸气，合拢挤压时呼气",
     ["chest"], ["delt_ant"]),
    ("上斜哑铃卧推", "bench", "下放吸气，上推呼气，顶端不憋气",
     ["chest"], ["delt_ant", "triceps"]),
    ("引体向上", "pulldown", "上拉呼气，下放吸气，顶端挤压时短屏息",
     ["lats"], ["biceps", "traps", "forearm"]),
    ("杠铃划船", "row", "拉起呼气挤压1秒，下放吸气",
     ["lats"], ["traps", "biceps", "lowerback"]),
    ("高位下拉", "pulldown", "下拉呼气，回放吸气（离心放慢2-3秒）",
     ["lats"], ["biceps", "delt_post"]),
    ("硬拉", "deadlift", "起拉前吸气憋气全身绷紧，顶端站直呼气，下放吸气",
     ["glutes", "hams", "lowerback"], ["quads", "traps", "forearm"]),
    ("杠铃深蹲", "squat", "下蹲吸气憋气收紧核心，蹬起呼气，顶端换气",
     ["quads", "glutes"], ["hams", "lowerback", "abs"]),
    ("腿举", "legpress", "下放踏板吸气，蹬起呼气，不锁膝",
     ["quads"], ["glutes", "hams"]),
    ("哑铃推肩", "ohp", "上推呼气，下放吸气",
     ["delts"], ["triceps", "traps"]),
    ("杠铃推举", "ohp", "上推呼气，下放回锁骨位置吸气",
     ["delts"], ["triceps", "abs"]),
    ("哑铃弯举", "curl", "弯举呼气挤压1秒，下放吸气3秒",
     ["biceps"], ["forearm"]),
    ("绳索下压", "pushdown", "下压呼气顶峰收缩，回放吸气",
     ["triceps"], ["forearm"]),
    ("平板支撑", "plank", "全程保持自然呼吸不憋气，鼻吸口呼",
     ["abs"], ["obliques", "delts", "quads"]),
    ("卷腹", "crunch", "卷起呼气挤压腹肌，下放吸气",
     ["abs"], ["obliques"]),
    ("跑步机慢跑", "run", "保持有节奏的口鼻协同呼吸：两步一吸两步一呼",
     ["quads", "calves"], ["hams", "glutes", "abs"]),
    ("动感单车", "bike", "匀速深呼吸配合踏频，冲刺时加深呼吸",
     ["quads"], ["glutes", "hams", "calves"]),
    ("椭圆机", "elliptical", "全程匀速深呼吸，保持心率区间",
     ["quads", "glutes"], ["delts", "hams", "calves"]),
    # ---- 数据库历史动作（init.sql 之外的 15 个）----
    ("双杠臂屈伸", "dips", "下降吸气2秒，撑起呼气，顶端挤压不锁肘",
     ["chest", "triceps"], ["delts"]),
    ("蝴蝶机夹胸", "fly", "夹拢呼气挤压胸肌1秒，张开吸气感受拉伸",
     ["chest"], ["delts"]),
    ("坐姿划船", "row", "拉起呼气挤压肩胛1秒，缓慢回放吸气",
     ["lats"], ["traps", "biceps"]),
    ("直臂下压", "pushdown", "下压呼气，回放吸气，肘部微屈固定",
     ["lats"], ["abs", "triceps"]),
    ("罗马尼亚硬拉", "deadlift", "俯身吸气拉伸腘绳肌，站直呼气挤压臀部",
     ["hams", "glutes"], ["lowerback"]),
    ("保加利亚分腿蹲", "squat", "下蹲吸气2-3秒，蹬地站起呼气",
     ["quads", "glutes"], ["hams"]),
    ("俯卧腿弯举", "legcurl", "弯起呼气顶峰收缩，下放吸气3秒",
     ["hams"], ["calves"]),
    ("站姿提踵", "calfraise", "踮起呼气顶端停顿1秒，下落吸气",
     ["calves"], []),
    ("哑铃侧平举", "lateral", "举起呼气，下放吸气控制3秒",
     ["delts"], ["traps"]),
    ("面拉", "row", "拉近面部呼气外旋，回放吸气",
     ["delt_post"], ["traps", "biceps"]),
    ("锤式弯举", "curl", "弯举呼气挤压1秒，离心下放3秒",
     ["biceps"], ["forearm"]),
    ("仰卧臂屈伸", "skullcrusher", "屈肘下放吸气，伸直呼气（肘部固定）",
     ["triceps"], []),
    ("悬垂举腿", "legraise", "抬腿呼气卷动骨盆，下落吸气控制",
     ["abs"], ["obliques", "forearm"]),
    ("俄罗斯转体", "twist", "左右匀速转体，保持自然呼吸不憋气",
     ["obliques"], ["abs"]),
    ("跳绳", "jump", "保持匀速浅快呼吸，前脚掌弹性落地",
     ["calves"], ["quads", "abs"]),
]


def migrate():
    cols = db.query("SHOW COLUMNS FROM rehab_exercises")
    names = {c["Field"] for c in cols}
    if "muscles" not in names:
        db.execute("ALTER TABLE rehab_exercises ADD COLUMN muscles JSON DEFAULT NULL "
                   "COMMENT '发力肌群 {primary:[],secondary:[]}'")
        print("[OK] exercises.muscles 已添加")
    if "breathing" not in names:
        db.execute("ALTER TABLE rehab_exercises ADD COLUMN breathing VARCHAR(200) DEFAULT '' "
                   "COMMENT '呼吸节奏'")
        print("[OK] exercises.breathing 已添加")
    if "anim" not in names:
        db.execute("ALTER TABLE rehab_exercises ADD COLUMN anim VARCHAR(30) DEFAULT '' "
                   "COMMENT '动作演示动画模式'")
        print("[OK] exercises.anim 已添加")

    updated = 0
    for name, anim, breathing, primary, secondary in UPDATES:
        muscles = json.dumps({
            "primary": [{"key": k, "label": MUSCLE_LABELS[k]} for k in primary],
            "secondary": [{"key": k, "label": MUSCLE_LABELS[k]} for k in secondary],
        }, ensure_ascii=False)
        affected = db.execute(
            "UPDATE rehab_exercises SET muscles = %s, breathing = %s, anim = %s WHERE name = %s",
            (muscles, breathing, anim, name))
        updated += affected
    print(f"[OK] 已为 {updated} 个动作填充肌群/呼吸/动画数据")


if __name__ == "__main__":
    migrate()
