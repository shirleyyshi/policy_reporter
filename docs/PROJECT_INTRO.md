# 项目介绍（中英文）

> 用途：项目概括用于口头介绍、作品集、导师/HR 快速了解；简历版用于简历项目经历栏。
> 表述刻意宏观：代码会持续迭代，具体数字以 `interview/INTERVIEW_PLAYBOOK.md` 的口径为准，本文避免写死易变细节。

---

## 一、项目概括（注重项目本身）

### 中文

Policy Reporter（财税政策日报生成系统）是一个自动化的政策资讯加工平台：系统每天定时从多个政府公开网站采集财税政策（中央部委 + 地方部门，覆盖财政、税务、金融、商贸四个领域），经清洗、去重、分类后入库；用户既可以在网页上按日期浏览、勾选政策一键导出排版好的 Word 日报，也可以交给内置的 ReAct 智能体（Agent）自主完成"取数 → 清洗 → 摘要 → 成稿"全流程。Agent 由大模型驱动，能自主规划执行步骤，内置质量审查与重规划机制、步数止损保护，并在关键判断点上暂停向用户提问（人在回路）；其每一步思考与操作都记录在案，运行轨迹可在网页上回看。系统还包括基于向量检索的历史日报参考（RAG）、用户级数据隔离、自动化测试与组件消融实验，以 Docker 容器化部署，具备健康检查与每日自动运维能力。

### English

Policy Reporter is an automated policy intelligence platform for China's fiscal and tax domain. Every day it crawls public policy releases from multiple government websites (central ministries plus provincial bureaus, covering finance, taxation, banking and commerce), then cleans, deduplicates and classifies them into a database. Users can browse policies by date in a web UI and export a formatted Word daily report with one click — or delegate the entire pipeline (fetch → clean → summarize → compose) to a built-in ReAct agent. The agent is driven by a large language model, plans its own steps, and ships with a quality-critic / replanner loop, a step-budget guard, and human-in-the-loop checkpoints where it pauses and asks the user before making judgment calls. Every thought and tool call is recorded and replayable in the web UI. The system further includes RAG-based retrieval over past reports, per-user data isolation, an automated test suite with ablation studies validating each agent component, and Docker-based deployment with health checks and daily cron maintenance.

---

## 二、简历项目介绍（注重个人能力与实现成果）

### 中文（条目式，可直接放简历）

**Policy Reporter — 财税政策日报智能生成系统**（独立开发，全栈 + LLM Agent）

- 独立设计并实现全栈系统：Vue 3 前端 + Django/DRF 后端 + MySQL + Docker 容器化部署，覆盖从数据采集到成品导出的完整链路
- 基于 ReAct 范式构建 LLM Agent：模型自主规划工具调用，配套 Critic 质量审查、Replanner 重规划、步数止损与人在回路确认，运行轨迹逐步落库可回看
- 构建端到端数据与生成管线：多站点定时爬虫（礼貌限速、增量去重、全量可溯源）+ RAG 检索增强 + DeepSeek API，自动产出排版规范的 Word 日报
- 建立质量保障体系：200+ 自动化测试（CI 覆盖率门槛 80%），并通过组件消融实验用数据验证 Critic/Replanner 等设计的必要性
- 落地多用户安全与生产化运维：JWT 双令牌自动续期、用户级数据隔离、越权访问防护，Docker 健康检查 + 每日 cron 自动运维

### English（bullet style, résumé-ready）

**Policy Reporter — AI-Powered Fiscal Policy Daily Report System** (solo developer, full-stack + LLM agent)

- Independently designed and built a full-stack system: Vue 3 frontend, Django/DRF backend, MySQL, and Dockerized deployment covering the entire pipeline from data ingestion to report export
- Engineered a ReAct-style LLM agent with autonomous tool planning, a critic/replanner quality loop, step-budget safeguards, and human-in-the-loop checkpoints; every step is persisted and replayable in the web UI
- Built the end-to-end data and generation pipeline: multi-site scheduled crawlers (polite rate limiting, incremental deduplication, fully traceable records) + RAG retrieval + the DeepSeek API, automatically producing formatted Word reports
- Established quality engineering: 200+ automated tests (80% CI coverage gate) and component ablation studies quantifying the contribution of each agent module
- Delivered multi-user security and production operations: dual-token JWT with silent refresh, per-user data isolation, cross-user access protection, plus Docker health checks and daily cron maintenance

### 使用提示

- 简历空间紧张时可再裁到 4 条（建议合并：把安全/运维并入第 1 条全栈部署）
- 面试展开每一条的口径见 `interview/INTERVIEW_PLAYBOOK.md`；数字的最新精确值以该文件为准
