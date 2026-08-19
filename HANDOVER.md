# Policy_Reporter 项目交接文档

> 创建日期：2026-08-16
> 当前状态：crawl_config 已配齐 8 站点（中央 4 + 广州 4），待服务器 dry-run 调 XPath + 清空重爬

---

## 1. 项目总览

财税政策日报 Agent — 基于 ReAct 范式的自主 Agent，输入日期自动编排工具链生成政策日报 Word 文档。

| 层级 | 技术栈 |
|------|--------|
| LLM | DeepSeek-chat |
| Agent | 自研 ReAct 框架（Actuator / Critic / Replanner / Terminator） |
| 后端 | Django 5.2 + DRF + SimpleJWT + gunicorn |
| 数据 | MySQL 8.0 + ChromaDB（向量检索） |
| 前端 | Vue 3 + Element Plus + Vite |
| 部署 | Docker Compose + Nginx |
| 测试 | pytest + pytest-cov（覆盖率 82%，179 个测试） |
| CI | GitHub Actions（backend-test + frontend-build 双 job） |

**部署地址**：新加坡云服务器（http://IP，无域名无 HTTPS）
**Git remotes**：origin=Gitee(shirleyyyshi), github=GitHub(shirleyyshi) — 每次提交需推两边

---

## 2. 业务分类方案（最终版）

4 大类，中央地方对称，参考国务院办公厅政府信息公开目录：

| 大类 | 中央站点 | 地方站点（广州） |
|------|---------|-----------------|
| **财政** | 财政部 | 广州市财政局 |
| **税务** | 国家税务总局 | 广东省税务局 |
| **金融** | 中国人民银行 | 广州市地方金融局 |
| **商贸** | 商务部 | 广州市商务局 |

**分类字段**：`CentralPolicy.type` 和 `LocalPolicy.type`（DB 字段，Agent 用 `classify_policy` 工具读 `type` 做确定性分类，不调 LLM）

---

## 3. 当前完成状态

### 已完成
- Phase A：Agent 能力补齐（Observation 三元组 + AgentRun 持久化 + RAG episodic memory）
- Phase B：配置就绪（跳过本地验证，直接服务器验证）
- Phase C：测试 82% 覆盖率 + GitHub Actions CI 双 job 全绿
- Phase D：服务器部署 + D6 生产加固（admin IP 白名单 + fail2ban + Docker 日志轮转 + DB 自动备份）
- 数据提取 bug 修复（导出标题日期/摘要条数/选择交集）
- save_state datetime 序列化 bug 修复
- episodic memory 序列化 bug 修复
- crawl_config 配齐 8 站点（中央 4 + 广州 4），分类统一为财政/税务/金融/商贸

### 未完成（按优先级排序）

#### P0：爬虫 dry-run + 调 XPath + 清空重爬（当前阻塞项）
crawl_config 已配 8 站点，但详情页 XPath（title/content/date）是基于政府站点常见结构的推断，**需要逐站 dry-run 验证后调**。

**服务器执行命令**：
```bash
cd /opt/policy_reporter
git pull origin main
docker compose exec backend python manage.py migrate

# 清空旧政策数据
docker compose exec backend python manage.py shell -c "
from report.models import CentralPolicy, LocalPolicy
CentralPolicy.objects.all().delete()
LocalPolicy.objects.all().delete()
print('已清空')
"

# 先 dry-run 验证 XPath
docker compose exec backend python manage.py crawl_policies --all --dry-run

# XPath 调好后正式爬取
docker compose exec backend python manage.py crawl_policies --all

# 重建 RAG 索引
docker compose exec backend python manage.py build_index
```

**dry-run 输出怎么看**：
- "找到 X 个链接" — X=0 说明 list_link_xpath 不对，需 curl 看 HTML 调
- "content=0字" — 说明 detail_content_xpath 不对，需 curl 看详情页 HTML 调
- "date=None" — 说明 detail_date_xpath 不对

**调 XPath 方法**：curl 拿 HTML → 看 DOM 结构 → 改 crawl_config.json 对应字段

#### P1：前端分类下拉框更新
前端 `CentralEditor.vue` / `LocalEditor.vue` 的分类下拉框可能还是旧值（海关/商务/税务），需更新为财政/税务/金融/商贸。

#### P2：Phase E 简历素材
1 页项目卡片 + 3 分钟话术 + demo 视频 + 架构图（README 已有 mermaid 图，可复用）

---

## 4. crawl_config 配置说明

文件位置：[backend/apps/report/management/commands/crawl_config.json](file:///d:/work/project/Policy_Reporter/backend/apps/report/management/commands/crawl_config.json)

8 站点配置（中央 4 + 广州地方 4）：

| 站点 | site_id | policy_type | default_category | list_url |
|------|---------|------------|-----------------|----------|
| 财政部 | mof | central | 财政 | mof.gov.cn/zhengwuxinxi/zhengcefabu/ |
| 国家税务总局 | chinatax | central | 税务 | chinatax.gov.cn/n810341/n810755/ |
| 中国人民银行 | pbc | central | 金融 | pbc.gov.cn/zhengcehuobisi/125133/125477/ |
| 商务部 | mofcom | central | 商贸 | mofcom.gov.cn/zcfb/zc/ |
| 广州市财政局 | guangzhou_czj | local | 财政 | czj.gz.gov.cn/zlshj/tzgg/ |
| 广东省税务局 | guangdong_tax | local | 税务 | guangdong.chinatax.gov.cn/site/guangdong/tax/notice/ |
| 广州市金融局 | guangzhou_jr | local | 金融 | jrjgj.gz.gov.cn/zcgh/ |
| 广州市商务局 | guangzhou_sw | local | 商贸 | sw.gz.gov.cn/xxgk/tzgg/tz/ |

**待调 XPath 字段**（dry-run 后可能需要改）：
- `list_link_xpath` — 列表页链接提取（每站可能不同）
- `detail_content_xpath` — 详情页正文提取（每站可能不同）
- `detail_date_xpath` — 详情页发布日期提取

---

## 5. 关键文件位置

| 模块 | 文件路径 |
|------|---------|
| Agent 核心 | backend/apps/agent/core.py |
| Agent 工具 | backend/apps/agent/tools.py |
| Agent prompts | backend/apps/agent/prompts.py |
| RAG | backend/apps/agent/rag.py |
| Agent views | backend/apps/agent/views.py |
| Agent 模型 | backend/apps/agent/models.py |
| 评估框架 | backend/apps/agent/eval/ |
| 政策模型 | backend/apps/report/models.py |
| 政策视图 | backend/apps/report/views.py |
| 爬虫 | backend/apps/report/management/commands/crawl_policies.py |
| 爬虫配置 | backend/apps/report/management/commands/crawl_config.json |
| 数据库迁移 | backend/apps/report/migrations/0003_localpolicy_type.py |
| Django 设置 | backend/config/settings.py |
| 中间件 | backend/config/middleware.py |
| Docker | docker-compose.yml |
| CI | .github/workflows/test.yml |
| 前端 | frontend/src/views/ |

---

## 6. 硬约束（从 project_memory 提取）

- 爬取的政策数据必须含 crawled_at 字段
- 标题过滤只保留 通知/公告/意见/办法/规定/方案/条例/细则 类型
- source_url 去重
- LocalPolicy 必须有 crawled_at 字段
- LocalPolicy 必须有 type 字段（业务分类）
- Agent 从 DB 读数据，不直接 web 抓取
- Agent run 状态序列化 datetime 为 ISO 字符串（_serialize_state 用 json.dumps default=str）
- git 提交必须同时推 Gitee + GitHub
- GitHub 用户名 shirleyyshi（2个y），Gitee 用户名 shirleyyyshi（3个y）

---

## 7. 服务器关键信息

- 路径：/opt/policy_reporter
- Docker 三容器：policy_backend / policy_db / policy_frontend
- cron 定时爬虫：每天 7:00（scripts/crawl.sh）
- DB 备份：每天 3:00（gzip 到 /opt/backups/），4:00 清理 7 天前备份
- admin IP 白名单：ADMIN_ALLOWED_IPS 已配在 .env
- 代码更新流程：`git pull origin main` → 如改了模型需 `migrate` → 如改了代码需 `docker compose up -d --build backend`

---

## 8. 下一步接手者必读

1. 先跑 dry-run 看哪些站 XPath 不对
2. 逐站调 XPath（curl HTML → 改 crawl_config → 再 dry-run）
3. XPath 全过后清空 DB + 正式爬取 + 重建索引
4. 前端分类下拉框更新为财政/税务/金融/商贸
5. 跑一次 agent run 验日报 docx 分类是否正确
6. 做 Phase E 简历素材
