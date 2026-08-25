# 运行说明书（Runbook）

> 面向操作者：从零部署、日常运维、故障排查。所有服务器命令在部署目录（如 `/opt/policy_reporter`）执行；本地开发命令在仓库根目录执行。
> 更深的事实与边界见 `HANDOVER.md`；架构说明见 `ARCHITECTURE.md`。

---

## 1. 环境要求

| 组件 | 要求 |
|------|------|
| 服务器 | Linux（Ubuntu 22.04 验证过），2G 内存起，可访问外网（采集目标站 + DeepSeek API） |
| Docker | Docker Engine 24+ 与 docker compose v2 |
| 密钥 | DeepSeek API Key（Agent 摘要必需，平台充值获取） |
| 本地开发（可选） | Python 3.11、Node 18+、MySQL 8（或直接用 Docker 起数据库） |

---

## 2. 首次部署（服务器，约 10 分钟）

```bash
# 1. 拉代码
git clone https://gitee.com/shirleyyyshi/policy_reporter.git /opt/policy_reporter
cd /opt/policy_reporter

# 2. 配置密钥（参照 .env.example 逐项填写）
cp .env.example .env
vim .env
#   必填：SECRET_KEY（随机长串）、DB_ROOT_PASSWORD、DEEPSEEK_API_KEY
#   可选：ADMIN_ALLOWED_IPS（留空=不限制 admin 访问 IP）

# 3. 启动（首次会构建镜像，几分钟）
docker compose up -d

# 4. 确认三个容器状态：db 与 backend 应为 healthy，frontend 为 running
docker compose ps

# 5. 验证服务
curl http://localhost/api/health/          # {"status":"ok","db":true}
ss -tlnp | grep -E '3306|8000'             # 应只见 127.0.0.1 绑定（安全）

# 6. 创建管理员账号（容器内执行；普通用户可在登录页点击“去注册”自行创建）
docker compose exec backend python manage.py createsuperuser

# 查看当前用户（不会显示密码；含 ID、用户名、邮箱、是否管理员/启用、注册时间）
docker compose exec backend python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); [print(u.id, u.username, u.email or '-', 'staff='+str(u.is_staff), 'superuser='+str(u.is_superuser), 'active='+str(u.is_active), u.date_joined.isoformat()) for u in U.objects.order_by('id')]"

# 7. 首次采集数据（约 15-20 分钟，含限速）
docker compose exec backend python manage.py crawl_policies --all -u

# 8. 重建检索索引（采集后必做；日常 cron 脚本已自动包含）
docker compose exec backend python manage.py build_index

# 9. 浏览器访问 http://<服务器IP>/ 登录验证
```

> 采集地区为广东/广州 + 中央部委。这是部署地（新加坡）网络可达性的取舍，采集源纯配置驱动（`backend/crawl_config.json`），换地区只改配置不改代码。

---

## 3. 日常运维

### 3.1 每日自动采集（cron）

```bash
# 注册（一次性）
crontab -e
# 加入一行：
# 0 8 * * * /opt/policy_reporter/scripts/crawl.sh >> /var/log/crawl.log 2>&1

# 次日起检查日志
tail -30 /var/log/crawl.log
# 正常应见：各站点统计（新增 N 条 / 跳过 N 条）→ 索引重建 → 完成
```

脚本内容 = 采集 + 自动重建索引。全程约 15-20 分钟属正常（礼貌限速 + 失败重试的设计成本），**期间长时间无输出不是卡死**。

### 3.2 手动采集与调试

```bash
# 全量（自动去重，重复跑安全）
docker compose exec backend python manage.py crawl_policies --all -u

# 单站点试跑（不写库，验证站点配置是否还活着）
docker compose exec backend python manage.py crawl_policies --site mof --dry-run
```

### 3.3 更新版本

```bash
cd /opt/policy_reporter
git pull origin main

# 按改动范围选择：
docker compose up -d --build backend          # 改了后端代码
docker compose up -d --build frontend         # 改了前端代码
docker compose up -d --build backend frontend # 都改了
docker compose up -d --force-recreate frontend # 只改了 nginx.conf（bind mount 陷阱，必须重建）

# 数据库迁移由 entrypoint 自动执行；验证：
docker compose exec backend pytest --tb=short -q   # 容器内需已装 dev 依赖
curl http://localhost/api/health/
```

### 3.4 备份

```bash
# 数据库导出（建议每周，产物不要提交到 git）
docker compose exec db mysqldump -uroot -p"$DB_ROOT_PASSWORD" policy_db > backup_$(date +%F).sql

# Word 产物在 backend_media 卷中，重要的话定期 tar 打包
```

---

## 4. 验证清单（部署后自检）

| 检查项 | 命令/操作 | 预期 |
|--------|----------|------|
| 健康 | `curl http://localhost/api/health/` | `{"status":"ok","db":true}` |
| 容器 | `docker compose ps` | db/backend healthy，frontend running |
| 端口 | `ss -tlnp \| grep -E '3306\|8000'` | 仅 127.0.0.1 |
| 登录 | 浏览器访问 `/` | 登录页正常，登录后进入主页 |
| 政策列表 | 主页选日期 | 中央/地方数量正常 |
| 手动导出 | 勾选政策→导出 | 下载 docx |
| Agent | 启动一次 Agent | 步骤进度推进，可能弹人在回路问题，最终可下载 docx |
| admin 样式 | 访问 `/admin/` | 有 CSS 样式（非纯文本） |
| media 封闭 | `curl -o /dev/null -w "%{http_code}" http://localhost/media/` | 404 |

---

## 5. 故障排查

| 现象 | 排查 | 处理 |
|------|------|------|
| health 返回 503/degraded | `docker compose ps` 看 db 是否 healthy | db 未起：`docker compose logs db`；多数是 .env 密码错或磁盘满 |
| 前端打不开/白屏 | `docker compose logs frontend --tail 50` | nginx.conf 改过后必须 `--force-recreate frontend` |
| Agent 一直 running 不动 | `docker compose logs backend --tail 100` | 看 DeepSeek 调用报错（余额/网络）；run 记录会标 failed 不会僵死 |
| 采集某站点 0 条 | `--dry-run` 单测该站点 | 站点改版需更新 `crawl_config.json` 的 XPath |
| 采集卡住很久 | 属正常（限速设计）；另开终端 `docker compose top backend` 确认进程 | >30 分钟无站点级输出再排查 |
| 401 循环跳登录 | 浏览器 localStorage 查 refresh_token | 7 天长期票过期，重新登录即可 |
| 下载的 docx 打不开（Word 报错） | 两个历史根因：① 文件 ~1KB 是 HTML（前端 URL 拼接错误，SPA 兜底返回 index.html）② 文件几十 KB 但 Word 拒开（含手动录入政策，空 source_url 生成了 Target='' 非法外链关系） | 均已修复（提交 5719bef / 本次）。历史坏文件无效：服务器上已生成的 docx 本身是坏的，需重新生成（手动导出重导；Agent 重跑该日期） |
| 迁移报错 | `docker compose exec backend python manage.py migrate` 看输出 | 多为前后版本跳太多，按报错的 migration 号处理 |
| 容器内存不足 OOM | `docker stats` | 采集+Agent 高峰需 ~1.5G；swap 或升配 |

---

## 6. 测试

```bash
# 本地（仓库 backend/ 下，venv 激活）
pytest                       # 全量 218 个，覆盖率门槛 80%

# 容器内（需镜像含 dev 依赖）
docker compose exec backend pytest --tb=short -q

# 前端构建验证
cd frontend && npm run build
```

---

## 7. 常用入口速查

| 入口 | 位置 |
|------|------|
| 前端页面 | `http://<IP>/` |
| Django admin | `http://<IP>/admin/` |
| 健康检查 | `http://<IP>/api/health/` |
| 采集配置 | `backend/crawl_config.json` |
| 环境变量 | 仓库根 `.env`（不入库） |
| 采集日志 | `/var/log/crawl.log`（cron 模式） |
| 容器日志 | `docker compose logs -f backend` |
