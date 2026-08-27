#!/bin/bash
# 警告：此脚本会修改 .env、安装并重启系统服务、覆盖 Docker daemon 配置、
# 重启 Docker、创建备份脚本并写入 cron。仅在审阅全部内容并确认目标服务器后执行；
# 不要在本地开发机、共享服务器或未经授权的环境中直接运行。
#
# D6 服务器加固脚本（一次性执行）
# 在服务器上跑：bash scripts/server_harden.sh
# 完成后删除：rm scripts/server_harden.sh
#
# 四项加固：
#   1. admin IP 白名单（写 .env + 重建 backend 容器）
#   2. fail2ban 防 SSH 暴力破解
#   3. docker log rotation（每个容器日志上限 30MB）
#   4. DB 自动备份 cron（每天 3:00 备份 + 4:00 清理 7 天前）

set -e

# 颜色标记
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; }
step() { echo -e "\n${YELLOW}=== $1 ===${NC}"; }

# 定位项目目录（默认 /opt/policy_reporter，可传参数覆盖）
PROJECT_DIR="${1:-/opt/policy_reporter}"
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    err "未找到 $PROJECT_DIR/docker-compose.yml"
    echo "用法：bash scripts/server_harden.sh [项目目录]"
    echo "如果项目不在 /opt/policy_reporter，请传入实际路径"
    exit 1
fi
cd "$PROJECT_DIR"

# ============ 1/4 admin IP 白名单 ============
step "1/4 配置 admin IP 白名单"

# 从 SSH 连接提取客户端 IP（你的家庭/办公公网 IP）
CLIENT_IP=$(echo "$SSH_CLIENT" | awk '{print $1}')
if [ -z "$CLIENT_IP" ]; then
    warn "无法从 SSH_CLIENT 获取来源 IP"
    read -p "请输入你的公网 IP（如 1.2.3.4）: " ADMIN_IP
else
    read -p "检测到 SSH 来源 IP: $CLIENT_IP，用作 admin 白名单？[Y/n] " confirm
    confirm=${confirm:-Y}
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        ADMIN_IP="$CLIENT_IP"
    else
        read -p "请输入 ADMIN_ALLOWED_IPS: " ADMIN_IP
    fi
fi

if [ -z "$ADMIN_IP" ]; then
    err "ADMIN_IP 为空，跳过白名单配置"
else
    if grep -q "^ADMIN_ALLOWED_IPS=" .env 2>/dev/null; then
        sed -i "s|^ADMIN_ALLOWED_IPS=.*|ADMIN_ALLOWED_IPS=$ADMIN_IP|" .env
    else
        echo "ADMIN_ALLOWED_IPS=$ADMIN_IP" >> .env
    fi
    ok ".env 已写入 ADMIN_ALLOWED_IPS=$ADMIN_IP"

    echo "重建 backend 容器（加载中间件，约 30-60 秒）..."
    docker compose up -d --build backend
    ok "backend 容器已重启，admin 白名单生效"
fi

# ============ 2/4 fail2ban ============
step "2/4 安装 fail2ban 防 SSH 暴力破解"

if command -v fail2ban-client &>/dev/null; then
    ok "fail2ban 已安装，跳过安装步骤"
else
    echo "安装 fail2ban..."
    sudo apt update -y
    sudo apt install -y fail2ban
    ok "fail2ban 安装完成"
fi

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
ok "fail2ban 已启用并重启"

echo "--- fail2ban 状态 ---"
sudo fail2ban-client status || warn "fail2ban 刚启动，sshd jail 可能需要几秒生效"

# ============ 3/4 docker log rotation ============
step "3/4 配置 docker log rotation"

DAEMON_JSON="/etc/docker/daemon.json"
if [ -f "$DAEMON_JSON" ]; then
    warn "$DAEMON_JSON 已存在，备份到 ${DAEMON_JSON}.bak"
    sudo cp "$DAEMON_JSON" "${DAEMON_JSON}.bak"
fi

sudo tee "$DAEMON_JSON" > /dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
ok "$DAEMON_JSON 已写入（max-size 10m, max-file 3）"

echo "重启 docker（容器会中断几秒后自动恢复）..."
sudo systemctl restart docker
ok "docker 已重启"

# 等待容器恢复
echo "等待容器恢复..."
sleep 5
docker compose up -d
ok "所有容器已启动"

echo "--- 容器状态 ---"
docker compose ps

# ============ 4/4 DB 备份 cron ============
step "4/4 配置数据库自动备份 cron"

sudo mkdir -p /opt/backups
sudo chown "$USER":"$USER" /opt/backups
ok "备份目录 /opt/backups 已创建"

# 从 .env 读 DB_ROOT_PASSWORD
DB_PASS=$(grep "^DB_ROOT_PASSWORD=" .env | cut -d'=' -f2-)
if [ -z "$DB_PASS" ]; then
    err ".env 中未找到 DB_ROOT_PASSWORD，请手动配置备份 cron"
    exit 1
fi

# 写备份脚本（避免密码暴露在 crontab 里，crontab 全系统可见）
BACKUP_SCRIPT="/opt/backups/backup_db.sh"
cat > "$BACKUP_SCRIPT" <<EOF
#!/bin/bash
cd "$PROJECT_DIR"
docker compose exec -T db mysqldump -u root -p"$DB_PASS" policy_db | gzip > /opt/backups/policy_db_\$(date +%Y%m%d).sql.gz
EOF
chmod 700 "$BACKUP_SCRIPT"
ok "备份脚本 $BACKUP_SCRIPT 已创建（权限 700）"

# 加 cron：先清掉旧的同名条目避免重复，再加新的
( crontab -l 2>/dev/null | grep -v "backup_db.sh" | grep -v "find /opt/backups"; \
  echo "0 3 * * * $BACKUP_SCRIPT >> /opt/backups/backup.log 2>&1"; \
  echo "0 4 * * * find /opt/backups -name '*.sql.gz' -mtime +7 -delete" ) | crontab -
ok "cron 已配置：每天 3:00 备份，4:00 清理 7 天前备份"

# ============ 最终验证 ============
step "验证汇总"

echo "--- admin 白名单 ---"
grep "ADMIN_ALLOWED_IPS" .env || warn "未配置（admin 公网可访问）"
echo ""
echo "--- fail2ban ---"
sudo systemctl is-active fail2ban
echo ""
echo "--- docker daemon.json ---"
cat "$DAEMON_JSON"
echo ""
echo "--- cron 任务 ---"
crontab -l | grep -E "backup_db|find /opt/backups"
echo ""
echo "--- 容器状态 ---"
docker compose ps

echo ""
ok "=========================================="
ok "D6 生产加固全部完成"
ok "=========================================="
echo ""
echo "验证清单（可手动检查）："
echo "  1. 换个网络（如手机热点）访问 http://$(hostname -I | awk '{print $1}')/admin/"
echo "     应返回 'Access denied.'（403）"
echo "  2. sudo fail2ban-client status sshd"
echo "     看 Currently failed 和 Total banned 数量"
echo "  3. 明天 3:00 后 ls /opt/backups/"
echo "     应有 policy_db_YYYYMMDD.sql.gz 文件"
echo ""
echo "手动测试备份（立即跑一次）："
echo "  bash /opt/backups/backup_db.sh && ls -lh /opt/backups/"
echo ""
echo "清除本脚本（执行完即可删）："
echo "  rm $PROJECT_DIR/scripts/server_harden.sh"
