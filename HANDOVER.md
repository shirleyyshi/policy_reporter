# Policy Reporter 交接文档

> 最后按代码复核：2026-08-22
> 定位：用于展示的个人学习项目，而非生产系统。它从政府公开站点采集财税相关政策，入库后由 ReAct Agent 编排工具生成 Word 日报。
> 配套：面试演示脚本与话术见 `INTERVIEW_PLAYBOOK.md`；内网部署改造问答见 `INTERVIEW_PREP.md`。

## 1. 先读这一页

### 当前可用能力

- 8 个公开政府站点的配置化采集，按 `source_url` 增量去重；当前采集范围为中央政策与**广东/广州**地方政策（原因见下）。
- Django + MySQL 保存政策；Vue 前端支持登录、按日期选择政策、手动导出和 Agent 运行轨迹查看。
- Agent 有 Actuator、Critic、Replanner、Terminator 四个职责，并持久化运行状态、轨迹和生成的 docx。
- ChromaDB 用于政策检索和历史运行经验检索；采集后需手动重建政策索引。
- Docker Compose 启动 MySQL、Django/gunicorn、Nginx/Vue 三个容器；GitHub Actions 包含后端测试（覆盖率门槛 80%）和前端构建。

### 已知数据快照（不是长期承诺）

2026-08-21 首次正式采集共 166 条：中央 94 条（财政 24、税务 8、金融 33、商贸 29），地方 72 条（财政 20、税务 1、金融 22、商贸 29），空正文为 0。数据会随站点改版、重跑和去重而变化，后续请以数据库查询结果为准。

### 关键边界：面试时必须如实说

- **地方源为什么是广东/广州，不是上海**：项目部署在新加坡云服务器，上海部分政府站点对海外 IP 访问受限，无法稳定采集，因此选择了从该服务器可稳定访问的广东/广州公开源。采集层是纯配置驱动的（`crawl_config.json`），后续若换国内服务器或需要上海数据，替换站点配置、重新采集即可，代码零改动——具体步骤见第 4.4 节。这是环境约束下的取舍，不是功能缺陷。
- Agent 的政策输入来自数据库，不会在运行日报时实时抓网页；`save_to_db` 是为保持工具集完整而保留的 stub，不是实际写库步骤。
- AgentRun 状态和已生成 docx 能在重启后读取；但后台 Agent 线程、等待人工回答的事件都在单个进程内。**进程重启不会续跑执行中的任务**，多 worker 下也不能保证人工回答命中原运行线程。
- 当前服务是 HTTP/IP 部署，没有域名和 HTTPS。不要在简历、README 或面试中说"已配 HTTPS""生产级"或"高并发"。
- 测试与消融数据是历史结果：仓库当前 194 个测试（含 config/ 下中间件测试），CI 覆盖率门槛 80%（README 记录最近一次 82%）；README 的消融对比表来自历史 eval 运行，`backend/eval_reports/` 报告目录未入库，如需复现需重跑 `run_eval`（会调用 DeepSeek 产生费用）。

## 2. 架构和数据流

```text
政府公开站点
  -> crawl_policies（requests + lxml；配置在 crawl_config.json）
  -> MySQL（CentralPolicy / LocalPolicy）
  -> build_index
  -> ChromaDB（政策检索索引）

Vue 3 前端 -> Nginx -> Django REST API -> MySQL / ChromaDB / DeepSeek API
                                      -> AgentRun + AgentTrace
                                      -> media/agent_docx/*.docx
```

Agent 的典型路径为：`fetch_central/fetch_local -> clean_policy -> deduplicate -> classify_policy -> summarize -> format_docx`。当数据稀少时，模型可选择 `rag_search`；Critic 定期给出重规划建议，Terminator 以最大步数（15）、连续失败（3 次）、重复调用（3 次）、停滞（5 步无变化）和 ask_human 上限（3 次）等规则兜底。LLM 调用带 3 次指数退避重试。

## 3. 关键文件

| 用途 | 文件 |
|---|---|
| Agent 主循环、状态持久化、人工介入 | `backend/apps/agent/core.py` |
| 10 个 Agent 工具 | `backend/apps/agent/tools.py` |
| Agent 提示词 | `backend/apps/agent/prompts.py` |
| 向量检索与 episodic memory | `backend/apps/agent/rag.py` |
| Agent API（启动/轮询/回答/下载） | `backend/apps/agent/views.py` |
| AgentRun / AgentTrace 模型 | `backend/apps/agent/models.py` |
| 消融配置与 eval 运行器 | `backend/apps/agent/eval/runner.py` |
| LLM-as-judge 评分 | `backend/apps/agent/eval/metrics.py` |
| 测试场景自动发现 | `backend/apps/agent/eval/testset.py` |
| eval 命令 / 造数据命令 / 建索引命令 | `backend/apps/agent/management/commands/run_eval.py`、`seed_eval_data.py`、`build_index.py` |
| 政策模型和 docx 导出 | `backend/apps/report/models.py`、`backend/apps/report/views.py` |
| 配置化爬虫 | `backend/apps/report/management/commands/crawl_policies.py` |
| 采集源、XPath 与分类 | `backend/apps/report/management/commands/crawl_config.json` |
| admin IP 白名单中间件 | `backend/config/middleware.py` |
| 容器和外部端口 | `docker-compose.yml`、`frontend/nginx.conf` |
| CI | `.github/workflows/test.yml` |
| 定时采集脚本（服务器未注册 cron） | `scripts/crawl.sh`、`scripts/crawl.bat` |

## 4. 数据源与维护原则

业务分类为财政、税务、金融、商贸，中央和地方都使用 `type` 字段。当前 8 个源为：

| 范围 | 分类 | 当前来源 |
|---|---|---|
| 中央 | 财政 | 财政部 |
| 中央 | 税务 | 广东省税务局转载的总局文件 |
| 中央 | 金融 | 国家外汇管理局 |
| 中央 | 商贸 | 商务部 |
| 地方 | 财政 | 广州市财政局 |
| 地方 | 税务 | 广东省税务局"粤文件" |
| 地方 | 金融 | 广州市地方金融局 |
| 地方 | 商贸 | 广州市商务局 |

注意中央税务与地方税务共享同一列表页，通过标题是否含"广东"分流，属于脆弱规则；若页面结构或标题命名变化，应首先人工抽样验证分类。财政部可能间歇 502（已加重试），商务部列表使用内部 JSON 接口；两者都应在站点改版时重点检查。

采集原则：遵守网站规则、限速、保留原始链接；采集异常或日期解析失败不要静默当作"今天"的政策。当前实现会在无法解析发布日期时以当前时间写库，因此需要人工抽检日期质量。

### 4.4 更换采集地区（可选扩展，非必须）

采集层没有写死任何站点。若后续要换地区（例如部署环境变更后接入上海源），操作是纯配置替换：

1. 在 `crawl_config.json` 中新增/替换站点条目：`list_url`、翻页 `page_url_pattern`、三个 XPath（列表链接 / 详情标题 / 详情正文 / 日期）和默认分类。
2. `python manage.py crawl_policies --site <new_site> --dry-run` 试运行，人工核对标题、正文、日期、分类。
3. 确认无误后正式采集（新库先清空旧数据），再 `build_index` 重建向量索引。
4. 用第 5 节的抽检命令验证分类分布与空正文比例。

整个过程中 `crawl_policies.py` 主逻辑不需要改动；只有当目标站点是 JS 渲染或强反爬时才需要评估新方案。

## 5. 日常操作与验收

以下命令在服务器项目目录 `/opt/policy_reporter` 执行；定时采集脚本 `scripts/crawl.sh` 已就绪但**尚未注册 cron**，如需每日自动采集，按脚本头部注释注册即可。

```bash
# 增量采集；可重复执行
docker compose exec backend python manage.py crawl_policies --all

# 采集后必须同步向量索引
docker compose exec backend python manage.py build_index

# 单站试运行，不写库
docker compose exec backend python manage.py crawl_policies --site mof --dry-run

# 质量抽检：分类分布、空正文、无来源链接
docker compose exec backend python manage.py shell -c "
from report.models import CentralPolicy, LocalPolicy
from collections import Counter
for name, model in [('central', CentralPolicy), ('local', LocalPolicy)]:
 print(name, dict(Counter(model.objects.values_list('type', flat=True))))
 print('empty_content=', model.objects.filter(content='').count(), 'empty_url=', model.objects.filter(source_url='').count())
"

# 回归测试（容器内应安装开发依赖；本地需先 pip install -r requirements-dev.txt）
docker compose exec backend pytest --tb=short -q
```

人工验收至少覆盖：登录、按日期查看政策、手动导出 docx、启动一次 Agent、查看 trace、下载 Agent docx。完整的面试演示流程（含人在回路、重启韧性等场景）见 `INTERVIEW_PLAYBOOK.md` 第 3 节。运行评估会调用 DeepSeek 并产生费用，且结果受模型与数据集变化影响；不要把一次消融结果包装成统计显著性结论。

## 6. 当前风险与改进优先级

### P0：安全与部署边界

已修复（2026-08-23）：

1. MySQL `3306` 与 Django `8000` 原直接暴露到宿主机，可绕过 Nginx；现改为只绑定 `127.0.0.1`，本地开发不受影响，外部必须经前端 Nginx 反代。**部署注意**：端口映射变更需在服务器执行 `docker compose up -d`（重建全部容器），仅 `--build backend` 不够。
2. `ADMIN_ALLOWED_IPS` 原先没传入 backend 容器，白名单形同虚设；现已传入。中间件同步加固：优先取 `X-Real-IP`（由本方 Nginx 覆盖设置、客户端不可伪造），不再信任 `X-Forwarded-For` 首项（客户端可自带伪造）；白名单含空串时视为未配置放行。生效前提：服务器 `.env` 中填写 ADMIN_ALLOWED_IPS 并重建容器。
3. Critic 输出解析失败原静默返回"无需重规划"；现记 warning 日志（含错误与原文前 200 字），返回语义不变，不污染消融指标口径。
4. `_deserialize_state` 原不把 ISO 字符串还原为 datetime，重启恢复后 `raw_policies[].publish_time` 变成字符串；现恢复为 datetime，与内存 state 类型一致（`clean_policies` 的 publish_time 本就是 str，属设计内，不处理）。
5. 顺带修复两个陈旧测试（`test_views.py` 引用已迁移到 `agent/utils.py` 的 `has_docx_trace` 旧名；`test_core.py` 期望的 LocalPolicy 默认 type 已从"综合"改为空串），修复前 CI 全量跑是红的。
6. `/static/` 静态文件服务已改为 Nginx 直接挂载共享卷（2026-08-24）：`backend_static` 卷同时挂入 backend（collectstatic 输出）与 frontend（只读），nginx `location /static/` 用 `alias` 直接服务并加 7 天缓存。原配置把 `/static/` 反代给 gunicorn，但 `DEBUG=False` 下 Django 不服务静态文件，admin 页面无样式。`/media/` 反代配置已移除——docx 下载本就走鉴权 API（`/api/agent/runs/<id>/download/`），直接暴露 media 目录反而绕过登录。**部署注意**：frontend 服务新增卷挂载，需 `docker compose up -d` 重建 frontend 容器。

仍待办（2026-08-24 决定：降级为不做，面试按"内网部署时按等保要求实施"口径讲）：

7. HTTPS、HTTP 安全响应头、登录/API 限流、备份恢复演练和密钥轮换。前置条件是域名；现有 fail2ban 只保护 SSH，不能替代应用安全控制。

### P1：提升演示与多用户价值

1. 为 `AgentRun` 关联创建用户并限制列表、trace、docx 下载到本人；现在所有已登录用户可查看所有运行记录。
2. 增加政策详情页、来源筛选、发布日期/采集日期展示和失败采集报表。面试演示应能清楚说明一条数据从何处来、何时采集、是否可追溯。
3. 将后台线程迁移到 Celery/RQ + Redis，人工介入用共享状态或消息队列；任务要有可取消、超时、失败重试和重启恢复语义。
4. 前端接入 refresh token（现在存了但未使用，access token 2 小时过期后只能重新登录）。

### P2：让"Agent"更可信、更可评估

1. 让 RAG 命中的正文片段明确参与摘要上下文，或把它定位为"检索建议"。当前 `rag_search` 主要把标题、链接和相似度返回给模型，不能证明其直接补充了摘要事实。
2. 把评估集固定为版本化的匿名样本和预期检查，不要完全依赖当前数据库动态发现用例；记录模型版本、提示词版本、随机参数和原始报告，并将 `eval_reports/` 产物入库以便复现。
3. "Critic 修复率"应改称"Critic 建议重规划率"，除非定义并验证"建议后任务确实恢复成功"的分子与分母。
4. 增加接口分页、日期格式校验、结构化日志、健康检查、爬虫失败告警、robots/站点规则记录和政策修订检测。

### 可以删减或降级的表述

- 不必把 `save_to_db` 当核心亮点；它目前是 no-op stub。
- 不要把 ChromaDB、ReAct、RAG 同时堆成"先进 AI 技术"。应讲清楚：哪些数据进了索引、何时检索、检索结果怎样影响决策。
- "10 工具动态编排"可以保留，但应同时说明其中以确定性清洗、去重、分类为主，LLM 只用于决策与摘要；这是更可信的工程取舍。

## 7. 面试口径（上海央国企技术岗）

推荐的一句话：

> 我实现了一个面向公开政策信息的日报生成原型：用 Django 完成可追溯采集和文档生成，用 ReAct 让模型在受控工具集内决定处理顺序，并把运行轨迹、失败保护和人工介入做成可观察的 Web 流程。下一步会按上海本地政策源、内网模型替换、国产数据库和审计权限完成企业内网适配。

避免承诺未实现的能力：生产级、高并发、服务重启自动续跑、真实上海政策覆盖、HTTPS 已部署、等保已通过、RAG 显著提升准确率。

对"如何适配内网"的回答应落在真实改造项：通过环境变量切换 OpenAI 兼容的内网模型服务；将异步任务和人工介入迁至 Redis/队列；以 Django ORM 评估国产数据库兼容性；增加 RBAC、审计、数据分级、证书与安全基线。不要说"改一个 URL 即可全部完成"。

## 8. 变更检查清单

- 改模型：生成并提交 migration，部署后执行 `migrate`。
- 改采集配置：先 `--dry-run`，抽样核对标题、正文、日期、分类和来源，再入库。
- 改爬虫后：重新执行 `build_index`，否则 RAG 仍检索旧索引。
- 改 backend 代码或配置：执行 `docker compose up -d --build backend`。
- 改 `docker-compose.yml`（端口/卷/环境变量）：执行 `docker compose up -d` 重建全部受影响容器（2026-08-23 端口改绑 127.0.0.1 后，服务器同步本次改动时需执行此命令）。
- 改前端：执行 `docker compose up -d --build frontend`，并确认 Agent 下载路径在未配置 `VITE_API_BASE` 时不会拼出 `undefined/api/...`。
- 提交前：运行测试、检查 `.env` 和数据库备份未被提交，并同步推送既定的 Gitee 与 GitHub 远端。

## 9. 文档地图与清理建议

当前根目录只保留五份有明确用途的文档：`README.md` 负责项目说明，`HANDOVER.md` 负责交接，`NEXT_STEPS.md` 负责后续待办的勾选跟踪，`INTERVIEW_PLAYBOOK.md` 负责演示与简历素材，`INTERVIEW_PREP.md` 负责央企内网改造问答。此前的历史审计、阶段总结和 TODO 文档内容已吸收到本文及面试材料中，不再单独保留，避免过时结论和悬空引用。

其他清理项：

- `backend/utils/response.py` 原为统一响应封装，但全仓无引用，已删除；空的 `backend/utils/` 包也已删除。
- `.gitignore` 中针对已删除 `config_policy_spider` 目录的专用规则已删除；通用 Python 缓存规则仍保留。
- `backend/htmlcov/` 为本地覆盖率产物，已被 gitignore，无需提交。
