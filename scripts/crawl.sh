#!/bin/bash
# Ubuntu cron 定时爬虫脚本（每天 7:00 跑一次）
# 用法：
#   1. chmod +x scripts/crawl.sh
#   2. crontab -e 加一行：0 7 * * * /opt/policy_reporter/scripts/crawl.sh >> /var/log/crawl.log 2>&1

set -e

# 项目路径（部署时改成实际路径）
PROJECT_DIR="/opt/policy_reporter"
cd "$PROJECT_DIR/backend"

# Python 环境（Docker 部署则改为 docker compose exec backend python manage.py ...）
PYTHON_BIN="${PYTHON_BIN:-python}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始爬取..."
$PYTHON_BIN manage.py crawl_policies --all

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 重建 RAG 索引..."
$PYTHON_BIN manage.py build_index

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成"
