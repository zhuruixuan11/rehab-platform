# 康衡康复中心 · 全周期康复管理平台

面向运动康复场景的一体化管理系统：**康复评估 → 个体化方案 → 康复训练日志 → 复评追踪**。

> 本项目由健身打卡系统深度改造而来，领域模型、角色文案、数据表均已康复化。

---

## 一、功能一览

### 患者端
| 模块 | 说明 |
| --- | --- |
| 康复日志 | 每日康复训练记录，练前/练后 VAS 疼痛评分与减量提示，上传图片/视频，组数次数重量、RPE、心率 |
| 我的康复档案 | 查看自己的病症档案、康复阶段、主诉、目标 |
| 康复评估 | 疼痛 VAS、平衡、步态、日常生活能力趋势图，关节活动度与肌力历史，按评估自动推荐动作 |
| 中医体质 | 九种体质自评 → 体质化康复建议 |
| 康复方案 | 治疗师制定的分阶段方案与动作清单 |
| 康复营 | 康复营参与、营内群聊、日志排行 |
| 康复动作库 | 89 个动作，按肩部 / 肘腕 / 颈腰椎 / 胸背 / 核心躯干 / 髋部 / 膝部 / 踝足 / 平衡步态 / 心肺全身分类，含动作讲解、安全要点、3D 图解 |
| 康复指标 | 体重、体脂、围度等身体指标记录与趋势 |
| 康复里程碑 | 连续训练里程碑与徽章 |
| 会员中心 | 会员订阅（Mock 支付）、体验券、邀请裂变 |
| 社区 / 消息 | 康复动态、评论点赞、私信 |

### 康复治疗师端
| 模块 | 说明 |
| --- | --- |
| 患者管理 | 患者名册、训练情况、补录审核 |
| 康复档案 | 新建/编辑康复档案（病症、类型、患侧、阶段、目标） |
| 康复评估 | 录入评估（VAS、ROM、MMT、平衡/步态/姿势/ADL），查看趋势，按评估智能推荐动作 |
| 方案制定 | 为患者编排康复方案与动作，支持「按评估推荐」一键带入 |
| 康复营 / 线上指导 / 社区 / 消息 | 督学与沟通 |
| 我的收益 | 付费定制分成（默认抽佣 15%）、可提现余额、提现申请 |

### 管理员端
统计看板、营收看板（总营收/本月/今日/趋势/会员）、用户管理、治疗师审核、
提现审核、公告管理、方案推荐、系统配置、操作日志。

---

## 二、技术栈

- 后端：FastAPI + PyMySQL（同步 MySQL）+ JWT
- 前端：原生 ES Module SPA（无框架）+ Chart.js / ECharts（已本地化）
- 数据库：MySQL 8，库名 `rehab_tracker`
- 推送：SMTP 邮件（未配置时优雅降级）

---

## 三、快速开始

```bash
# 1. 建库（首次）
mysql -u root -p < sql/init.sql

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 .env
#    DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME=rehab_tracker
#    JWT_SECRET / PORT=8003

# 4. 演示数据（可选）
python seed.py

# 5. 启动
python -m uvicorn app.main:app --host 127.0.0.1 --port 8003
```

打开 http://127.0.0.1:8003

### 测试账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `Admin@123` |
| 康复治疗师 | `coach_li` | `Coach@123` |
| 患者 | `student_wx` | `Student@123` |
| 患者 | `student_zy` | `Student@123` |

> 注：角色内部标识仍为 `student` / `coach` / `admin`（兼容既有接口），
> 界面统一显示为「患者 / 康复治疗师 / 管理员」。

---

## 四、康复化数据模型

核心表由原健身模型重命名而来（字段保持不变，平滑迁移）：

| 原表 | 康复表 | 含义 |
| --- | --- | --- |
| `checkins` | `rehab_logs` | 康复训练日志 |
| `checkin_media` | `rehab_log_media` | 日志图片/视频 |
| `checkin_details` | `rehab_log_details` | 动作组数次数 |
| `checkin_comments` | `rehab_log_comments` | 日志评论 |
| `training_plans` | `rehab_programs` | 康复方案 |
| `plan_items` | `program_items` | 方案动作 |
| `exercises` | `rehab_exercises` | 康复动作库 |
| `camps` | `rehab_camps` | 康复营 |
| `camp_members` | `rehab_camp_members` | 营成员 |
| `camp_messages` | `rehab_camp_messages` | 营内消息 |
| `achievements` | `milestones` | 康复里程碑 |
| `coach_profiles` | `therapist_profiles` | 治疗师档案 |

新增康复专业表：

| 表 | 说明 |
| --- | --- |
| `rehab_cases` | 康复档案：病症、类型、患侧、阶段、主诉、诊断、目标 |
| `rehab_assessments` | 康复评估：VAS、ROM、MMT、平衡、步态、姿势、ADL |
| `tcm_constitutions` | 中医体质辨识：主体质、九维得分、调理建议 |

---

## 五、主要接口

```
GET  /api/rehab/cases                       康复档案列表（按角色过滤）
POST /api/rehab/cases                       新建康复档案（治疗师/管理员）
PUT  /api/rehab/cases/{id}                  更新康复档案
GET  /api/rehab/patients                    治疗师患者名册
GET  /api/rehab/assessments?patient_id&case_id   评估记录
POST /api/rehab/assessments                 录入评估（治疗师/管理员）
GET  /api/rehab/assessments/trend?patient_id&case_id  评估趋势
GET  /api/rehab/exercise-recommendations?patient_id&case_id  按评估推荐动作（部位/VAS/阶段规则）
GET  /api/rehab/tcm/latest                  最近体质辨识结果
POST /api/rehab/tcm/assess                  提交九维体质问卷
```

---

## 六、目录结构

```
app/
  routers/
    rehab.py        # 康复档案 / 评估 / 中医体质
    student.py      # 患者端（日志、方案、指标、里程碑等）
    coach.py        # 治疗师端
    admin.py        # 管理端
    features.py     # 会员、优惠券、邀请、营收、提现、邮件推送
  services/         # 业务逻辑
  utils/            # 邮件、缓存等
static/
  js/rehab.js       # 康复档案 / 康复评估 / 中医体质
  js/student.js     # 患者端视图
  js/coach.js       # 治疗师端视图
  js/admin.js       # 管理端视图
sql/init.sql        # 康复化建表脚本
```
