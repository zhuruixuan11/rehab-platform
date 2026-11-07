"""一次性迁移脚本（2026-08-25）：
1. 删除教学视频库相关表（videos / video_notes / video_history）
2. 创建社区动态表（community_posts / community_likes / community_comments）
3. exercises 表增加 intro/steps/tips 详解字段，删除 video_id
4. 回填 18 个内置动作的介绍与详解
5. 修正公告（移除视频库公告，补充社区公告）

用法：在项目根目录执行  python migrate_20260825.py
"""
from app.database import db

EXERCISE_DETAILS = {
    "杠铃卧推": (
        "平卧推举是练厚胸部的黄金动作，主练胸大肌整体，三角肌前束与肱三头肌协同发力。",
        "1. 仰卧凳上，双脚踩实地面，肩胛骨后缩下沉，握距约为肩宽1.5倍；\n2. 请同伴保护，将杠铃从架上限位取出，直臂悬于胸口正上方；\n3. 吸气憋气收紧核心，控制杠铃缓慢下放至胸口中线附近（乳头连线位置）；\n4. 杠铃轻触胸后，脚向下蹬地传导力量，爆发将杠铃沿略向后上的轨迹推起；\n5. 顶点肘部接近伸直但不锁死，完成一次，重复至目标次数。",
        "· 下放过程肘部约与躯干呈45-70度夹角，完全外展容易伤肩；\n· 杠铃触胸位置过高练肩、过低练前束，中线最稳；\n· 臀部不离开凳面，靠腰背自然拱起维持稳定；\n· 大重量务必请人保护，力竭时切勿直接放弃杠铃。"),
    "哑铃飞鸟": (
        "孤立拉伸胸大肌的单关节动作，给胸肌中缝带来强烈的拉伸与挤压感。",
        "1. 双手持哑铃仰卧，双臂伸直于胸口上方，掌心相对，肘部微屈固定；\n2. 保持肘部角度不变，沿弧线缓慢向两侧张开双臂；\n3. 感受胸肌被拉长，下降至大臂与地面平行或略低（以不痛为限）；\n4. 想象环抱一棵大树，用胸肌发力将哑铃沿原弧线合拢；\n5. 顶端挤压胸肌1秒，再进行下一次。",
        "· 全程肘部角度保持不变，变成\"卧推\"就失去孤立意义；\n· 重量宁轻勿重，飞鸟是感受型动作；\n· 底部出现肩关节弹响或疼痛应立即减小幅度。"),
    "上斜哑铃卧推": (
        "上斜30-45度推举，重点刺激胸大肌上部与三角肌前束，改善上胸薄弱。",
        "1. 调节凳面至30-45度（角度过大偏向三角肌）；\n2. 坐于凳上，哑铃置于大腿，借力将其翻至肩前；\n3. 后仰贴稳凳面，哑铃置于肩上方两侧，肘部朝斜下方；\n4. 控制下放至上胸位置，哑铃略低于肩水平线；\n5. 用上胸发力将哑铃推向斜上方，顶端不完全并拢，保持张力。",
        "· 椅背角度超过45度会变成推肩，注意调整；\n· 顶端哑铃不碰撞，避免借力与损坏器械；\n· 下放时肩胛骨始终贴紧凳面。"),
    "引体向上": (
        "自重练背之王，主练背阔肌与大圆肌，同时强化肱二头肌与核心稳定。",
        "1. 正握单杠，握距略宽于肩，身体自然悬垂，肩胛骨先激活下沉；\n2. 想象把杠\"拉向胸口\"，用肘部向下带动身体；\n3. 下巴过杠即算完成，顶端挤压背肌1秒；\n4. 缓慢下放至手臂接近伸直，保持背部张力不完全放松；\n5. 全程核心收紧，避免身体大幅度摆动借力。",
        "· 先沉肩再拉，耸肩会让斜方肌与手臂代偿；\n· 不要靠蹬腿摆体\"甩\"上去；\n· 做不满3个可用弹力带辅助或做离心（跳上慢放）训练。"),
    "杠铃划船": (
        "俯身划船打造背部厚度的核心动作，主练背阔肌、斜方肌中部与菱形肌。",
        "1. 双脚与髋同宽，屈膝俯身至上半身接近平行地面，背部挺直；\n2. 正握杠铃，握距略宽于肩，核心收紧；\n3. 用背肌力量将杠铃拉向下腹部（肚脐附近）；\n4. 顶端肘部越过背部，挤压肩胛骨1秒；\n5. 缓慢沿大腿前侧下放至手臂伸直，重复。",
        "· 俯身角度小于45度会变成耸肩借力；\n· 拉向胸口会过多使用三角肌后束；\n· 腰背有伤者改用坐姿划船或器械。"),
    "高位下拉": (
        "坐姿下拉是引体向上的最佳替代动作，安全可控地强化背阔肌宽度。",
        "1. 调整坐垫高度，大腿牢牢固定于海绵垫下；\n2. 正握横杆略宽于肩，身体后倾约15-20度，挺胸收腹；\n3. 想象肘部\"向下插口袋\"，肩胛骨下沉带动横杆下降；\n4. 将杆拉至锁骨/上胸位置，顶峰挤压背阔肌1秒；\n5. 控制横杆缓慢回放至手臂接近伸直，背部保持张力。",
        "· 用手臂\"拽\"杆是最常见错误，注意先沉肩、用背发力；\n· 身体过度后仰变成\"划船式\"借力；\n· 下放阶段要慢，离心阶段才是背肌增长关键。"),
    "硬拉": (
        "全身性力量之王，练后侧链（臀大肌、腘绳肌、竖脊肌）效率最高的复合动作。",
        "1. 杠铃置于脚掌正上方中部，双脚与髋同宽，脚尖微外展；\n2. 屈髋俯身握杠，握距略宽于双脚，背部挺直、肩胛骨收紧；\n3. 起拉前吸气憋气，全身绷紧，想象\"把地面推开\"；\n4. 杠铃贴腿直线上升，髋膝同步伸展，顶端站直即可不过度后仰；\n5. 屈髋控制杠铃沿大腿滑落回地面，完成一次。",
        "· 起始时杠铃离身体太远会让腰椎受力剧增；\n· 背部任何时刻不允许弓起，宁轻勿弯；\n· 顶端过度挺髋后仰会挤压腰椎；\n· 佩戴腰带、使用六角杠可降低腰部压力。"),
    "杠铃深蹲": (
        "下肢训练之王，全面发展股四头肌、臀大肌与核心力量。",
        "1. 杠铃置于斜方肌上（高杠位），双手扶稳，肘部下压；\n2. 双脚与肩同宽或略宽，脚尖自然外展30度左右；\n3. 吸气憋气收紧核心，屈髋屈膝同步下蹲，像坐椅子一样向后向下；\n4. 下蹲至大腿至少平行地面（髋低于膝），膝盖与脚尖方向一致；\n5. 全脚掌蹬地站起，顶端呼气，不锁死膝盖。",
        "· 重心始终落在脚掌中部，脚跟离地说明重心前移；\n· 膝盖内扣是膝盖损伤的头号风险；\n· 髋踝灵活性不足时可垫高脚跟或先练箱式深蹲。"),
    "腿举": (
        "坐姿腿举对腰背压力小，适合新手安全地积累腿部训练量。",
        "1. 调整座椅使膝盖弯曲时约90度，双脚与肩同宽踩稳踏板；\n2. 双脚位置偏高更侧重臀与腘绳肌，偏低侧重股四头肌；\n3. 解开保险销，屈膝让踏板缓慢下降，下放至膝盖约90度；\n4. 脚掌发力将踏板推起，接近伸直时不锁死膝盖；\n5. 全程腰部与臀部贴紧靠垫。",
        "· 顶端锁死膝盖在负重下非常危险；\n· 臀部离开靠垫说明下放过深或重量过大；\n· 双脚站位不同可微调刺激重点。"),
    "哑铃推肩": (
        "坐姿哑铃推举是打造三角肌围度的主力动作，比杠铃活动度更自由。",
        "1. 坐于靠背凳，双脚踩实，腰部贴紧靠垫；\n2. 双手持哑铃举至肩侧，掌心朝前，肘部位于身体两侧略前方；\n3. 呼气将哑铃垂直上推至头顶上方接近合拢；\n4. 顶端不碰撞哑铃、不锁死肘部；\n5. 缓慢下放至大臂约平行地面或略低，重复。",
        "· 下放过低（哑铃低于肩）会给肩关节带来压力；\n· 腰部反弓过大说明重量超标；\n· 想练三角肌整体围度，坐姿比站姿更稳。"),
    "杠铃推举": (
        "站姿杠铃推举（军用推举）是发展肩部力量与全身稳定的经典动作。",
        "1. 双脚与髋同宽，杠铃置于锁骨前，双肘位于杠铃正下方；\n2. 全身绷紧，臀部与核心收紧，想象双脚钉进地面；\n3. 呼气将杠铃垂直向上推起，头部微微后移让杠铃贴面前通过；\n4. 顶端杠铃落于头顶正上方、耳朵侧后方，肘部伸直不锁死；\n5. 控制下放回锁骨位置，保持躯干稳定。",
        "· 腰部过度反弓（挺肚子）说明核心没收紧或重量太大；\n· 杠铃绕头走弧线会增大肩部压力；\n· 站姿推举对核心要求高，可先从坐姿开始。"),
    "哑铃弯举": (
        "最经典的肱二头肌孤立动作，可交替或同时进行。",
        "1. 双脚与肩同宽站立，双手持哑铃自然下垂于体侧，掌心朝前；\n2. 上臂贴近躯干并保持固定，肘部是唯一活动的关节；\n3. 呼气弯举哑铃至肩前，顶端挤压肱二头肌1秒；\n4. 缓慢下放至手臂接近伸直但不完全放松；\n5. 可在顶端外旋手腕进一步强化收缩感。",
        "· 身体后仰甩动哑铃是最常见借力，宁可减轻重量；\n· 肘部前移会让三角肌前束代偿；\n· 控制离心（3秒下放）对增肌效果显著。"),
    "绳索下压": (
        "龙门架绳索下压是孤立训练肱三头肌的最佳动作之一，持续保持张力。",
        "1. 将绳索或直杆固定于高位，正握把手，肘部贴近躯干固定；\n2. 上臂保持不动，呼气用肱三头肌将把手下压；\n3. 顶端手臂完全伸直，停顿1秒并做顶峰收缩；\n4. 缓慢回放至前臂约平行地面，肘部角度不完全放开；\n5. 使用绳索时顶端可向外旋开，强化收缩。",
        "· 肘部外飘或前后移动会让胸背代偿；\n· 身体过度前倾压重量是借力表现；\n· 想让手臂变粗，肱三头肌占上臂围度约2/3，不可只练弯举。"),
    "平板支撑": (
        "静态等长收缩训练，强化腹横肌与深层核心，提升全身稳定性。",
        "1. 俯卧，双肘撑地位于肩部正下方，双脚并拢或略分开；\n2. 头、背、臀、脚跟保持一条直线，视线朝下；\n3. 收紧腹部与臀部，想象肚脐拉向脊柱；\n4. 保持自然呼吸不憋气，坚持目标时间；\n5. 塌腰或撅臀立即停止，质量重于时长。",
        "· 塌腰是腰椎代偿，宁可时间短也要保持直线；\n· 肩胛骨保持平整，不耸肩缩脖子；\n· 能稳定坚持2分钟以上可升级为动态变式。"),
    "卷腹": (
        "上固定式腹肌训练，主练腹直肌上部，比传统仰卧起坐更安全。",
        "1. 仰卧屈膝约90度，双脚平放，双手轻扶耳侧或交叉于胸前；\n2. 下背部贴紧地面，呼气用腹肌力量将肩胛骨抬离地面；\n3. 顶端挤压腹肌1-2秒，腰部始终不离开地面；\n4. 缓慢下放肩胛骨轻触地面即再次卷起；\n5. 动作幅度小而慢，感受腹肌全程发力。",
        "· 双手抱头用力拉扯颈部是常见错误，只轻扶即可；\n· 不要用惯性\"弹\"起来；\n· 想练下腹改做反向卷腹（抬腿卷盆骨）。"),
    "跑步机慢跑": (
        "最普及的有氧训练方式，提升心肺功能、燃烧热量，配速可控易坚持。",
        "1. 先以4-5km/h快走1-2分钟热身，再逐步提升速度；\n2. 跑姿：身体微前倾、落地于脚掌中部、步幅不宜过大；\n3. 保持匀速慢跑（能边跑边说话的强度），新手从20分钟开始；\n4. 结束前逐步降速至快走3-5分钟冷身；\n5. 每周跑量增幅不超过10%，给关节适应时间。",
        "· 抓扶手跑会大幅降低训练效果；\n· 步幅过大、脚跟重击容易伤膝；\n· 体重基数大者优先选择快走/椭圆机减轻关节冲击。"),
    "动感单车": (
        "低冲击高燃脂的室内有氧，跟随课程节奏骑行，对膝盖压力小。",
        "1. 调节坐垫高度：踩到最低点时膝盖微屈约25-30度；\n2. 车把高度与坐垫齐平或略高，避免过度弯腰；\n3. 前脚掌踩踏板，用画圆的轨迹发力；\n4. 阻力随课程节奏调整，保持踏频80-110rpm；\n5. 结束后慢骑2-3分钟冷身，再进行下肢拉伸。",
        "· 阻力为0时空踩伤膝，保持适当阻力；\n· 肩颈放松，不要耸肩撑车把；\n· 骑行前后注意补水。"),
    "椭圆机": (
        "关节友好的全身性有氧器械，手脚并用，适合大体重与膝盖不适人群。",
        "1. 双脚全掌踩稳踏板，双手轻握活动扶手；\n2. 身体直立微前倾，核心收紧，不塌腰驼背；\n3. 平滑地推拉扶手并蹬踏踏板，保持连贯节奏；\n4. 阻力与坡度调节至微微出汗但仍可匀速运动的强度；\n5. 持续20-45分钟，结束前逐步降低阻力冷身。",
        "· 脚跟抬起或踮脚会加剧小腿疲劳；\n· 全身重量压在扶手上会降低消耗；\n· 想增阻力优先加坡度而非一味加快频率。"),
}


def has_table(name: str) -> bool:
    return any(list(r.values())[0] == name for r in db.query("SHOW TABLES"))


def has_column(table: str, col: str) -> bool:
    return any(c["Field"] == col for c in db.query(f"SHOW COLUMNS FROM {table}"))


def migrate():
    # 1. 删除视频库相关表
    for t in ("video_history", "video_notes", "videos"):
        if has_table(t):
            db.execute(f"DROP TABLE IF EXISTS {t}")
            print(f"[OK] 已删除表 {t}")

    # 2. 创建社区表
    if not has_table("community_posts"):
        db.execute("""
            CREATE TABLE community_posts (
              id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              user_id     BIGINT UNSIGNED NOT NULL,
              content     VARCHAR(2000) NOT NULL,
              media_paths VARCHAR(1000) DEFAULT '' COMMENT '逗号分隔图片路径',
              visibility  ENUM('public','coach','private') DEFAULT 'public' COMMENT '公开/仅教练可见/仅自己可见',
              created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
              INDEX idx_posts_feed (created_at),
              INDEX idx_posts_user (user_id),
              CONSTRAINT fk_post_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("[OK] 已创建表 community_posts")
    if not has_table("community_likes"):
        db.execute("""
            CREATE TABLE community_likes (
              id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              post_id     BIGINT UNSIGNED NOT NULL,
              user_id     BIGINT UNSIGNED NOT NULL,
              created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
              UNIQUE KEY uq_post_like (post_id, user_id),
              CONSTRAINT fk_like_post FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
              CONSTRAINT fk_like_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("[OK] 已创建表 community_likes")
    if not has_table("community_comments"):
        db.execute("""
            CREATE TABLE community_comments (
              id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
              post_id     BIGINT UNSIGNED NOT NULL,
              user_id     BIGINT UNSIGNED NOT NULL,
              content     VARCHAR(1000) NOT NULL,
              created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
              INDEX idx_cmt_post (post_id),
              CONSTRAINT fk_cmt_post FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
              CONSTRAINT fk_cmt_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        print("[OK] 已创建表 community_comments")

    # 3. exercises 表结构调整
    if not has_column("exercises", "intro"):
        db.execute("ALTER TABLE rehab_exercises ADD COLUMN intro VARCHAR(500) DEFAULT '' COMMENT '一句话介绍' AFTER difficulty")
        print("[OK] exercises 增加 intro 列")
    if not has_column("exercises", "steps"):
        db.execute("ALTER TABLE rehab_exercises ADD COLUMN steps TEXT COMMENT '动作步骤详解' AFTER intro")
        print("[OK] exercises 增加 steps 列")
    if not has_column("exercises", "tips"):
        db.execute("ALTER TABLE rehab_exercises ADD COLUMN tips TEXT COMMENT '训练要点与常见错误' AFTER steps")
        print("[OK] exercises 增加 tips 列")
    if has_column("exercises", "video_id"):
        db.execute("ALTER TABLE rehab_exercises DROP COLUMN video_id")
        print("[OK] exercises 删除 video_id 列")

    # 4. 回填动作详解
    updated = 0
    for name, (intro, steps, tips) in EXERCISE_DETAILS.items():
        db.execute(
            "UPDATE rehab_exercises SET intro=%s, steps=%s, tips=%s WHERE name=%s AND is_custom=0",
            (intro, steps, tips, name))
        updated += 1
    print(f"[OK] 已回填 {updated} 个动作的详解数据")

    # 5. 公告修正
    db.execute("DELETE FROM announcements WHERE title LIKE %s", ("%视频%",))
    db.execute(
        "INSERT INTO announcements (title, content, is_pinned, status, target_role, created_by) "
        "SELECT '社区动态已上线', '训练心得、进步瞬间都可以发布到社区，还可以自行设置动态的可见范围。', "
        "0, 'published', 'all', NULL FROM DUAL "
        "WHERE NOT EXISTS (SELECT 1 FROM (SELECT 1 FROM announcements WHERE title='社区动态已上线') x)")
    print("[OK] 公告已更新")

    print("\n迁移完成。")


if __name__ == "__main__":
    migrate()
