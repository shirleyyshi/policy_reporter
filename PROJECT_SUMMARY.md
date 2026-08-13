# Policy_Reporter 项目总结

> 财税政策日报生成器，从半成品改造为 ReAct Agent 项目。本文档是分阶段开发完成后的最终总结，供学习与面试复盘用。

---

## 一、项目定位

把"写死的 export → summarize → docx pipeline"改造为 **LLM 自主编排工具的 ReAct Agent**，用于海外 AI 硕士申请与求职面试展示。

**核心改造点**：Agent 根据数据状态动态选择工具组合，而非固定流程。同一条 prompt，不同日期的数据密度（dense / sparse / empty / duplicate / partial_missing）会让 Agent 走不同路径——这是"反玩具"的关键证据。

**不面向**：真实生产高并发。不做高可用、不做真实多用户、不做监控告警。

---

## 二、技术栈

| 层 | 选型 |
|---|---|
| Agent LLM | DeepSeek-chat（通过 OpenAI SDK 调用） |
| 后端 | Django 5.2 + DRF 3.16 + MySQL + JWT |
| 前端 | Vue 3 + Vite + Element Plus |
| 部署 | Docker + docker-compose（MySQL + Django + Nginx） |
| 爬虫 | requests + lxml（Django management command，零新依赖） |

---

## 三、整体架构

```
┌──────────────────────────────────────────────────────────┐
│  数据层（Phase 1）                                        │
│  crawl_policies 命令 → gov.cn / shanghai.gov.cn → DB     │
│  CentralPolicy / LocalPolicy（含 crawled_at 字段）        │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  Agent 层（Phase 2）                                      │
│  ReAct 主循环（core.py）                                  │
│    Actuator (每步 1 次 LLM) → 工具执行 → Observation      │
│    Critic (每 3 步 / 重复 / 停滞时) → Replanner 注入 hint │
│    Terminator (代码：max_steps / 重复 / 失败 / 求助上限)   │
│  10 个工具（tools.py）                                    │
│    fetch_central / fetch_local / clean_policy /          │
│    deduplicate / classify_policy / summarize /           │
│    rag_search / save_to_db / format_docx / ask_human     │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  人在回路（Phase 5）                                      │
│  后台线程 + waiting_human 状态 + 前端 2s 轮询 + 弹窗       │
│  threading.Event 实现线程同步，5 分钟超时兜底              │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  评估层（Phase 3-4）                                      │
│  EvalRunner + 4 消融配置 + LLM-as-judge                   │
│  测试场景：dense/empty/sparse/with_legal/duplicate/       │
│           partial_missing（自动从 DB 发现）                │
└──────────────────────────────────────────────────────────┘
```

---

## 四、分阶段完成内容

### Phase 0：地基清创

- `django-environ` 密钥外置到 `.env`，`.gitignore` 防泄露
- `requirements.txt` 锁版本号
- Docker 三容器骨架（MySQL + Django + Nginx）
- 保留旧功能：政策 CRUD、JWT 登录、DeepSeek 摘要、docx 导出

### Phase 1：数据层（爬虫 + 合成数据）

- **替代方案**：原 `config_policy_spider/` 的 Scrapy + Splash 太重且 Postgres 不兼容，重写为 Django management command
- 实现：[crawl_policies.py](./backend/apps/report/management/commands/crawl_policies.py) + [crawl_config.json](./backend/apps/report/management/commands/crawl_config.json)
- 站点：国务院政策库 `gov.cn` + 上海市政府 `shanghai.gov.cn/nw12344/`
- 特性：`source_url` 去重、`title_filter` 政策类型过滤、`crawled_at` 采集时间、多格式日期解析
- 合成数据：[seed_eval_data.py](./backend/apps/agent/management/commands/seed_eval_data.py) 植入 sparse/duplicate/partial_missing 三场景测试数据（`source_url` 含 `eval_seed` 标记区分）
- 实测数据量：33 条（21 条真实爬虫 + 12 条 eval seed），覆盖 2025-08 ~ 2026-07

### Phase 2：Agent 核心

- **ReAct 主循环**（[core.py](./backend/apps/agent/core.py)）：max_steps=15，每步 LLM 决策 {reasoning, tool, params, done}
- **10 个工具**（[tools.py](./backend/apps/agent/tools.py)）：批量式操作 AgentState，LLM 只看计数摘要（避免把政策全文塞进 prompt）
- **三角色合并**：Actuator（Planner+ToolSelector+ParamGen 合一）、Critic（Critic+Replanner 合一）、Terminator（纯代码）
- **循环防护**：连续 3 次重复触发 Critic、连续 3 次失败终止、5 步停滞触发 Critic、ask_human 上限 3 次
- **trace 入 DB**：`AgentTrace` 表记录每步 {step, action, tool, input, output, reasoning}
- **RAG 真实化**：[rag.py](./backend/apps/agent/rag.py) 接入 ChromaDB（all-MiniLM-L6-v2 多语言 embedding），[build_index](./backend/apps/agent/management/commands/build_index.py) 命令构建向量索引，`rag_search` 工具实际检索相似历史政策（返回标题+相似度+source_url）
- **RAG 行为验证**：sparse 场景（数据 <5 条）Agent 主动调 RAG 补充上下文；dense 场景 Agent 跳过 RAG 直接 summarize——"不同 run 不同路径"的反玩具证据
- **单元测试**：[tests.py](./backend/apps/agent/tests.py) 21 个测试覆盖 `_clean_text` / `clean_policy` / `deduplicate` / `classify_policy` / `AgentState`，`python manage.py test agent` 全过

### Phase 3：Eval 框架

- [EvalRunner](./backend/apps/agent/eval/runner.py) 支持自定义配置批量跑测试集
- 4 组消融配置：
  - `baseline`：默认全开
  - `no_critic`：Critic 关掉（`critic_every_n=999`）
  - `no_replanner`：Replanner 关掉（不接收 Critic 的 hint）
  - `no_stall`：停滞检测关掉
- 测试场景自动从 DB 发现：dense / empty / sparse / with_legal / duplicate / partial_missing
- 评分：LLM-as-judge 评摘要质量（1-5 分）+ 步数 + 工具调用分布 + 修复率

### Phase 4：消融实验

跑完 4 组配置 × 6 场景的实验，关键结论：

| 组件 | 作用 | 量化结论 |
|---|---|---|
| Critic | 诊断问题 | 增加 32% 时间开销，不影响最终质量 |
| Replanner | 修复问题 | 关掉后修复率 0%（虽有 Critic 诊断但无 hint 注入） |
| 停滞检测 | 兜底 | 在 partial_missing 场景把质量从 4 提到 5 |

**核心 tradeoff**：Critic 和 Replanner 是配套的——单独开 Critic 只会增加开销不提升质量，必须配套 Replanner 才能转化诊断为修复。这是一个反"组件堆砌"的工程教训。

### Phase 5：人在回路

- Agent 改为后台线程运行，状态存 DB
- `ask_human` 触发时设 `status=waiting_human`，通过 `threading.Event` 阻塞线程
- 前端每 2 秒轮询 `/runs/{id}/state/`，检测到 `waiting_human` 弹窗显示问题
- 用户提交答案 → `/runs/{id}/answer/` → 唤醒线程继续
- 同步模式（eval 用）仍走 mock，互不影响

---

## 五、Phase 6 待办（部署 + 简历包装）

### 部署
- [ ] 写 `crawl.sh` cron 脚本（每天 7 点爬一次）
- [ ] 写 `crawl.bat` Windows 任务计划脚本
- [ ] Docker compose 一键启动验证
- [ ] 生产环境 settings（DEBUG=False、ALLOWED_HOSTS）
- [ ] Nginx 静态文件配置
- [ ] 部署后 cron 跑爬虫 + `build_index` 重建 RAG 索引

### 简历素材
- [ ] 整理 4 组消融实验对比表（已有 md 报告在 [eval_reports/](./backend/eval_reports/)）
- [ ] 整理 failure case：empty 场景 Agent 如何处理、duplicate 场景 dedup 工具效果
- [ ] 整理 trace 样例：sparse 触发 RAG vs dense 跳过 RAG 的路径差异
- [ ] 录制 demo 视频：前端弹窗 ask_human 交互

---

## 六、关键设计决策（面试 tradeoff）

| 决策点 | 选择 | 理由 |
|---|---|---|
| Agent 模式 | ReAct 而非 Plan-and-Execute | ReAct 每步可见 observation，trace 更可解释；Plan-and-Execute 计划一旦失败要全盘重规划 |
| 三角色合并 | 7 → 3 | Planner/ToolSelector/ParamGen 合为 Actuator（一次 LLM 调用产出 structured output）；Critic+Replanner 合一；Terminator 纯代码 |
| 工具调用方式 | 批量式而非逐条 | 工具操作 AgentState，LLM 只看计数摘要——避免把 20 条政策全文塞进 prompt |
| 分类工具 | 确定性元数据而非 LLM | DB 的 `type`/`province` 字段已是结构化分类，再调 LLM 浪费且不稳——"并非每一步都需要 LLM" |
| RAG 接入 | ChromaDB + 多语言小模型 | 本地 PersistentClient 零 API 成本；all-MiniLM-L6-v2 模型 80MB；政策少于 5 条时 Agent 主动调 RAG，数据充足时跳过——"按需调用"而非"每步必调" |
| 人在回路 | 轮询而非 WebSocket | Django Channels + Redis 是新基础设施，面试不因 WebSocket 加分；轮询能实现暂停求助，省 3-5 天 |
| 爬虫 | Django 命令而非 Scrapy | 政府站都是纯 HTML，requests+lxml 够用；Scrapy+Splash 杀鸡用牛刀 |
| Eval 方式 | LLM-as-judge + 消融 | 人工标注基准太慢；消融实验能证明组件价值而非堆砌 |

---

## 七、4 个反玩具硬指标完成情况

| 指标 | 完成方式 | 证据 |
|---|---|---|
| 不同 run 走不同路径 | 数据状态驱动工具选择 | dense 跳过 RAG 直接 summarize，sparse 触发 2 次 RAG 调用补充上下文，empty 触发 ask_human，duplicate 触发 dedup——trace 各异 |
| ablation 数据 | 4 组配置 × 6 场景 | [eval_reports/](./backend/eval_reports/) 下 8 份报告（baseline + ablation） |
| failure case + 修复 | empty 场景 + partial_missing 场景 | empty 触发 ask_human 兜底；partial_missing 在 no_replanner 下质量降级 |
| 设计 tradeoff 解释 | 每个决策都有理由 | 见上表，面试时能讲为什么选 ReAct、为什么合并角色、为什么用轮询、为什么 RAG 按需调用 |

---

## 八、关键文件索引

### Agent 核心
- [backend/apps/agent/core.py](./backend/apps/agent/core.py) — ReAct 主循环、同步/异步入口、人在回路线程同步
- [backend/apps/agent/tools.py](./backend/apps/agent/tools.py) — 10 个工具 + AgentState
- [backend/apps/agent/rag.py](./backend/apps/agent/rag.py) — ChromaDB 向量检索封装（rebuild_index / search）
- [backend/apps/agent/prompts.py](./backend/apps/agent/prompts.py) — Actuator/Critic system prompt
- [backend/apps/agent/models.py](./backend/apps/agent/models.py) — AgentTrace 表
- [backend/apps/agent/views.py](./backend/apps/agent/views.py) — Agent API（启动/轮询/回答/下载）
- [backend/apps/agent/tests.py](./backend/apps/agent/tests.py) — 21 个单元测试
- [backend/apps/agent/management/commands/build_index.py](./backend/apps/agent/management/commands/build_index.py) — 构建 RAG 索引命令

### 数据层
- [backend/apps/report/models.py](./backend/apps/report/models.py) — CentralPolicy / LocalPolicy（含 crawled_at）
- [backend/apps/report/management/commands/crawl_policies.py](./backend/apps/report/management/commands/crawl_policies.py) — 爬虫命令
- [backend/apps/report/management/commands/crawl_config.json](./backend/apps/report/management/commands/crawl_config.json) — 站点配置
- [backend/apps/report/views.py](./backend/apps/report/views.py) — 旧版 export/generate_docx（Agent 复用）

### Eval
- [backend/apps/agent/eval/runner.py](./backend/apps/agent/eval/runner.py) — EvalRunner + 4 消融配置
- [backend/apps/agent/eval/testset.py](./backend/apps/agent/eval/testset.py) — 测试用例自动发现
- [backend/apps/agent/eval/metrics.py](./backend/apps/agent/eval/metrics.py) — per-run 指标收集
- [backend/apps/agent/management/commands/seed_eval_data.py](./backend/apps/agent/management/commands/seed_eval_data.py) — 造数据命令
- [backend/apps/agent/management/commands/run_eval.py](./backend/apps/agent/management/commands/run_eval.py) — 跑 eval 命令
- [backend/eval_reports/](./backend/eval_reports/) — 8 份实验报告

### 前端
- [frontend/src/views/AgentRun.vue](./frontend/src/views/AgentRun.vue) — 启动 Agent + 轮询 + 弹窗
- [frontend/src/views/AgentRuns.vue](./frontend/src/views/AgentRuns.vue) — 历史 run 列表

---

## 九、运行指南

### 爬虫（每天定时）
```bash
# 手动跑一次
cd backend
python manage.py crawl_policies --all

# Ubuntu cron（每天 7:00 跑爬虫 + 重建 RAG 索引）
0 7 * * * cd /opt/policy_reporter/backend && /opt/venv/bin/python manage.py crawl_policies --all && /opt/venv/bin/python manage.py build_index >> /var/log/crawl.log 2>&1
```

### RAG 索引（爬虫后跑）
```bash
# 重建向量索引（幂等：清空 + 重新插入所有 DB 政策）
python manage.py build_index

# 只看索引数量
python manage.py build_index --count
```

### 单元测试
```bash
# 跑所有 agent 工具测试（21 个，<1 秒）
python manage.py test agent

# 跑指定测试类
python manage.py test agent.tests.DeduplicateTest
```

### Agent（手动触发或 API）
```bash
# eval 模式（同步跑测试集）
python manage.py run_eval

# API 模式（前端调用）
POST /api/agent/run/  {"date": "2026-07-13"}
GET  /api/agent/runs/{id}/state/   # 每 2s 轮询
POST /api/agent/runs/{id}/answer/  # ask_human 时回答
GET  /api/agent/runs/{id}/download/  # 下载 docx
```

### 端到端验证（已通过）
- 爬虫：21 条真实政策入库
- Agent：2026-07-13 日期，8 步完成，174 字摘要，794 KB docx
- Critic 触发并给出 replan_hint，配套机制正常

---

## 十、踩坑记录

| 问题 | 解决 |
|---|---|
| DB 表名找不到 | app 注册为 `report`/`agent` 而非 `apps.report`，import 要用 `from report.models import ...` |
| in-memory docx 缓存服务器重启后 404 | 改为文件系统持久化到 `media/agent_docx/{run_id}.docx` |
| PowerShell 不支持 `&&` | 用 `;` 分隔命令 |
| Shanghai 详情页 `div.contain` 只含面包屑 | 实际正文在 `div.Article_content`，改 XPath |
| `apps.report.models` 不声明 app_label | app 注册名是 `report`，不是 `apps.report` |
| 政府站改版导致 XPath 失效 | 失败时打印 URL 便于排查；每日跑 + source_url 去重容错 |
