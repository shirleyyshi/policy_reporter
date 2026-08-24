#!/bin/bash
# Ubuntu cron 定时爬虫脚本（每天 8:00 跑一次，采集后自动重建 RAG 索引）
# 用法：
#   1. chmod +x scripts/crawl.sh
#   2. crontab -e 加一行：0 8 * * * /opt/policy_reporter/scripts/crawl.sh >> /var/log/crawl.log 2>&1
# Docker 部署自动走 docker compose exec，本地裸机开发自动走宿主机 python

set -e

PROJECT_DIR="/opt/policy_reporter"
cd "$PROJECT_DIR"

if [ -f docker-compose.yml ] && docker compose ps --status running 2>/dev/null | grep -q backend; then
    RUN="docker compose exec -T backend python"
else
    cd "$PROJECT_DIR/backend"
    RUN="${PYTHON_BIN:-python}"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始爬取（执行方式: $RUN）..."
$RUN manage.py crawl_policies --all

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 重建 RAG 索引..."
$RUN manage.py build_index

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成"
