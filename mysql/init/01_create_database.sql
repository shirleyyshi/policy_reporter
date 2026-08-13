# Policy_Reporter 数据库初始化
# Docker MySQL 容器首次启动时自动执行
CREATE DATABASE IF NOT EXISTS policy_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
