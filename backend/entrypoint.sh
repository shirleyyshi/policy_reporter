#!/bin/sh
# 后端容器启动脚本：等 DB → migrate → collectstatic → gunicorn
set -e

echo "[entrypoint] 等待 MySQL 就绪..."
# 最多等 60 秒
for i in $(seq 1 60); do
    python -c "
import os, sys
import MySQLdb
try:
    MySQLdb.connect(
        host=os.environ.get('DB_HOST', 'db'),
        port=int(os.environ.get('DB_PORT', 3306)),
        user=os.environ.get('DB_USER', 'root'),
        passwd=os.environ.get('DB_PASSWORD', os.environ.get('DB_ROOT_PASSWORD', '')),
        db=os.environ.get('DB_NAME', 'policy_db'),
    )
    sys.exit(0)
except Exception:
    sys.exit(1)
" && break
    echo "  MySQL 未就绪，5 秒后重试 ($i/60)..."
    sleep 5
done

echo "[entrypoint] MySQL 已就绪，开始 migrate..."
python manage.py migrate --noinput

echo "[entrypoint] 收集静态文件..."
python manage.py collectstatic --noinput

# 首次启动构建 RAG 索引（幂等，已存在则跳过）
echo "[entrypoint] 构建 RAG 索引..."
python manage.py build_index || echo "  [警告] build_index 失败，跳过（首次启动无数据时正常）"

echo "[entrypoint] 启动 gunicorn..."
exec gunicorn config.wsgi:application \
    -b 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
