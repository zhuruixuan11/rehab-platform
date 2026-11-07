-- =============================================================
-- 习惯/健身打卡追踪器 数据库初始化脚本
-- MySQL 8.0 / utf8mb4
-- 用法: mysql -uroot -p < sql/init.sql
-- 演示账号由 seed.py 创建（需 bcrypt 生成密码哈希）
-- 注意：SET NAMES 必须保留——Docker 镜像初始化时客户端默认 latin1，
-- 不加此行中文会被双重编码存成乱码
-- =============================================================

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS rehab_tracker
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'fitness_user'@'localhost' IDENTIFIED BY 'CHANGE_ME_DB_PASSWORD';
GRANT ALL PRIVILEGES ON rehab_tracker.* TO 'fitness_user'@'localhost';
FLUSH PRIVILEGES;

USE rehab_tracker;

-- -------------------------------------------------------------
-- 用户表
-- -------------------------------------------------------------
DROP TABLE IF EXISTS operation_logs;
DROP TABLE IF EXISTS system_configs;
DROP TABLE IF EXISTS announcements;
DROP TABLE IF EXISTS message_templates;
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS milestones;
DROP TABLE IF EXISTS body_records;
DROP TABLE IF EXISTS community_comments;
DROP TABLE IF EXISTS community_likes;
DROP TABLE IF EXISTS community_posts;
DROP TABLE IF EXISTS video_history;
DROP TABLE IF EXISTS video_notes;
DROP TABLE IF EXISTS videos;
DROP TABLE IF EXISTS makeup_requests;
DROP TABLE IF EXISTS rehab_log_comments;
DROP TABLE IF EXISTS rehab_log_details;
DROP TABLE IF EXISTS rehab_log_media;
DROP TABLE IF EXISTS rehab_logs;
DROP TABLE IF EXISTS program_items;
DROP TABLE IF EXISTS rehab_programs;
DROP TABLE IF EXISTS rehab_exercises;
DROP TABLE IF EXISTS therapist_profiles;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username        VARCHAR(50)  NOT NULL UNIQUE,
  password_hash   VARCHAR(100) NOT NULL,
  nickname        VARCHAR(50)  NOT NULL,
  role            ENUM('student','coach','admin') NOT NULL DEFAULT 'student',
  phone           VARCHAR(20)  DEFAULT NULL,
  gender          TINYINT      DEFAULT 0 COMMENT '0未知 1男 2女',
  avatar          VARCHAR(255) DEFAULT '',
  reminder_time   TIME         DEFAULT '20:00:00' COMMENT '每日打卡提醒时间',
  anonymous_rank  TINYINT      DEFAULT 0 COMMENT '排行榜是否匿名 0否 1是',
  current_streak  INT          DEFAULT 0 COMMENT '当前连续打卡天数',
  longest_streak  INT          DEFAULT 0 COMMENT '历史最长连续打卡',
  status          TINYINT      DEFAULT 1 COMMENT '1启用 0禁用',
  last_login_at   DATETIME     DEFAULT NULL,
  created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_role (role),
  INDEX idx_users_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 教练档案（资质审核）
-- -------------------------------------------------------------
CREATE TABLE therapist_profiles (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id        BIGINT UNSIGNED NOT NULL UNIQUE,
  real_name      VARCHAR(50)  DEFAULT '',
  bio            VARCHAR(500) DEFAULT '' COMMENT '个人履历',
  specialty      VARCHAR(200) DEFAULT '' COMMENT '擅长领域',
  certifications VARCHAR(500) DEFAULT '' COMMENT '证书描述',
  certificate_paths VARCHAR(500) DEFAULT '' COMMENT '证书附件路径,分隔',
  review_status  ENUM('none','pending','approved','rejected') DEFAULT 'none',
  review_note    VARCHAR(500) DEFAULT '',
  reviewed_by    BIGINT UNSIGNED DEFAULT NULL,
  reviewed_at    DATETIME     DEFAULT NULL,
  created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_coach_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 训练计划
-- -------------------------------------------------------------
CREATE TABLE rehab_programs (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  coach_id     BIGINT UNSIGNED NOT NULL,
  student_id   BIGINT UNSIGNED NOT NULL,
  title        VARCHAR(100) NOT NULL,
  description  VARCHAR(500) DEFAULT '',
  start_date   DATE NOT NULL,
  end_date     DATE NOT NULL,
  status       ENUM('active','inactive') DEFAULT 'active',
  is_recommended TINYINT DEFAULT 0 COMMENT '管理员推荐至首页 0否 1是',
  recommend_weight INT DEFAULT 0 COMMENT '推荐权重',
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_plans_coach (coach_id),
  INDEX idx_plans_student (student_id, status),
  CONSTRAINT fk_plan_coach FOREIGN KEY (coach_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_plan_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 计划动作明细（按天）
CREATE TABLE program_items (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  plan_id        BIGINT UNSIGNED NOT NULL,
  day_date       DATE NOT NULL,
  exercise_name  VARCHAR(100) NOT NULL,
  sets           INT DEFAULT 3 COMMENT '建议组数',
  reps           INT DEFAULT 12 COMMENT '建议次数',
  weight_suggest DECIMAL(6,2) DEFAULT 0 COMMENT '建议重量kg',
  rest_sec       INT DEFAULT 90 COMMENT '组间休息秒',
  note           VARCHAR(200) DEFAULT '',
  sort_order     INT DEFAULT 0,
  INDEX idx_plan_items_plan (plan_id, day_date),
  CONSTRAINT fk_plan_item_plan FOREIGN KEY (plan_id) REFERENCES training_plans(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 动作库（内置 + 教练自定义）
-- -------------------------------------------------------------
CREATE TABLE rehab_exercises (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  name           VARCHAR(100) NOT NULL,
  category       VARCHAR(50) NOT NULL COMMENT '部位: 胸/背/腿/肩/臂/核心/有氧',
  equipment      VARCHAR(50) DEFAULT '自重' COMMENT '器械',
  difficulty     TINYINT DEFAULT 1 COMMENT '1初级 2中级 3高级',
  intro          VARCHAR(500) DEFAULT '' COMMENT '一句话介绍',
  steps          TEXT COMMENT '动作步骤详解',
  tips           TEXT COMMENT '训练要点与常见错误',
  default_sets   INT DEFAULT 3,
  default_reps   INT DEFAULT 12,
  default_weight DECIMAL(6,2) DEFAULT 0,
  is_custom      TINYINT DEFAULT 0 COMMENT '0内置 1教练自定义',
  creator_id     BIGINT UNSIGNED DEFAULT NULL,
  muscles        JSON DEFAULT NULL COMMENT '发力肌群 {primary:[],secondary:[]}',
  breathing      VARCHAR(200) DEFAULT '' COMMENT '呼吸节奏',
  anim           VARCHAR(30) DEFAULT '' COMMENT '动作演示动画模式',
  video_url      VARCHAR(500) DEFAULT NULL COMMENT '教学视频地址',
  is_member_only TINYINT(1) DEFAULT 0 COMMENT '1会员专属',
  contraindications TEXT COMMENT '运动禁忌/不宜进行的情况',
  alternatives   TEXT COMMENT '替代动作建议',
  sort_order     INT NOT NULL DEFAULT 0 COMMENT '排序权重',
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_exercise_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 打卡
-- -------------------------------------------------------------
CREATE TABLE rehab_logs (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id       BIGINT UNSIGNED NOT NULL,
  checkin_date  DATE NOT NULL,
  content       TEXT,
  plan_id       BIGINT UNSIGNED DEFAULT NULL COMMENT '关联训练计划',
  train_volume  INT DEFAULT 0 COMMENT '总训练量kg',
  duration_min  INT DEFAULT 0 COMMENT '训练时长分钟',
  intensity     TINYINT DEFAULT 1 COMMENT '强度1-5（热力图层级）',
  vas_before    TINYINT DEFAULT NULL COMMENT '练前疼痛VAS 0-10',
  vas_after     TINYINT DEFAULT NULL COMMENT '练后疼痛VAS 0-10',
  is_makeup     TINYINT DEFAULT 0 COMMENT '是否补签',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_checkin_user_date (user_id, checkin_date),
  INDEX idx_checkin_date (checkin_date),
  CONSTRAINT fk_checkin_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE rehab_log_media (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  checkin_id BIGINT UNSIGNED NOT NULL,
  file_path  VARCHAR(255) NOT NULL,
  media_type ENUM('image','video') NOT NULL DEFAULT 'image',
  CONSTRAINT fk_media_checkin FOREIGN KEY (checkin_id) REFERENCES checkins(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 动作级训练数据
CREATE TABLE rehab_log_details (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  checkin_id    BIGINT UNSIGNED NOT NULL,
  exercise_name VARCHAR(100) NOT NULL,
  sets          INT DEFAULT 0,
  reps          INT DEFAULT 0,
  weight        DECIMAL(6,2) DEFAULT 0,
  rpe           TINYINT DEFAULT NULL COMMENT '主观疲劳度1-10',
  heart_rate    INT DEFAULT NULL,
  rest_sec      INT DEFAULT NULL,
  CONSTRAINT fk_detail_checkin FOREIGN KEY (checkin_id) REFERENCES checkins(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 教练对打卡的评论/指导
CREATE TABLE rehab_log_comments (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  checkin_id BIGINT UNSIGNED NOT NULL,
  coach_id   BIGINT UNSIGNED NOT NULL,
  content    VARCHAR(1000) NOT NULL,
  voice_path VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_comment_checkin FOREIGN KEY (checkin_id) REFERENCES checkins(id) ON DELETE CASCADE,
  CONSTRAINT fk_comment_coach FOREIGN KEY (coach_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 补签申请（教练审批）
CREATE TABLE makeup_requests (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id       BIGINT UNSIGNED NOT NULL,
  checkin_date  DATE NOT NULL,
  reason        VARCHAR(500) DEFAULT '',
  status        ENUM('pending','approved','rejected') DEFAULT 'pending',
  reviewed_by   BIGINT UNSIGNED DEFAULT NULL,
  review_note   VARCHAR(500) DEFAULT '',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  reviewed_at   DATETIME DEFAULT NULL,
  UNIQUE KEY uq_makeup_user_date (user_id, checkin_date),
  CONSTRAINT fk_makeup_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 社区动态
-- -------------------------------------------------------------
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE community_likes (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  post_id     BIGINT UNSIGNED NOT NULL,
  user_id     BIGINT UNSIGNED NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_post_like (post_id, user_id),
  CONSTRAINT fk_like_post FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_like_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE community_comments (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  post_id     BIGINT UNSIGNED NOT NULL,
  user_id     BIGINT UNSIGNED NOT NULL,
  content     VARCHAR(1000) NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_pc_post (post_id),
  CONSTRAINT fk_pc_post FOREIGN KEY (post_id) REFERENCES community_posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_pc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 身体数据
-- -------------------------------------------------------------
CREATE TABLE body_records (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  record_date DATE NOT NULL,
  weight      DECIMAL(5,2) DEFAULT NULL COMMENT 'kg',
  body_fat    DECIMAL(4,2) DEFAULT NULL COMMENT '%',
  chest       DECIMAL(5,2) DEFAULT NULL COMMENT '胸围cm',
  waist       DECIMAL(5,2) DEFAULT NULL,
  hip         DECIMAL(5,2) DEFAULT NULL,
  arm         DECIMAL(5,2) DEFAULT NULL,
  thigh       DECIMAL(5,2) DEFAULT NULL,
  photo_path  VARCHAR(255) DEFAULT '',
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_body_user_date (user_id, record_date),
  CONSTRAINT fk_body_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 成就
-- -------------------------------------------------------------
CREATE TABLE milestones (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id     BIGINT UNSIGNED NOT NULL,
  badge_code  VARCHAR(50) NOT NULL,
  unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_achievement (user_id, badge_code),
  CONSTRAINT fk_ach_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 消息（sender_id 为 NULL 表示系统消息）
-- -------------------------------------------------------------
CREATE TABLE messages (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  sender_id   BIGINT UNSIGNED DEFAULT NULL,
  receiver_id BIGINT UNSIGNED NOT NULL,
  msg_type    ENUM('text','image','voice','video','system') NOT NULL DEFAULT 'text',
  content     VARCHAR(2000) DEFAULT '',
  media_path  VARCHAR(255) DEFAULT '',
  is_read     TINYINT DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_msg_receiver (receiver_id, is_read),
  INDEX idx_msg_pair (sender_id, receiver_id, created_at),
  CONSTRAINT fk_msg_sender FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_msg_receiver FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 消息模板（coach_id 为 NULL 表示系统模板）
CREATE TABLE message_templates (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  coach_id   BIGINT UNSIGNED DEFAULT NULL,
  title      VARCHAR(100) NOT NULL,
  content    VARCHAR(1000) NOT NULL,
  category   VARCHAR(50) DEFAULT '通用',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 公告
-- -------------------------------------------------------------
CREATE TABLE announcements (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(100) NOT NULL,
  content     TEXT NOT NULL,
  is_pinned   TINYINT DEFAULT 0,
  status      ENUM('published','draft','offline') DEFAULT 'published',
  target_role ENUM('all','student','coach') DEFAULT 'all',
  publish_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_by  BIGINT UNSIGNED DEFAULT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 系统配置
-- -------------------------------------------------------------
CREATE TABLE system_configs (
  config_key   VARCHAR(50) PRIMARY KEY,
  config_value VARCHAR(200) NOT NULL,
  description  VARCHAR(200) DEFAULT '',
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- 管理员操作日志（保留90天，由定时清理）
-- -------------------------------------------------------------
CREATE TABLE operation_logs (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id   BIGINT UNSIGNED DEFAULT NULL,
  module     VARCHAR(50) NOT NULL,
  action     VARCHAR(50) NOT NULL,
  detail     VARCHAR(1000) DEFAULT '',
  ip         VARCHAR(50) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_oplog_time (created_at),
  INDEX idx_oplog_admin (admin_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================
-- 基础数据
-- =============================================================

INSERT INTO system_configs (config_key, config_value, description) VALUES
('checkin_window_start', '05:00', '每日打卡窗口开始时间'),
('checkin_window_end', '23:59', '每日打卡窗口结束时间'),
('makeup_days_limit', '7', '补签最多回溯天数'),
('ranking_refresh_sec', '300', '排行榜缓存刷新秒数'),
('max_image_size_mb', '10', '图片最大上传大小MB'),
('max_video_size_mb', '500', '视频最大上传大小MB'),
('log_retention_days', '90', '操作日志保留天数');

INSERT INTO rehab_exercises (name, category, equipment, difficulty, intro, steps, tips, default_sets, default_reps, default_weight) VALUES
('杠铃卧推', '胸', '杠铃', 2, '平卧推举是练厚胸部的黄金动作，主练胸大肌整体，三角肌前束与肱三头肌协同发力。',
 '1. 仰卧凳上，双脚踩实地面，肩胛骨后缩下沉，握距约为肩宽1.5倍；\n2. 请同伴保护，将杠铃从架上限位取出，直臂悬于胸口正上方；\n3. 吸气憋气收紧核心，控制杠铃缓慢下放至胸口中线附近（乳头连线位置）；\n4. 杠铃轻触胸后，脚向下蹬地传导力量，爆发将杠铃沿略向后上的轨迹推起；\n5. 顶点肘部接近伸直但不锁死，完成一次，重复至目标次数。',
 '· 下放过程肘部约与躯干呈45-70度夹角，完全外展容易伤肩；\n· 杠铃触胸位置过高练肩、过低练前束，中线最稳；\n· 臀部不离开凳面，靠腰背自然拱起维持稳定；\n· 大重量务必请人保护，力竭时切勿直接放弃杠铃。',
 4, 10, 50),
('哑铃飞鸟', '胸', '哑铃', 1, '孤立拉伸胸大肌的单关节动作，给胸肌中缝带来强烈的拉伸与挤压感。',
 '1. 双手持哑铃仰卧，双臂伸直于胸口上方，掌心相对，肘部微屈固定；\n2. 保持肘部角度不变，沿弧线缓慢向两侧张开双臂；\n3. 感受胸肌被拉长，下降至大臂与地面平行或略低（以不痛为限）；\n4. 想象环抱一棵大树，用胸肌发力将哑铃沿原弧线合拢；\n5. 顶端挤压胸肌1秒，再进行下一次。',
 '· 全程肘部角度保持不变，变成"卧推"就失去孤立意义；\n· 重量宁轻勿重，飞鸟是感受型动作；\n· 底部出现肩关节弹响或疼痛应立即减小幅度。',
 3, 12, 12),
('上斜哑铃卧推', '胸', '哑铃', 2, '上斜30-45度推举，重点刺激胸大肌上部与三角肌前束，改善上胸薄弱。',
 '1. 调节凳面至30-45度（角度过大偏向三角肌）；\n2. 坐于凳上，哑铃置于大腿，借力将其翻至肩前；\n3. 后仰贴稳凳面，哑铃置于肩上方两侧，肘部朝斜下方；\n4. 控制下放至上胸位置，哑铃略低于肩水平线；\n5. 用上胸发力将哑铃推向斜上方，顶端不完全并拢，保持张力。',
 '· 椅背角度超过45度会变成推肩，注意调整；\n· 顶端哑铃不碰撞，避免借力与损坏器械；\n· 下放时肩胛骨始终贴紧凳面。',
 4, 10, 20),
('引体向上', '背', '自重', 3, '自重练背之王，主练背阔肌与大圆肌，同时强化肱二头肌与核心稳定。',
 '1. 正握单杠，握距略宽于肩，身体自然悬垂，肩胛骨先激活下沉；\n2. 想象把杠"拉向胸口"，用肘部向下带动身体；\n3. 下巴过杠即算完成，顶端挤压背肌1秒；\n4. 缓慢下放至手臂接近伸直，保持背部张力不完全放松；\n5. 全程核心收紧，避免身体大幅度摆动借力。',
 '· 先沉肩再拉，耸肩会让斜方肌与手臂代偿；\n· 不要靠蹬腿摆体"甩"上去；\n· 做不满3个可用弹力带辅助或做离心（跳上慢放）训练。',
 4, 8, 0),
('杠铃划船', '背', '杠铃', 2, '俯身划船打造背部厚度的核心动作，主练背阔肌、斜方肌中部与菱形肌。',
 '1. 双脚与髋同宽，屈膝俯身至上半身接近平行地面，背部挺直；\n2. 正握杠铃，握距略宽于肩，核心收紧；\n3. 用背肌力量将杠铃拉向下腹部（肚脐附近）；\n4. 顶端肘部越过背部，挤压肩胛骨1秒；\n5. 缓慢沿大腿前侧下放至手臂伸直，重复。',
 '· 俯身角度小于45度会变成耸肩借力；\n· 拉向胸口会过多使用三角肌后束；\n· 腰背有伤者改用坐姿划船或器械。',
 4, 10, 40),
('高位下拉', '背', '器械', 1, '坐姿下拉是引体向上的最佳替代动作，安全可控地强化背阔肌宽度。',
 '1. 调整坐垫高度，大腿牢牢固定于海绵垫下；\n2. 正握横杆略宽于肩，身体后倾约15-20度，挺胸收腹；\n3. 想象肘部"向下插口袋"，肩胛骨下沉带动横杆下降；\n4. 将杆拉至锁骨/上胸位置，顶峰挤压背阔肌1秒；\n5. 控制横杆缓慢回放至手臂接近伸直，背部保持张力。',
 '· 用手臂"拽"杆是最常见错误，注意先沉肩、用背发力；\n· 身体过度后仰变成"划船式"借力；\n· 下放阶段要慢，离心阶段才是背肌增长关键。',
 3, 12, 35),
('硬拉', '腿/臀', '杠铃', 3, '全身性力量之王，练后侧链（臀大肌、腘绳肌、竖脊肌）效率最高的复合动作。',
 '1. 杠铃置于脚掌正上方中部，双脚与髋同宽，脚尖微外展；\n2. 屈髋俯身握杠，握距略宽于双脚，背部挺直、肩胛骨收紧；\n3. 起拉前吸气憋气，全身绷紧，想象"把地面推开"；\n4. 杠铃贴腿直线上升，髋膝同步伸展，顶端站直即可不过度后仰；\n5. 屈髋控制杠铃沿大腿滑落回地面，完成一次。',
 '· 起始时杠铃离身体太远会让腰椎受力剧增；\n· 背部任何时刻不允许弓起，宁轻勿弯；\n· 顶端过度挺髋后仰会挤压腰椎；\n· 佩戴腰带、使用六角杠可降低腰部压力。',
 5, 5, 60),
('杠铃深蹲', '腿/臀', '杠铃', 3, '下肢训练之王，全面发展股四头肌、臀大肌与核心力量。',
 '1. 杠铃置于斜方肌上（高杠位），双手扶稳，肘部下压；\n2. 双脚与肩同宽或略宽，脚尖自然外展30度左右；\n3. 吸气憋气收紧核心，屈髋屈膝同步下蹲，像坐椅子一样向后向下；\n4. 下蹲至大腿至少平行地面（髋低于膝），膝盖与脚尖方向一致；\n5. 全脚掌蹬地站起，顶端呼气，不锁死膝盖。',
 '· 重心始终落在脚掌中部，脚跟离地说明重心前移；\n· 膝盖内扣是膝盖损伤的头号风险；\n· 髋踝灵活性不足时可垫高脚跟或先练箱式深蹲。',
 5, 8, 50),
('腿举', '腿/臀', '器械', 1, '坐姿腿举对腰背压力小，适合新手安全地积累腿部训练量。',
 '1. 调整座椅使膝盖弯曲时约90度，双脚与肩同宽踩稳踏板；\n2. 双脚位置偏高更侧重臀与腘绳肌，偏低侧重股四头肌；\n3. 解开保险销，屈膝让踏板缓慢下降，下放至膝盖约90度；\n4. 脚掌发力将踏板推起，接近伸直时不锁死膝盖；\n5. 全程腰部与臀部贴紧靠垫。',
 '· 顶端锁死膝盖在负重下非常危险；\n· 臀部离开靠垫说明下放过深或重量过大；\n· 双脚站位不同可微调刺激重点。',
 4, 12, 80),
('哑铃推肩', '肩', '哑铃', 1, '坐姿哑铃推举是打造三角肌围度的主力动作，比杠铃活动度更自由。',
 '1. 坐于靠背凳，双脚踩实，腰部贴紧靠垫；\n2. 双手持哑铃举至肩侧，掌心朝前，肘部位于身体两侧略前方；\n3. 呼气将哑铃垂直上推至头顶上方接近合拢；\n4. 顶端不碰撞哑铃、不锁死肘部；\n5. 缓慢下放至大臂约平行地面或略低，重复。',
 '· 下放过低（哑铃低于肩）会给肩关节带来压力；\n· 腰部反弓过大说明重量超标；\n· 想练三角肌整体围度，坐姿比站姿更稳。',
 3, 12, 10),
('杠铃推举', '肩', '杠铃', 2, '站姿杠铃推举（军用推举）是发展肩部力量与全身稳定的经典动作。',
 '1. 双脚与髋同宽，杠铃置于锁骨前，双肘位于杠铃正下方；\n2. 全身绷紧，臀部与核心收紧，想象双脚钉进地面；\n3. 呼气将杠铃垂直向上推起，头部微微后移让杠铃贴面前通过；\n4. 顶端杠铃落于头顶正上方、耳朵侧后方，肘部伸直不锁死；\n5. 控制下放回锁骨位置，保持躯干稳定。',
 '· 腰部过度反弓（挺肚子）说明核心没收紧或重量太大；\n· 杠铃绕头走弧线会增大肩部压力；\n· 站姿推举对核心要求高，可先从坐姿开始。',
 4, 8, 30),
('哑铃弯举', '臂', '哑铃', 1, '最经典的肱二头肌孤立动作，可交替或同时进行。',
 '1. 双脚与肩同宽站立，双手持哑铃自然下垂于体侧，掌心朝前；\n2. 上臂贴近躯干并保持固定，肘部是唯一活动的关节；\n3. 呼气弯举哑铃至肩前，顶端挤压肱二头肌1秒；\n4. 缓慢下放至手臂接近伸直但不完全放松；\n5. 可在顶端外旋手腕（ supination）进一步强化收缩感。',
 '· 身体后仰甩动哑铃是最常见借力，宁可减轻重量；\n· 肘部前移会让三角肌前束代偿；\n· 控制离心（3秒下放）对增肌效果显著。',
 3, 12, 10),
('绳索下压', '臂', '器械', 1, '龙门架绳索下压是孤立训练肱三头肌的最佳动作之一，持续保持张力。',
 '1. 将绳索或直杆固定于高位，正握把手，肘部贴近躯干固定；\n2. 上臂保持不动，呼气用肱三头肌将把手下压；\n3. 顶端手臂完全伸直，停顿1秒并做顶峰收缩；\n4. 缓慢回放至前臂约平行地面，肘部角度不完全放开；\n5. 使用绳索时顶端可向外旋开，强化收缩。',
 '· 肘部外飘或前后移动会让胸背代偿；\n· 身体过度前倾压重量是借力表现；\n· 想让手臂变粗，肱三头肌占上臂围度约2/3，不可只练弯举。',
 3, 12, 20),
('平板支撑', '核心', '自重', 1, '静态等长收缩训练，强化腹横肌与深层核心，提升全身稳定性。',
 '1. 俯卧，双肘撑地位于肩部正下方，双脚并拢或略分开；\n2. 头、背、臀、脚跟保持一条直线，视线朝下；\n3. 收紧腹部与臀部，想象肚脐拉向脊柱；\n4. 保持自然呼吸不憋气，坚持目标时间；\n5. 塌腰或撅臀立即停止，质量重于时长。',
 '· 塌腰是腰椎代偿，宁可时间短也要保持直线；\n· 肩胛骨保持平整，不耸肩缩脖子；\n· 能稳定坚持2分钟以上可升级为动态变式。',
 3, 60, 0),
('卷腹', '核心', '自重', 1, '上固定式腹肌训练，主练腹直肌上部，比传统仰卧起坐更安全。',
 '1. 仰卧屈膝约90度，双脚平放，双手轻扶耳侧或交叉于胸前；\n2. 下背部贴紧地面，呼气用腹肌力量将肩胛骨抬离地面；\n3. 顶端挤压腹肌1-2秒，腰部始终不离开地面；\n4. 缓慢下放肩胛骨轻触地面即再次卷起；\n5. 动作幅度小而慢，感受腹肌全程发力。',
 '· 双手抱头用力拉扯颈部是常见错误，只轻扶即可；\n· 不要用惯性"弹"起来；\n· 想练下腹改做反向卷腹（抬腿卷盆骨）。',
 3, 20, 0),
('跑步机慢跑', '有氧', '器械', 1, '最普及的有氧训练方式，提升心肺功能、燃烧热量，配速可控易坚持。',
 '1. 先以4-5km/h快走1-2分钟热身，再逐步提升速度；\n2. 跑姿：身体微前倾、落地于脚掌中部、步幅不宜过大；\n3. 保持匀速慢跑（能边跑边说话的强度），新手从20分钟开始；\n4. 结束前逐步降速至快走3-5分钟冷身；\n5. 每周跑量增幅不超过10%，给关节适应时间。',
 '· 抓扶手跑会大幅降低训练效果；\n· 步幅过大、脚跟重击容易伤膝；\n· 体重基数大者优先选择快走/椭圆机减轻关节冲击。',
 1, 30, 0),
('动感单车', '有氧', '器械', 1, '低冲击高燃脂的室内有氧，跟随课程节奏骑行，对膝盖压力小。',
 '1. 调节坐垫高度：踩到最低点时膝盖微屈约25-30度；\n2. 车把高度与坐垫齐平或略高，避免过度弯腰；\n3. 前脚掌踩踏板，用画圆的轨迹发力；\n4. 阻力随课程节奏调整，保持踏频80-110rpm；\n5. 结束后慢骑2-3分钟冷身，再进行下肢拉伸。',
 '· 阻力为0时空踩伤膝，保持适当阻力；\n· 肩颈放松，不要耸肩撑车把；\n· 骑行前后注意补水。',
 1, 45, 0),
('椭圆机', '有氧', '器械', 1, '关节友好的全身性有氧器械，手脚并用，适合大体重与膝盖不适人群。',
 '1. 双脚全掌踩稳踏板，双手轻握活动扶手；\n2. 身体直立微前倾，核心收紧，不塌腰驼背；\n3. 平滑地推拉扶手并蹬踏踏板，保持连贯节奏；\n4. 阻力与坡度调节至微微出汗但仍可匀速运动的强度；\n5. 持续20-45分钟，结束前逐步降低阻力冷身。',
 '· 脚跟抬起或踮脚会加剧小腿疲劳；\n· 全身重量压在扶手上会降低消耗；\n· 想增阻力优先加坡度而非一味加快频率。',
 1, 30, 0);

INSERT INTO announcements (title, content, is_pinned, status, target_role, created_by) VALUES
('欢迎使用康衡康复中心', '康复是循序渐进的过程，每天完成康复训练后记得记录，治疗师会据此调整您的康复方案。', 1, 'published', 'all', NULL),
('社区动态已上线', '康复心得、进步瞬间都可以发布到社区，还可以自行设置动态的可见范围。', 0, 'published', 'all', NULL);

INSERT INTO message_templates (coach_id, title, content, category) VALUES
(NULL, '康复训练提醒', '您好，今天还没有记录康复训练哦，训练结束后记得记录，方便治疗师评估恢复进度！', '打卡提醒'),
(NULL, '方案更新', '您的康复方案已更新，请查看最新安排并按方案执行。', '计划更新'),
(NULL, '康复鼓励', '康复是循序渐进的过程，坚持每一天都会看到进步！', '鼓励');

-- =============================================================
-- 康复专业模块（康复档案 / 康复评估 / 中医体质）
-- =============================================================

CREATE TABLE IF NOT EXISTS rehab_cases (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  therapist_id BIGINT UNSIGNED DEFAULT NULL,
  condition_name VARCHAR(120) NOT NULL COMMENT '病症/损伤名称',
  condition_type VARCHAR(40) NOT NULL DEFAULT '运动损伤' COMMENT '骨科术后/运动损伤/慢性疼痛/神经康复/体态矫正',
  injured_side VARCHAR(10) DEFAULT '左' COMMENT '左/右/双侧',
  onset_date DATE DEFAULT NULL,
  stage VARCHAR(20) DEFAULT '恢复期' COMMENT '急性期/恢复期/强化期/维持期',
  chief_complaint VARCHAR(500) DEFAULT '',
  diagnosis VARCHAR(500) DEFAULT '',
  goal VARCHAR(500) DEFAULT '',
  status VARCHAR(20) DEFAULT 'active' COMMENT 'active/paused/closed',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_patient (patient_id), KEY idx_therapist (therapist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='康复档案（病例）';

CREATE TABLE IF NOT EXISTS rehab_assessments (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  case_id BIGINT UNSIGNED DEFAULT NULL,
  assess_date DATE NOT NULL,
  assessor_id BIGINT UNSIGNED DEFAULT NULL,
  pain_vas TINYINT DEFAULT 0 COMMENT '疼痛VAS 0-10',
  rom_json TEXT COMMENT '关节活动度',
  mmt_json TEXT COMMENT '徒手肌力MMT',
  balance_score TINYINT DEFAULT 0,
  gait_score TINYINT DEFAULT 0,
  posture_score TINYINT DEFAULT 0,
  adl_score TINYINT DEFAULT 0,
  berg_score TINYINT DEFAULT NULL COMMENT 'Berg平衡量表 0-56',
  tug_sec DECIMAL(5,1) DEFAULT NULL COMMENT '起立行走TUG秒',
  walk10m_sec DECIMAL(5,1) DEFAULT NULL COMMENT '10米步行秒',
  odi_score TINYINT DEFAULT NULL COMMENT 'ODI功能障碍指数 0-100',
  womac_score TINYINT DEFAULT NULL COMMENT 'WOMAC骨关节炎指数 0-100',
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_patient_date (patient_id, assess_date), KEY idx_case (case_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='康复评估记录';

CREATE TABLE IF NOT EXISTS tcm_constitutions (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  primary_type VARCHAR(20) NOT NULL COMMENT '九种体质之一',
  scores_json TEXT,
  advice TEXT,
  assessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_patient (patient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='中医体质辨识结果';

-- -------------------------------------------------------------
-- 2026-11 康复业务扩展：红旗征筛查 / 排班预约 / 疗程卡 / 随访
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rehab_screenings (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  case_id BIGINT UNSIGNED DEFAULT NULL,
  assessor_id BIGINT UNSIGNED DEFAULT NULL,
  items_json TEXT COMMENT '筛查项 {key: true/false}',
  has_red_flag TINYINT DEFAULT 0,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_patient (patient_id), KEY idx_case (case_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='红旗征筛查';

CREATE TABLE IF NOT EXISTS therapist_schedules (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  coach_id BIGINT UNSIGNED NOT NULL,
  work_date DATE NOT NULL,
  start_time VARCHAR(5) NOT NULL,
  end_time VARCHAR(5) NOT NULL,
  slot_min INT DEFAULT 30 COMMENT '每个号源分钟数',
  capacity INT DEFAULT 1 COMMENT '同时可预约人数',
  location VARCHAR(100) DEFAULT '康衡康复中心',
  note VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_coach_date (coach_id, work_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='治疗师排班';

CREATE TABLE IF NOT EXISTS appointments (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  coach_id BIGINT UNSIGNED NOT NULL,
  schedule_id BIGINT UNSIGNED DEFAULT NULL,
  appt_date DATE NOT NULL,
  start_time VARCHAR(5) NOT NULL,
  end_time VARCHAR(5) DEFAULT '',
  appt_type VARCHAR(30) DEFAULT '门诊评估',
  status VARCHAR(20) DEFAULT 'booked' COMMENT 'booked/completed/cancelled',
  note VARCHAR(500) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_patient (patient_id), KEY idx_coach_date (coach_id, appt_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='康复预约';

CREATE TABLE IF NOT EXISTS treatment_cards (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  case_id BIGINT UNSIGNED DEFAULT NULL,
  title VARCHAR(100) NOT NULL,
  total_sessions INT DEFAULT 10,
  used_sessions INT DEFAULT 0,
  valid_from DATE DEFAULT NULL,
  valid_to DATE DEFAULT NULL,
  status VARCHAR(20) DEFAULT 'active' COMMENT 'active/finished/expired',
  note VARCHAR(255) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_patient (patient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='疗程卡';

CREATE TABLE IF NOT EXISTS followups (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  patient_id BIGINT UNSIGNED NOT NULL,
  coach_id BIGINT UNSIGNED NOT NULL,
  case_id BIGINT UNSIGNED DEFAULT NULL,
  due_date DATE DEFAULT NULL,
  content VARCHAR(500) DEFAULT '',
  status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/sent',
  sent_at DATETIME DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_patient (patient_id), KEY idx_coach (coach_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='随访提醒';

-- 康复动作库（分阶段：术后早期 / 肩关节 / 颈腰椎 / 髋膝踝 / 核心稳定 / 平衡协调 / 呼吸训练 / 心肺耐力）
-- 原有健身动作统一归入「力量进阶」，仅在恢复后期由治疗师评估后使用
UPDATE rehab_exercises SET category='力量进阶', sort_order=900 WHERE is_custom=0 AND category IN ('胸','背','腿/臀','肩','臂','核心');
UPDATE rehab_exercises SET category='心肺耐力', sort_order=805 WHERE is_custom=0 AND category='有氧';

INSERT INTO rehab_exercises (name, category, equipment, difficulty, intro, steps, tips, default_sets, default_reps, default_weight, is_custom, sort_order, is_member_only) VALUES
('股四头肌等长收缩', '术后早期', '自重', 1, '不移动膝关节的前提下激活大腿前侧肌力，预防术后股四头肌萎缩。', '1. 仰卧伸膝，膝下可垫一条薄毛巾；\n2. 用力绷紧大腿前侧，将膝窝向下压；\n3. 保持5-10秒后完全放松3秒；\n4. 重复至目标次数。', '· 只绷紧不抬腿，避免髋部代偿；\n· 疼痛明显或关节肿胀加重时减少强度；\n· 每日可分多次练习，累计完成即可。', 3, 10, 0, 0, 101, 0),
('臀肌等长收缩', '术后早期', '自重', 1, '激活臀大肌，为后期站立、行走与髋部稳定打基础。', '1. 仰卧屈膝，双脚平放于床面；\n2. 收紧臀部像夹紧一样，保持5-10秒；\n3. 完全放松3秒后重复。', '· 避免憋气与腰部代偿；\n· 髋关节置换术后需遵医嘱；\n· 以酸胀感为宜，不应出现锐痛。', 3, 10, 0, 0, 102, 0),
('肩关节钟摆运动', '术后早期', '自重', 1, '利用重力让患肩放松摆动，温和维持肩关节活动度。', '1. 健侧手扶桌沿，身体前倾；\n2. 患臂自然下垂，像钟摆一样前后、左右轻摆；\n3. 再画小圈，由小到大；\n4. 每个方向约10次。', '· 全程肩部放松，不主动用力；\n· 肩袖修复术后早期禁止大幅度画圈；\n· 出现弹响伴疼痛应停止并咨询治疗师。', 2, 10, 0, 0, 103, 0),
('深呼吸训练', '术后早期', '自重', 1, '改善术后浅快呼吸，预防肺不张与肺部感染。', '1. 半卧位或坐位，一手放胸口、一手放腹部；\n2. 用鼻缓慢吸气3秒，感受腹部隆起；\n3. 缩唇缓慢呼气5秒；\n4. 每组10次，每日3-4组。', '· 避免用力过猛引起伤口疼痛；\n· 可配合有效咳嗽训练；\n· 出现头晕时先恢复自然呼吸。', 3, 10, 0, 0, 104, 0),
('肩前屈主动辅助训练', '肩关节', '毛巾/桌面', 1, '用健侧手或桌面辅助患肩前屈，早期安全恢复活动度。', '1. 仰卧或坐位，双手握住毛巾或木棍；\n2. 健侧手带动患侧手向前上方抬起；\n3. 到轻微牵拉感处停留2秒；\n4. 缓慢放下，重复。', '· 以不痛为限，不强求抬高高度；\n· 肩袖术后需遵循医生允许的角度；\n· 避免耸肩代偿。', 3, 10, 0, 0, 200, 0),
('肩外旋等长收缩', '肩关节', '墙面', 1, '在肘部贴身状态下激活肩袖外旋肌群，早期安全练力。', '1. 屈肘90度，肘部夹紧身体；\n2. 手背抵住墙面；\n3. 用约30%力量向外推墙，保持5秒；\n4. 放松后重复。', '· 身体不要转动；\n· 力量由轻到重，不追求最大力；\n· 肩袖修复术后需在治疗师指导下进行。', 3, 8, 0, 0, 201, 0),
('弹力带肩外旋', '肩关节', '弹力带', 2, '强化冈下肌与小圆肌，改善肩关节动态稳定。', '1. 屈肘90度，肘部夹毛巾贴身；\n2. 弹力带固定于健侧，患手握另一端；\n3. 缓慢向外旋转前臂；\n4. 控制回到起始位。', '· 肘部始终不离开身体；\n· 避免用躯干旋转借力；\n· 选择能完成12次且动作不变形的阻力。', 3, 12, 0, 0, 202, 0),
('墙面爬墙', '肩关节', '墙面', 1, '借助墙面逐步恢复肩关节前屈活动度。', '1. 面对墙站立，患手指尖触墙；\n2. 手指像爬楼梯一样向上爬；\n3. 到轻微牵拉感处标记高度；\n4. 缓慢退回，重复。', '· 不憋气、不耸肩；\n· 每日可多次，逐步提高高度；\n· 疼痛超过3分（0-10）应降低高度。', 3, 10, 0, 0, 203, 0),
('肩胛后缩训练', '肩关节', '自重', 1, '激活中下斜方肌与菱形肌，改善圆肩与肩胛控制。', '1. 坐或站姿，双臂自然下垂；\n2. 将两侧肩胛骨向后、向下轻轻夹紧；\n3. 保持5秒后放松；\n4. 重复。', '· 不耸肩、不过度挺胸；\n· 动作幅度小而精准；\n· 可配合弹力带增加阻力。', 3, 12, 0, 0, 204, 0),
('弹力带划船', '肩关节', '弹力带', 2, '强化背部与肩胛回缩肌群，改善肩关节前侧压力。', '1. 弹力带固定于胸前高度；\n2. 双手握带，手臂伸直；\n3. 肩胛先后缩，再屈肘将带拉向肋侧；\n4. 缓慢还原。', '· 避免耸肩与腰部后仰；\n· 肘部贴近身体；\n· 肩痛加重时减小阻力。', 3, 12, 0, 0, 205, 0),
('颈椎后缩训练', '颈腰椎', '自重', 1, '纠正头前引，激活颈深屈肌，缓解颈肩紧张。', '1. 坐位，目视前方；\n2. 下巴水平向后收，像做出双下巴；\n3. 保持5秒；\n4. 放松后重复。', '· 不低头、不仰头；\n· 动作轻柔，出现头晕立即停止；\n· 久坐时每小时可做5次。', 3, 10, 0, 0, 300, 0),
('颈部等长抗阻', '颈腰椎', '手', 1, '四方向轻度抗阻，安全增强颈部稳定性。', '1. 手掌分别抵住前额、后脑、左右颞侧；\n2. 头保持不动，用手施加约20-30%力量；\n3. 每个方向保持5秒；\n4. 四个方向为一组。', '· 全程不产生明显头部移动；\n· 力量轻柔，不追求强度；\n· 颈椎急性损伤或术后遵医嘱。', 2, 4, 0, 0, 301, 0),
('猫牛式', '颈腰椎', '瑜伽垫', 1, '温和活动脊柱各节段，改善腰背僵硬。', '1. 四点跪位，手在肩下、膝在髋下；\n2. 吸气塌腰抬头（牛式）；\n3. 呼气拱背低头（猫式）；\n4. 缓慢往返。', '· 动作跟随呼吸，不追求幅度；\n· 手腕不适可改握拳撑地；\n· 急性腰痛期先咨询治疗师。', 2, 10, 0, 0, 302, 0),
('鸟狗式', '颈腰椎', '瑜伽垫', 2, '训练躯干抗旋转稳定，强化臀肌与背部。', '1. 四点跪位，收紧腹部；\n2. 对侧手与腿同时伸直；\n3. 保持2-3秒后收回；\n4. 换另一侧。', '· 骨盆保持水平，不塌腰；\n· 先做单侧手脚再进阶对侧；\n· 腰部不适时减小幅度。', 3, 8, 0, 0, 303, 0),
('臀桥', '颈腰椎', '瑜伽垫', 1, '激活臀大肌、缓解久坐腰痛，改善髋伸肌力。', '1. 仰卧屈膝，双脚与髋同宽；\n2. 呼气收紧臀部将髋抬起；\n3. 肩、髋、膝成一条直线；\n4. 保持2秒后缓慢落下。', '· 不要用腰部顶起；\n· 顶端不追求过高；\n· 膝痛者减小幅度。', 3, 12, 0, 0, 304, 0),
('麦肯基俯卧伸展', '颈腰椎', '瑜伽垫', 1, '通过腰椎伸展方向自我松动，适合部分椎间盘源性腰痛。', '1. 俯卧，双手撑于肩下；\n2. 保持骨盆贴地，缓慢撑起上半身；\n3. 到腰部有轻微压迫感即停；\n4. 保持5-10秒后放下。', '· 仅适用于伸展方向症状减轻者；\n· 出现腿部放射痛加重立即停止；\n· 急性期先由治疗师评估。', 2, 8, 0, 0, 305, 0),
('坐位伸膝', '髋膝踝', '椅子', 1, '在坐位下安全强化股四头肌，改善伸膝控制。', '1. 坐于椅面前缘，双脚着地；\n2. 缓慢伸直一侧膝盖至大腿与地面平行；\n3. 保持2秒后缓慢放下；\n4. 两侧交替进行。', '· 避免甩腿借力；\n· 膝关节术后遵循允许角度；\n· 动作全程缓慢控制。', 3, 12, 0, 0, 400, 0),
('直腿抬高', '髋膝踝', '瑜伽垫', 1, '强化髋屈肌与股四头肌，膝术后早期常用。', '1. 仰卧，健侧屈膝，患腿伸直；\n2. 绷紧大腿前侧后缓慢抬腿约30-40度；\n3. 保持2秒后缓慢放下。', '· 抬腿时膝盖保持伸直；\n· 腰部不拱起；\n· 髋关节置换术后需遵医嘱。', 3, 10, 0, 0, 401, 0),
('靠墙静蹲', '髋膝踝', '墙面', 2, '低负荷等长训练，增强股四头肌与膝关节稳定。', '1. 背靠墙站立，双脚向前迈半步；\n2. 沿墙缓慢下滑至膝屈30-45度；\n3. 膝盖不超过脚尖；\n4. 保持20-40秒后站起。', '· 膝痛明显时减小屈膝角度；\n· 膝盖与脚尖同向，不内扣；\n· 全程自然呼吸不憋气。', 3, 30, 0, 0, 402, 0),
('坐站转移训练', '髋膝踝', '椅子', 1, '训练从坐到站的功能性动作，提升下肢力量与平衡。', '1. 坐于稳固椅子前缘，双脚后收；\n2. 身体前倾，用双腿发力站起；\n3. 站稳后再缓慢坐下。', '· 双手先扶椅再进阶不扶手；\n· 膝盖不内扣；\n· 出现头晕立即坐下。', 3, 10, 0, 0, 403, 0),
('低台阶上下', '髋膝踝', '台阶', 2, '模拟上下楼功能，逐步恢复单腿支撑力量。', '1. 面对10-15cm低台阶；\n2. 患腿先上，健腿跟上；\n3. 下台阶时健腿先下；\n4. 控制速度不跳跃。', '· 全程扶好扶手；\n· 膝盖与脚尖同向；\n· 术后早期不做患腿先下。', 3, 10, 0, 0, 404, 0),
('提踵', '髋膝踝', '自重', 1, '强化小腿三头肌，改善步行推进与静脉回流。', '1. 扶墙站立，双脚与髋同宽；\n2. 缓慢踮起脚跟至最高点；\n3. 保持1-2秒后缓慢落下。', '· 踝关节不稳者扶稳；\n· 不左右晃动；\n· 跟腱术后遵医嘱。', 3, 15, 0, 0, 405, 0),
('蚌式开合', '髋膝踝', '弹力带', 1, '强化臀中肌，改善膝内扣与髋部稳定。', '1. 侧卧，双膝屈曲，脚跟并拢；\n2. 保持骨盆不后倒，缓慢打开上侧膝盖；\n3. 到最大范围后缓慢合拢。', '· 身体不要向后翻；\n· 动作幅度小也可有效；\n· 髋外侧酸胀属正常。', 3, 12, 0, 0, 406, 0),
('腹式呼吸核心激活', '核心稳定', '自重', 1, '建立正确的呼吸-核心协同，为所有康复训练打基础。', '1. 仰卧屈膝，一手放腹部；\n2. 鼻吸气使腹部隆起，胸口保持不动；\n3. 缓慢呼气并将下腹轻轻收紧；\n4. 每组8-10次。', '· 不要用力鼓肚子；\n· 呼气时肋骨下沉；\n· 头晕时恢复自然呼吸。', 3, 10, 0, 0, 500, 0),
('改良平板支撑', '核心稳定', '瑜伽垫', 1, '跪姿降低负荷，安全训练躯干抗伸展稳定。', '1. 双膝跪地，肘撑于肩下；\n2. 头、背、臀成一条直线；\n3. 收紧腹部与臀部，保持20-40秒；\n4. 休息后重复。', '· 塌腰立即停止；\n· 全程不憋气；\n· 肩痛者调整前臂支撑角度。', 3, 30, 0, 0, 501, 0),
('改良侧桥', '核心稳定', '瑜伽垫', 2, '强化腹斜肌与臀中肌，提升侧向稳定。', '1. 侧卧，前臂撑地，膝屈90度；\n2. 将髋部抬离地面；\n3. 保持20-30秒后换侧。', '· 肩肘在一条直线上；\n· 骨盆不前后倾；\n· 腰部不适时缩短时间。', 3, 25, 0, 0, 502, 0),
('双足并拢站立', '平衡协调', '自重', 1, '缩小支撑面，训练静态平衡，适合早期平衡训练。', '1. 扶稳桌边站立；\n2. 双脚并拢，目视前方；\n3. 保持20-30秒；\n4. 逐步减少扶手。', '· 身边保持有支撑物；\n· 头晕立即坐下；\n· 闭眼进阶需有人保护。', 3, 30, 0, 0, 600, 0),
('单腿站立', '平衡协调', '自重', 2, '单腿支撑训练，提升步行与上下楼稳定性。', '1. 扶墙站立，重心移到一侧腿；\n2. 另一侧脚离地数厘米；\n3. 保持10-30秒后换腿。', '· 膝盖微屈不锁死；\n· 骨盆保持水平；\n· 周围留出安全空间。', 3, 20, 0, 0, 601, 0),
('足跟脚尖直线行走', '平衡协调', '自重', 2, '动态平衡与步态协调训练，改善行走稳定性。', '1. 沿直线行走，脚跟紧接脚尖；\n2. 双臂自然摆动；\n3. 目视前方；\n4. 往返5-10米。', '· 靠近墙面或有陪护；\n· 速度慢、步子小；\n· 出现眩晕时停止。', 3, 10, 0, 0, 602, 0),
('缩唇呼吸', '呼吸训练', '自重', 1, '延长呼气、减少气促，适合心肺功能较弱者。', '1. 经鼻吸气2秒；\n2. 缩唇如吹蜡烛，缓慢呼气4-6秒；\n3. 吸呼比约1:2；\n4. 每组10次。', '· 不深吸猛呼；\n· 气促时先休息再练；\n· 慢阻肺患者需遵医嘱。', 3, 10, 0, 0, 700, 0),
('放松腹式呼吸', '呼吸训练', '自重', 1, '激活副交感神经，缓解疼痛与焦虑。', '1. 舒适坐卧，双手放腹部；\n2. 鼻吸气4秒，腹部隆起；\n3. 屏息2秒；\n4. 口呼气6秒，重复10次。', '· 以放松为目的，不追求深度；\n· 睡前练习有助睡眠；\n· 头晕时缩短屏息。', 3, 10, 0, 0, 701, 0),
('六分钟步行训练', '心肺耐力', '自重', 1, '以自身节奏快走6分钟，安全评估并提升心肺耐力。', '1. 选择平整场地，穿舒适鞋；\n2. 以能说话但略喘的速度行走；\n3. 记录6分钟步行距离；\n4. 结束后慢走放松。', '· 出现胸闷、头晕、明显气促立即停止；\n· 术后或心肺疾病患者需医生评估；\n· 每周3-5次。', 1, 6, 0, 0, 800, 0),
('低阻力功率自行车', '心肺耐力', '功率车', 1, '坐位低冲击有氧，适合下肢术后早期恢复心肺。', '1. 调整座椅至踩踏时膝微屈；\n2. 从低阻力开始热身3分钟；\n3. 保持能交谈的强度骑10-20分钟；\n4. 结束低阻力放松。', '· 膝痛时降低阻力；\n· 术后遵循负重限制；\n· 监测心率与疲劳度。', 1, 15, 0, 0, 801, 0);

-- 康复动作全部免费开放，避免患者因付费墙无法获得基础训练指导
UPDATE rehab_exercises SET is_member_only=0 WHERE is_custom=0 AND category IN ('术后早期','肩关节','颈腰椎','髋膝踝','核心稳定','平衡协调','呼吸训练','心肺耐力');

INSERT INTO rehab_exercises (name, category, equipment, difficulty, intro, steps, tips, default_sets, default_reps, default_weight, is_custom, sort_order, is_member_only) VALUES
('踝泵运动', '术后早期', '自重', 1, '通过踝关节屈伸带动小腿肌肉泵，促进下肢静脉回流，预防术后血栓与肿胀。', '1. 仰卧或坐位，双腿伸直放松；\n2. 缓慢用力勾脚尖至最大背屈，保持2秒；\n3. 再向下踩至最大跖屈，保持2秒；\n4. 双脚交替或同时进行，节奏缓慢均匀。', '· 麻醉消退后即可开始，以不引起明显疼痛为度；\n· 踝部骨折内固定术后需遵医嘱限制活动范围；\n· 出现小腿胀痛、发热应立即告知医生。', 3, 20, 0, 0, 100, 0);
UPDATE rehab_exercises SET is_member_only=0 WHERE name='踝泵运动';

-- BODY_PART_LIBRARY_V1
-- 动作库按身体部位分类（康复中心口径）
UPDATE rehab_exercises SET category=NULL WHERE is_custom=0;
UPDATE rehab_exercises SET category='肩部', sort_order=10 WHERE name IN ('哑铃推肩', '杠铃推举', '哑铃侧平举', '面拉', '肩关节钟摆运动', '肩前屈主动辅助训练', '肩外旋等长收缩', '弹力带肩外旋', '墙面爬墙', '肩胛后缩训练', '弹力带划船');
UPDATE rehab_exercises SET category='肘腕', sort_order=110 WHERE name IN ('哑铃弯举', '绳索下压', '锤式弯举', '仰卧臂屈伸');
UPDATE rehab_exercises SET category='颈腰椎', sort_order=210 WHERE name IN ('颈椎后缩训练', '颈部等长抗阻', '猫牛式', '鸟狗式', '麦肯基俯卧伸展');
UPDATE rehab_exercises SET category='胸背', sort_order=310 WHERE name IN ('杠铃卧推', '哑铃飞鸟', '上斜哑铃卧推', '双杠臂屈伸', '蝴蝶机夹胸', '引体向上', '杠铃划船', '高位下拉', '坐姿划船', '直臂下压');
UPDATE rehab_exercises SET category='核心躯干', sort_order=410 WHERE name IN ('平板支撑', '卷腹', '悬垂举腿', '俄罗斯转体', '腹式呼吸核心激活', '改良平板支撑', '改良侧桥');
UPDATE rehab_exercises SET category='髋部', sort_order=510 WHERE name IN ('硬拉', '罗马尼亚硬拉', '臀桥', '臀肌等长收缩', '蚌式开合');
UPDATE rehab_exercises SET category='膝部', sort_order=610 WHERE name IN ('杠铃深蹲', '腿举', '保加利亚分腿蹲', '俯卧腿弯举', '股四头肌等长收缩', '坐位伸膝', '直腿抬高', '靠墙静蹲', '坐站转移训练', '低台阶上下');
UPDATE rehab_exercises SET category='踝足', sort_order=710 WHERE name IN ('站姿提踵', '踝泵运动', '提踵');
UPDATE rehab_exercises SET category='平衡步态', sort_order=810 WHERE name IN ('双足并拢站立', '单腿站立', '足跟脚尖直线行走');
UPDATE rehab_exercises SET category='心肺全身', sort_order=910 WHERE name IN ('跑步机慢跑', '动感单车', '椭圆机', '跳绳', '深呼吸训练', '缩唇呼吸', '放松腹式呼吸', '六分钟步行训练', '低阻力功率自行车');

INSERT INTO rehab_exercises (name, category, equipment, difficulty, intro, steps, tips, default_sets, default_reps, default_weight, is_custom, sort_order, is_member_only) VALUES
('弹力带肩内旋', '肩部', '弹力带', 2, '强化肩胛下肌，改善肩关节前侧稳定。', '1. 屈肘90度，肘部夹毛巾贴身；\n2. 弹力带固定于患侧，手握另一端；\n3. 缓慢向内旋转前臂；\n4. 控制回到起始位。', '· 肘部始终不离开身体；\n· 选择能完成12次且动作不变形的阻力；\n· 肩前侧疼痛时暂停。', 3, 12, 0, 0, 120, 0),
('侧卧肩外旋', '肩部', '轻哑铃', 2, '在侧卧位下强化肩袖外旋肌，负荷更集中。', '1. 健侧卧，患侧在上，屈肘90度；\n2. 肘部贴住身体，手握轻哑铃；\n3. 缓慢向上旋转前臂；\n4. 控制放下。', '· 肘部不离开体侧；\n· 用1-2kg即可，重了容易代偿；\n· 肩袖术后遵医嘱。', 3, 12, 0, 0, 130, 0),
('肩水平外展', '肩部', '自重', 1, '恢复肩关节水平面活动度，改善肩前侧紧张。', '1. 仰卧屈膝，双臂向两侧伸直；\n2. 掌心向上，缓慢将手臂向头侧下放；\n3. 到轻微牵拉感处停留5秒；\n4. 缓慢还原。', '· 保持肩胛贴床；\n· 不追求下放幅度；\n· 肩痛明显时垫高前臂。', 3, 10, 0, 0, 140, 0),
('墙上天使', '肩部', '墙面', 1, '改善胸椎伸展与肩胛上回旋，纠正圆肩驼背。', '1. 背靠墙站立，后脑、肩胛、臀部贴墙；\n2. 双臂贴墙呈W形；\n3. 缓慢沿墙向上滑至Y形；\n4. 控制回到W形。', '· 腰部不离开墙面；\n· 只滑到不耸肩的高度；\n· 动作缓慢，配合呼吸。', 2, 10, 0, 0, 150, 0),
('腕屈伸活动', '肘腕', '自重', 1, '维持腕关节活动度，缓解术后或制动后僵硬。', '1. 前臂放于桌面，手掌悬空；\n2. 缓慢向上抬起手腕；\n3. 再缓慢向下屈腕；\n4. 每个方向停留2秒。', '· 动作在无痛范围内进行；\n· 腕部骨折术后遵医嘱；\n· 不甩动手腕。', 3, 15, 0, 0, 210, 0),
('前臂旋前旋后', '肘腕', '自重', 1, '恢复前臂旋转功能，改善拧毛巾、开门等日常动作。', '1. 屈肘90度，前臂贴住身体；\n2. 掌心向上缓慢翻转至掌心向下；\n3. 再缓慢翻回；\n4. 保持肘部不动。', '· 肘部夹紧不晃动；\n· 速度慢，范围以不痛为限；\n· 可握轻物增加感觉输入。', 3, 15, 0, 0, 220, 0),
('握力训练', '肘腕', '软球', 1, '增强手部握力，改善日常抓握能力。', '1. 手握软球或握力器；\n2. 缓慢用力握紧，保持3秒；\n3. 完全放松3秒；\n4. 重复。', '· 手腕保持中立位；\n· 不憋气；\n· 腱鞘炎急性期减少次数。', 3, 15, 0, 0, 230, 0),
('胸椎旋转', '颈腰椎', '椅子', 1, '改善胸椎旋转活动度，缓解上背僵硬。', '1. 坐位，双手抱于胸前；\n2. 骨盆稳定，缓慢向一侧旋转上身；\n3. 到末端停留2秒；\n4. 回到中间换侧。', '· 旋转来自胸椎而不是腰部；\n· 不追求角度；\n· 出现腰痛时减小幅度。', 2, 10, 0, 0, 310, 0),
('仰卧抱膝', '颈腰椎', '瑜伽垫', 1, '温和牵引腰背，缓解腰部紧张。', '1. 仰卧屈膝，双脚平放；\n2. 双手抱住一侧膝盖拉向胸口；\n3. 保持20-30秒；\n4. 换另一侧。', '· 腰部有舒适牵拉感即可；\n· 髋关节置换术后遵医嘱；\n· 出现放射痛加重立即停止。', 2, 10, 0, 0, 320, 0),
('弹力带扩胸', '胸背', '弹力带', 1, '打开胸廓、强化上背，改善含胸姿势。', '1. 双手握弹力带于胸前；\n2. 手臂伸直向两侧打开；\n3. 肩胛骨向后夹紧；\n4. 缓慢还原。', '· 不耸肩；\n· 肩前侧不适时减小幅度；\n· 保持自然呼吸。', 3, 12, 0, 0, 410, 0),
('俯身弹力带划船', '胸背', '弹力带', 2, '强化中背与肩胛回缩肌群，改善背部无力。', '1. 弹力带踩于脚下，屈髋俯身；\n2. 背部挺直，双手握带；\n3. 屈肘将带拉向腹部；\n4. 缓慢还原。', '· 腰部不适时改坐姿划船；\n· 不弓背；\n· 肘部贴近身体。', 3, 12, 0, 0, 420, 0),
('侧卧髋外展', '髋部', '自重', 1, '强化臀中肌，改善髋部稳定与步态。', '1. 侧卧，下侧腿屈膝稳定；\n2. 上侧腿伸直缓慢抬起；\n3. 到30-40度停留2秒；\n4. 缓慢放下。', '· 骨盆不后倒；\n· 脚尖朝前不朝上；\n· 髋外侧酸胀属正常。', 3, 12, 0, 0, 610, 0),
('俯卧髋后伸', '髋部', '自重', 1, '激活臀大肌，改善髋伸展能力。', '1. 俯卧，额头垫手；\n2. 一侧腿伸直缓慢抬离床面；\n3. 保持2秒后放下；\n4. 换另一侧。', '· 不用腰部代偿；\n· 幅度小而可控；\n· 腰椎不适时停止。', 3, 10, 0, 0, 620, 0),
('单腿臀桥', '髋部', '瑜伽垫', 2, '单侧强化臀大肌与躯干稳定，进阶训练。', '1. 仰卧屈膝，一侧腿伸直抬起；\n2. 支撑腿发力将髋抬起；\n3. 保持2秒后缓慢落下；\n4. 换侧。', '· 骨盆保持水平；\n· 不用腰部顶起；\n· 先掌握双腿臀桥再进阶。', 3, 10, 0, 0, 630, 0),
('终末伸膝训练', '膝部', '弹力带', 1, '强化股内侧肌，改善膝关节终末伸展控制。', '1. 坐位，膝下垫毛巾卷；\n2. 弹力带套于膝后；\n3. 用力伸直膝盖至完全伸直；\n4. 保持3秒后缓慢放下。', '· 只做最后15-20度伸展；\n· 不甩腿；\n· 术后遵医嘱控制角度。', 3, 12, 0, 0, 710, 0),
('离心下台阶', '膝部', '台阶', 2, '离心控制股四头肌，改善下楼梯稳定性。', '1. 站在10-15cm台阶上；\n2. 患腿支撑，健腿缓慢向下点地；\n3. 用3秒控制下放；\n4. 再站回台阶。', '· 全程扶扶手；\n· 膝盖与脚尖同向；\n· 疼痛超过3分时降低台阶高度。', 3, 10, 0, 0, 720, 0),
('弹力带踝背屈', '踝足', '弹力带', 1, '强化胫前肌，改善足下垂与踝背屈力量。', '1. 坐位伸腿，弹力带固定于前脚掌；\n2. 另一端固定在前方；\n3. 缓慢勾脚背向身体方向；\n4. 控制还原。', '· 踝关节术后遵医嘱；\n· 不引起踝前疼痛；\n· 动作缓慢。', 3, 15, 0, 0, 810, 0),
('足趾抓毛巾', '踝足', '毛巾', 1, '训练足底小肌群，改善足弓与本体感觉。', '1. 坐位，脚下放一条毛巾；\n2. 用脚趾反复抓取毛巾；\n3. 抓满后放松；\n4. 重复。', '· 足底筋膜炎急性期减少；\n· 动作轻柔；\n· 可赤足进行。', 3, 15, 0, 0, 820, 0),
('踝关节字母操', '踝足', '自重', 1, '用踝关节在空中写字母，全面活动踝关节。', '1. 坐位抬起一侧脚；\n2. 用脚尖在空中写A-Z；\n3. 幅度由小到大；\n4. 换另一侧。', '· 动作缓慢连贯；\n· 不引起明显疼痛；\n· 踝不稳者扶稳。', 2, 1, 0, 0, 830, 0),
('闭眼站立', '平衡步态', '自重', 2, '减少视觉输入，强化本体感觉与静态平衡。', '1. 扶稳桌边，双脚与髋同宽；\n2. 站稳后缓慢闭眼；\n3. 保持10-20秒；\n4. 睁眼休息后重复。', '· 身边必须有支撑物或陪护；\n· 头晕立即睁眼坐下；\n· 从睁眼进阶到闭眼。', 3, 15, 0, 0, 910, 0),
('侧向行走', '平衡步态', '弹力带', 2, '训练侧向步态与髋部稳定，改善行走控制。', '1. 弹力带套于膝上方；\n2. 微屈膝，侧向迈步；\n3. 保持弹力带张力；\n4. 往返行走。', '· 膝盖不内扣；\n· 步子不宜过大；\n· 靠近墙面练习。', 3, 12, 0, 0, 920, 0),
('原地踏步', '心肺全身', '自重', 1, '低冲击有氧，适合早期恢复心肺耐力。', '1. 站立扶稳，原地缓慢踏步；\n2. 逐渐加快至略喘；\n3. 保持2-5分钟；\n4. 慢走放松。', '· 能说话为适宜强度；\n· 胸闷气促立即停止；\n· 平衡差者扶稳。', 1, 3, 0, 0, 1010, 0);

UPDATE rehab_exercises SET is_member_only=0 WHERE is_custom=0 AND category IN ('肩部','肘腕','颈腰椎','胸背','核心躯干','髋部','膝部','踝足','平衡步态','心肺全身');
