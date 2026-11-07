-- Docker 专用：init.sql 只创建了 'fitness_user'@'localhost'，
-- 应用容器经 Docker 网络连接，需要放开为 '%' 才能访问
CREATE USER IF NOT EXISTS 'fitness_user'@'%' IDENTIFIED BY 'CHANGE_ME_DB_PASSWORD';
GRANT ALL PRIVILEGES ON fitness_tracker.* TO 'fitness_user'@'%';
FLUSH PRIVILEGES;
