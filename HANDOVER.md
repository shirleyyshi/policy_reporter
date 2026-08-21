# Policy_Reporter 项目交接文档

> 创建日期：2026-08-16
> 当前状态（2026-08-21）：爬虫全链路已通并完成正式爬取 — **166 条真实政策数据（中央 94 + 地方 72），财政/税务/金融/商贸 4 类中央地方全对称，空正文 0，RAG 索引已重建**。cron 定时任务**未注册**（用户要求需要时再开，见第 8 节）。剩余待办仅 Phase E 简历素材。

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
| **税务** | 广东省税务局"总局文件"栏目转载（总局官网 JS 渲染无法爬） | 广东省税务局（粤文件） |
| **金融** | 国家外汇管理局（央行 403 反爬无法访问） | 广州市地方金融局 |
| **商贸** | 商务部 | 广州市商务局 |

> 2026-08-21 起中央税务/金融用上述替代源：总局官网 chinatax.gov.cn 列表页为 JS 动态渲染（requests 拿不到链接），央行 pbc.gov.cn 对新加坡服务器返回 403。广东税务 zjfg 栏目完整转载总局原文，按标题是否含"广东"区分中央/地方入库。

**分类字段**：`CentralPolicy.type` 和 `LocalPolicy.type`（DB 字段，Agent 用 `classify_policy` 工具读 `type` 做确定性分类，不调 LLM）

---

## 3. 当前完成状态

### 已完成
- Phase A：Agent 能力补齐（Observation 三元组 + AgentRun 持久化 + RAG episodic memory）
- Phase B：配置就绪
- Phase C：测试 82% 覆盖率 + GitHub Actions CI 双 job 全绿
- Phase D：服务器部署 + D6 生产加固（admin IP 白名单 + fail2ban + Docker 日志轮转 + DB 自动备份）
- 数据提取 bug 修复（导出标题日期/摘要条数/选择交集）
- save_state datetime 序列化 bug 修复
- episodic memory 序列化 bug 修复
- crawl_config 配齐 8 站点（中央 4 + 广州 4），分类统一为财政/税务/金融/商贸
- 2026-08-21 爬虫质量修复：8 站 URL 逐一 WebFetch 实测修正（商务部/广州财政/广东税务 3 个旧 URL 已失效全部更换）；新增 safe（中央金融）+ chinatax_central（中央税务）两个替代源；爬虫逻辑增强（翻页偏移 page_offset、标题取首个非空、正文取最长节点、日期页面文本兜底、完整 Chrome UA）
- 2026-08-21 二轮实测修复（服务器 dry-run 暴露）：商务部列表/详情页均为 JS 渲染 → 列表改走 jpaas JSON API（list_api 配置，翻页参数 paramJson 已实测）；广州财政（zw-title/zoomcon/span.time）、广州金融（info_title/info_cont/info_time）、广东税务（UCAPTITLE/zoomcon/lawfwrq）详情页 XPath 按真实 DOM 修正；财政部子域名网关随机 502 → retries=3 递增退避 + delay 3s
- 2026-08-21 **正式爬取完成**：166 条入库（中央 94：财政24/税务8/金融33/商贸29；地方 72：财政20/税务1/金融22/商贸29），空正文 0，RAG 索引已重建（166 条）。爬虫阶段收尾
- 前端 CentralEditor.vue 分类下拉框已更新为财政/税务/金融/商贸
- 代码鲁棒性审查 + 修复（详见第 9 节）

### 未完成（按优先级排序）

#### P1：Phase E 简历素材
1 页项目卡片 + 3 分钟话术 + demo 视频 + 架构图（README 已有 mermaid 图，可复用）

### 已知遗留（不阻塞，知悉即可）
- **财政部约 10 条 502**：mof.gov.cn 子域名网关从新加坡访问随机拒绝（同 URL 时好时坏）。已配 retries=3 递增退避；因按 source_url 去重，**每次重跑会自动重试失败项，多跑几次攒齐**，无需特殊处理
- **商务部走 jpaas JSON API**：列表由前端 JS 渲染，requests 拿不到，故直调其内部接口（list_api 配置）。若商务部改版导致 API 参数失效，症状是"找到 0 个链接"——届时 curl 列表页找新 API 地址和 webId/pageId 参数
- **粤文件仅 1 条**：guangdong_tax 站点"粤文件"栏目本身更新少，非爬虫问题

---

## 4. crawl_config 配置说明

文件位置：[backend/apps/report/management/commands/crawl_config.json](file:///d:/work/project/Policy_Reporter/backend/apps/report/management/commands/crawl_config.json)

8 站点配置（中央 4 + 广州地方 4）：

| 站点 | site_id | policy_type | default_category | list_url |
|------|---------|------------|-----------------|----------|
| 财政部 | mof | central | 财政 | mof.gov.cn/zhengwuxinxi/zhengcefabu/ |
| 中央税务（广东转载总局文件） | chinatax_central | central | 税务 | guangdong.chinatax.gov.cn/gdsw/zcwj/zcwj.shtml |
| 国家外汇管理局 | safe | central | 金融 | safe.gov.cn/safe/zcfg/index.html |
| 商务部 | mofcom | central | 商贸 | mofcom.gov.cn/zcfb/zc/index.html |
| 广州市财政局 | guangzhou_czj | local | 财政 | czj.gz.gov.cn/tzgg/index.html |
| 广东省税务局（粤文件） | guangdong_tax | local | 税务 | guangdong.chinatax.gov.cn/gdsw/zcwj/zcwj.shtml |
| 广州市金融局 | guangzhou_jr | local | 金融 | jrjgj.gz.gov.cn/zcgh/index.html |
| 广州市商务局 | guangzhou_sw | local | 商贸 | sw.gz.gov.cn/xxgk/tzgg/tz/ |

**2026-08-21 实测修正记录**：
- 商务部旧路径 `/article/zcfb/zc/` 已失效 → 新路径 `/zcfb/zc/`
- 广州财政局 `/zwgk/tzgg/` 已失效 → `/tzgg/`
- 广东税务局 `/site/guangdong/tax/notice/` 已失效 → `/gdsw/zcwj/zcwj.shtml`
- 财政部翻页第 2 页实际是 `index_1.htm` → 配置 `page_offset: -1`（其余站 `index_2.html` 起为 0）
- 中央税务/金融分类的数据来源见第 2 节替代说明

**关键 XPath 字段**（均按真实 DOM 实测配置，多路径用 `|` 联合，代码侧有兜底）：
- `list_link_xpath` — 列表页链接提取（chinatax_central/guangdong_tax 按标题是否含"广东"分流）
- `detail_content_xpath` — 正文容器（多节点匹配时代码自动取文本最长者）
- `detail_date_xpath` — 发布日期（XPath 失败时代码从页面头部文本按"发布日期/发文日期/时间"上下文正则兜底）

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

## 6. 硬约束

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
- cron 定时爬虫：**未注册**（用户明确要求需要时再开）。已注册的 cron 只有 DB 备份（每天 3:00 备份到 /opt/backups/，4:00 清理 7 天前）。要开定时爬虫时执行（每天 7:00 爬取+重建索引）：
  ```bash
  ( crontab -l 2>/dev/null | grep -v "crawl_policies" ; \
    echo "0 7 * * * cd /opt/policy_reporter && docker compose exec -T backend python manage.py crawl_policies --all >> /var/log/crawl.log 2>&1 && docker compose exec -T backend python manage.py build_index >> /var/log/crawl.log 2>&1" ) | crontab -
  ```
  注意 `-T` 必须加（cron 无 tty 环境不加会静默失败）
- admin IP 白名单：ADMIN_ALLOWED_IPS 已配在 .env
- 代码更新流程：`git pull origin main` → 如改了模型需 `migrate` → **改了任何 backend 代码/配置必须 `docker compose up -d --build backend`**（容器里是构建时打包的代码，不 rebuild 跑的还是旧版，此坑已踩过两次）

---

## 8. 手动测试与运维指引（接手者必读）

### 8.1 手动更新政策数据（当前唯一的更新方式，无定时任务）

```bash
cd /opt/policy_reporter

# 爬取（增量，按 source_url 去重，重复跑安全；失败项下轮自动重试）
docker compose exec backend python manage.py crawl_policies --all

# 重建 RAG 索引（爬完必跑，否则 Agent rag_search 检索的是旧数据）
docker compose exec backend python manage.py build_index
```

**验证数据质量**（4 大类中央/地方都要有数，空正文应为 0）：
```bash
docker compose exec backend python manage.py shell -c "
from report.models import CentralPolicy, LocalPolicy
from collections import Counter
print('中央:', dict(Counter(CentralPolicy.objects.values_list('type', flat=True))))
print('地方:', dict(Counter(LocalPolicy.objects.values_list('type', flat=True))))
print('空正文:', CentralPolicy.objects.filter(content='').count() + LocalPolicy.objects.filter(content='').count())
"
```

基准参考（2026-08-21 首爬）：中央 财政24/税务8/金融33/商贸29，地方 财政20/税务1/金融22/商贸29，共 166 条。

### 8.2 测试 Agent 日报生成（核心业务链路）

前端登录 → 日报页输入日期（如 2026-08-21，库里已有该日期前后数据）→ 发起 Agent Run → 前端每 2 秒轮询进度 → 完成后下载 docx，检查：
- 日报按 财政/税务/金融/商贸 分类组织
- 摘要对应正文内容（不是编的）
- AgentTrace 步骤 ≤15、无死循环

也可只跑单站爬虫测试：`crawl_policies --site mof --dry-run`（site_id 见第 4 节表格）

### 8.3 跑评估框架（量化 Agent 质量）

```bash
# 基线评估（成功率/平均步数/Critic 触发率/修复率/LLM-judge 评分）
docker compose exec backend python manage.py run_eval --yes

# 消融实验（baseline / no_critic / no_replanner / no_stall）
docker compose exec backend python manage.py run_eval --ablation baseline --yes
docker compose exec backend python manage.py run_eval --all-ablations --yes

# 报告在 backend/eval_reports/ 目录
```

注意：eval 的 LLM-judge 会调 DeepSeek API，消耗少量额度。

### 8.4 跑测试套件（改代码后确认无回归）

```bash
docker compose exec backend pytest --tb=short -q
```

### 8.5 爬虫出问题时的排查流程

症状 → 原因 → 处理：
- **"找到 0 个链接"** — 站点改版，list_link_xpath 或 URL 失效 → `curl -A "Mozilla/5.0 ... Chrome/120" <列表页URL>` 看 HTML 里的真实链接格式和栏目路径，改 crawl_config.json
- **"content=0字"** — 详情页改版 → 同上，curl 详情页看正文容器的 class/id，改 detail_content_xpath（多路径用 `|` 联合，代码自动取文本最长节点）
- **"date=None"** → 日期 XPath 失效（代码有"发布日期/发文日期"文本兜底，一般不易触发）
- **大量 [HTTP 502]/[HTTP 412]** — 网站限流/反爬。502 多为临时性（重跑即可）；持续 412 需在站点配置加自定义请求头
- 改完 crawl_config.json 后：`git add/commit` → 推双远端 → 服务器 `git pull` → **`docker compose up -d --build backend`** → dry-run 验证

### 8.6 日志位置

- 爬虫输出：手动跑时直接看终端；开 cron 后在 /var/log/crawl.log
- Django/Agent：`docker compose logs backend --tail 100`

---

## 9. 代码鲁棒性审查与修复记录（2026-08-16）

### 修复的 8 个问题

| # | 严重度 | 文件 | 问题 | 修复 |
|---|--------|------|------|------|
| 1 | **P0 严重** | agent/views.py:173 | 变量 `has_docx_trace` 遮蔽导入的同名函数，导致 `UnboundLocalError`，线上 `agent_runs_list` 端点 500 | 局部变量改名 `has_docx` |
| 2 | P1 | agent/core.py:22 | 未使用的 `from datetime import datetime` 死导入 | 删除 |
| 3 | P1 | agent/core.py:98,124 | LLM 返回 `None` content 时 `json.loads(None)` 抛 `TypeError`，穿透容错逻辑 | 抽取 `_parse_llm_json()` 公共函数，显式判空 + 捕获 `(JSONDecodeError, TypeError)` |
| 4 | P1 | agent/core.py:372 | `isinstance(a, tuple)` 在 JSON 序列化后恒为 False（tuple→list），断点续跑会丢失 key_decisions | 改为 `len(a) >= 2` 兼容 tuple/list |
| 5 | P1 | agent/rag.py:33 | `_get_collection` 不检查 `_client` 是否已存在，可能覆盖已有客户端 | 加 `if _client is None:` 守卫，与 `_get_episodic_collection` 对齐 |
| 6 | P1 | report/views.py:56 | `call_deepseek_summarization` 无重试无异常处理，DeepSeek 限流导致导出偶发失败 | 加指数退避重试（3 次），重试耗尽返回空摘要不阻断导出 |
| 7 | P1 | crawl_policies.py:290 | 配置文件读取无异常处理，文件缺失/JSON 错误抛原始堆栈 | 加 `FileNotFoundError` / `JSONDecodeError` 捕获 + 友好提示 |
| 8 | P2 | agent/views.py:105 | `traces.last().step` 在 list comprehension 消费 QuerySet 后触发不必要的二次 SQL | 改为 `trace_list[-1]['step']` |

### 消除的重复代码
- `_call_actuator` 和 `_call_critic` 的 JSON 解析容错逻辑重复 → 抽取 `_parse_llm_json()` 公共函数

### 双语注释
以下关键函数已加中英文双语注释：
- `core.py`: `_parse_llm_json` / `_call_actuator` / `_call_critic` / `key_decisions` 逻辑
- `rag.py`: `_get_collection`
- `report/views.py`: `call_deepseek_summarization`
- `crawl_policies.py`: `handle` 配置读取

### 验证
- 所有 44 个 Python 文件编译通过（`py_compile` 检查）
- 本地无 pytest 环境，服务器有完整 pytest 环境，推送后跑 `pytest --tb=short -q` 确认无回归
