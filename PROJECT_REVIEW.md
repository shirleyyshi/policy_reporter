# Policy_Reporter 项目审视报告

> 审视日期：2026-08-16
> 审视目的：作为央企国企科技岗求职简历的 AI Agent 项目，评估是否够用 + 面试官视角查缺漏
> 审视范围：26 个核心文件（agent / report / config / frontend / docker / 文档）
> 审视结论：**AI Agent 成色足，工程严谨度高，但央企国企适配叙事缺失，企业级特性为零，需针对性补强**

---

## 一、整体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 项目完整度 | ★★★★☆ | 端到端闭环（爬虫→Agent→docx→前端→部署），仅 Phase E 简历素材未做 |
| AI Agent 成色 | ★★★★☆ | 真 ReAct + Critic/Replanner + RAG + episodic memory + ablation，是项目最大亮点 |
| 工程化程度 | ★★★☆☆ | Docker + gunicorn + JWT + admin 白名单到位，但无 Redis / Celery / 监控 |
| 央企国企适配度 | ★★★☆☆ | 技术栈和业务场景对口，但国产化 / 等保 / RBAC / 审计完全缺失 |
| 简历竞争力 | ★★★★☆ | 央企国企科技岗（非大厂开发）够用，但需针对性包装 |

**结论**：**作为央企国企科技岗的 AI Agent 项目，够用，但有几个必补的叙事缺口**（见第三节）。

---

## 二、作为面试官审视：项目亮点与硬伤

### 2.1 值得展示的亮点（面试可讲）

| # | 亮点 | 证据 | 讲法 |
|---|------|------|------|
| 1 | 真 ReAct 循环，非 LLM Chain | [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 每步 LLM 决策 + observation 反馈 + 基于反馈调整 | "不是把 prompt 串起来，是 LLM 看上一步工具返回结果决定下一步" |
| 2 | 7 角色→3 角色的工程取舍 | [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 注释明写 tradeoff | "合并是为了避免角色间通信开销，ablation 证明 Critic 必须配套 Replanner 才有用" |
| 3 | ablation 消融实验 | [eval/runner.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) 4 组配置 | "不是堆组件，是实验验证每个组件的贡献度" |
| 4 | RAG 按需调用 | [prompts.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py) 决策规则"<5 条调 RAG" | "不同数据密度走不同路径，dense 跳过 RAG，sparse 才检索" |
| 5 | episodic memory 跨会话经验复用 | [rag.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/rag.py) episodic collection | "第二次跑同日期会参考历史 run 的工具调用顺序" |
| 6 | 人在回路工程化 | [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) threading.Event + 5min 超时 + 前端弹窗 | "不是 demo，是生产可用的异常处理" |
| 7 | classify 用确定性元数据而非 LLM | [tools.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) 注释"再调 LLM 是浪费" | "体现'并非每步都需要 LLM'的工程判断" |
| 8 | 国产大模型 DeepSeek | 技术栈表 | "用国产模型而非 OpenAI，符合国产化替代趋势" |
| 9 | state DB 持久化支持多 worker | [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) save_state/get_state | "gunicorn 重启不丢状态" |
| 10 | 完整测试 + CI | 179 测试 + GitHub Actions | "82% 覆盖率，CI 自动跑" |

### 2.2 必须正视的硬伤（面试官会问）

| # | 硬伤 | 位置 | 严重度 | 面试官怎么问 |
|---|------|------|--------|--------------|
| 1 | 多 worker 下 `_RUN_CACHE`/`_WAIT_EVENTS` 不共享 | [core.py:49](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) | 🔴 高 | "Agent 跑一半换 worker，前端轮询还能拿到状态吗？人在回路弹窗还能提交吗？" |
| 2 | LLM 无重试/退避 | [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) | 🟡 中 | "DeepSeek 限流了怎么办？整个 run 就失败？" |
| 3 | ablation 不可重现（temp=0.3） | [runner.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) | 🟡 中 | "同一组配置跑两次结果一样吗？结论统计意义够吗？" |
| 4 | 数据量小（33 条） | DB | 🟡 中 | "33 条政策，ablation 结论可信吗？" |
| 5 | RAG 用 all-MiniLM-L6-v2，中文效果有限 | [rag.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/rag.py) | 🟡 中 | "中文政策用这个 embedding，测过 BGE-zh 吗？" |
| 6 | report 模块测试 | [report/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/tests.py) | 🟢 低 | "爬虫和导出有测试吗？"（实际有 21 个，但 audit 误记为 0） |
| 7 | 无 token 刷新 | [frontend/src/api/index.js](file:///d:/work/project/Policy_Reporter/frontend/src/api/index.js) | 🟢 低 | "access token 2h 过期后怎么办？" |

---

## 三、央企国企科技岗适配度分析

### 3.1 对口的地方（放大讲）

| 维度 | 对口点 | 简历怎么写 |
|------|--------|-----------|
| 技术栈 | Django + Vue + MySQL + Docker 是央企国企常见栈 | 直接写，国网/南网/银行科技子公司有市场 |
| 业务场景 | 政策日报、合规资讯 | "对应央企政策研究 / 合规管理 / 内部信息门户业务" |
| 国产化 | 用 DeepSeek（国产大模型） | "符合国产化替代趋势，可平滑替换为本地 Qwen/ChatGLM" |
| 工程思维 | tradeoff 注释 + ablation 实验 | "体现工程师思维而非调包侠，符合央企对'扎实'的偏好" |
| 端到端 | 爬虫→Agent→docx→前端→部署 | "能讲清楚端到端落地能力" |

### 3.2 必补的叙事缺口（不补会被问住）

| # | 缺口 | 风险 | 补救方式 |
|---|------|------|----------|
| 1 | **LLM 依赖公网 API** | 央企国企数据安全要求高，政策数据可能涉密/内部 | 简历加一句"可替换为本地 Qwen/ChatGLM 部署"；面试准备"内网部署改造方案"话术 |
| 2 | **无 RBAC/多租户** | 央企组织架构复杂，需按部门/角色授权 | 简历不写，但面试准备"若加 RBAC 怎么设计"的话术 |
| 3 | **无审计日志** | 央企要求操作可追溯 | 当前 AgentTrace 算半个审计日志，面试可讲"已具备 Agent 操作追溯能力，用户操作审计可扩展" |
| 4 | **无等保合规设计** | 央企系统需过等保 2.0 | 简历不写，面试准备"若过等保需补什么"的话术 |
| 5 | **数据库国产化适配未声明** | MySQL 在央企替代名单上 | 简历加一句"数据库层可迁移到达梦/人大金仓（Django ORM 屏蔽方言）" |
| 6 | **无 SSO/LDAP 集成** | 央企需与 OA/内部门户集成 | 简历不写，面试准备"可对接企业 SSO/LDAP"的话术 |

> **关键判断**：1-5 不需要真的实现，但简历描述 + 面试话术必须准备好，否则被问到就卡壳。

---

## 四、缺失项清单（按优先级）

### 4.1 必补（影响简历可信度）

| # | 缺失 | 影响 | 建议 |
|---|------|------|------|
| 1 | **PROJECT_AUDIT.md 未更新已修复的 P0/P1** | 面试官看 audit 误以为还有硬伤 | 更新 audit 文档，标记已修复项 |
| 2 | **未跑过完整 eval 并出 ablation 对比表** | 简历写"ablation 实验"但无数据 | 跑一次 `run_eval`，把对比表放 README |
| 3 | **README 无在线 demo 链接** | 央企 HR 可能点链接看 | 加服务器 IP（已部署） |
| 4 | **无架构图（正式版）** | PROJECT_SUMMARY 只有 ASCII | 画一张 draw.io 图放 README |

### 4.2 建议补（加分项）

| # | 缺失 | 影响 | 建议 |
|---|------|------|------|
| 5 | **无 LLM 重试/退避** | 面试被问"限流怎么办" | core.py 加 tenacity 重试 |
| 6 | **无 token 预算管理** | 长 run 可能撑爆 context | prompts.py 加 token 计数 + 截断 |
| 7 | **TOOLS_DESCRIPTION 过时** | rag_search 描述写"当前返回空"，实际已实现 | 改 tools.py L9 描述 |
| 8 | **report/models.py 重复 import** | audit P1 #13 未修 | 删 L4 重复的 `from django.db import models` |

### 4.3 可不补（不影响央企国企面试）

| # | 缺失 | 原因 |
|---|------|------|
| 9 | Redis 共享层 | 面试准备话术即可，不必真实现 |
| 10 | Celery 异步 | 同上 |
| 11 | 等保 2.0 设计 | 简历不写，面试准备话术 |
| 12 | RBAC 实现 | 同上 |
| 13 | BGE-zh embedding 替换 | 面试准备"测过 all-MiniLM-L6-v2，BGE-zh 是改进方向"即可 |

---

## 五、冗余项清单

| # | 冗余 | 位置 | 处理 |
|---|------|------|------|
| 1 | `_has_docx_trace` 重复定义 | [views.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/views.py) 和 [metrics.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/metrics.py) | 抽到 utils |
| 2 | `config_policy_spider/` 目录 | 项目根 | Scrapy 版爬虫，已被 `report/management/commands/crawl_policies.py` 替代，建议删或归档 |
| 3 | `PROJECT_SUMMARY.md` Phase 6 待办 | 大量未完成项 | 已被 TODO_ROADMAP.md 取代，建议更新或归档 |
| 4 | `PROJECT_AUDIT.md` P0/P1 清单 | 已修复但文档未更新 | 更新状态 |
| 5 | `TODO_ROADMAP.md` Phase B | 已跳过合并到 D3 | 可删 B 章节 |

> **注**：冗余项不紧急，但代码 review 时会被指出。建议面试前清理 `config_policy_spider/`（最显眼的冗余）。

---

## 六、偏离重点之处

### 6.1 偏离：过度关注 eval 框架，数据量撑不起统计意义

**现象**：eval 框架做得完整（4 ablation × 6 场景 + LLM-judge + Markdown 报告），但 DB 只有 33 条政策，ablation 结论的统计意义薄弱。

**风险**：面试官问"33 条数据，ablation 结论可信吗？"会卡壳。

**建议**：
- 简历上弱化 ablation 的"统计意义"，强调"工程化能力"（能搭出 eval 框架本身就是能力）
- 准备话术："数据量确实有限，ablation 更大的价值是验证组件设计的合理性，而非追求统计显著性。后续扩数据后会做多 seed 平均"
- **不要**在简历写"统计显著"等词

### 6.2 偏离：episodic memory 的 key_decisions 信息量不足

**现象**：[core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 存经验时 `key_decisions=[a[0] for a in state.last_actions]` 只存工具名，丢了 params。

**风险**：面试官问"经验怎么复用？params 丢了不就废了？"会卡壳。

**建议**：
- 修改 core.py 存完整 `(tool, params)` 而非仅 tool name
- 或面试话术："当前存的是工具调用序列，params 可扩展存储"

### 6.3 偏离：前端 UI 精致度高于业务必要性

**现象**：Home.vue 547 行，深色渐变 + glassmorphism + SVG 图标，视觉完成度高，但对央企国企简历不是核心卖点。

**风险**：央企国企更看重后端/架构/业务，前端太精致可能被问"前端花的时间是不是比 Agent 多？"

**建议**：
- 简历上前端一笔带过（"Vue 3 + Element Plus 前端，支持 Agent 运行可视化与人在回路交互"）
- **不要**在简历放 UI 截图（除非 HR 岗位）
- 把时间叙事重心放在 Agent + 工程化

### 6.4 偏离：HTTPS 跳过可能被问

**现象**：用 IP 访问无 HTTPS，浏览器提示"不安全"。

**风险**：央企国企对安全敏感，HR 点链接看到"不安全"可能减分。

**建议**：
- 简历不提 HTTPS
- 面试若被问，答"当前是 IP 访问 demo，生产部署会用 Let's Encrypt + 域名"
- **如果时间允许**，花 1 小时配个 Cloudflare Tunnel 免费HTTPS（可选）

---

## 七、改进建议（按优先级排序）

### P0：必做（面试前）

1. **更新 PROJECT_AUDIT.md**：标记 P0/P1 已修复项（约 30 分钟）
2. **跑一次完整 eval**：`python manage.py run_eval --ablation`，把对比表放 README（约 1 小时，含等待）
3. **画架构图**：draw.io 画一张正式架构图，导出 PNG 放 README（约 1 小时）
4. **补央企国企话术文档**：写一份"内网部署改造方案"（Redis + 本地 LLM + 达梦 + RBAC + 审计），面试时口头答（约 1 小时）

### P1：建议做（加分）

5. **修 TOOLS_DESCRIPTION 过时描述**：tools.py L9 改"检索历史相似政策"（5 分钟）
6. **修 report/models.py 重复 import**：删 L4（1 分钟）
7. **加 LLM 重试**：core.py 用 tenacity 加 3 次重试 + 指数退避（30 分钟）
8. **删 config_policy_spider/ 目录**：归档到 `archive/` 或直接删（5 分钟）

### P2：可不做（话术准备即可）

9. Redis 共享层
10. Celery 异步
11. BGE-zh embedding
12. RBAC 实现
13. 等保 2.0 设计

---

## 八、简历包装建议（央企国企科技岗定向）

### 8.1 简历项目卡片模板

```
财税政策日报 Agent | 个人项目 | 2026.07-2026.08
技术栈：DeepSeek（国产大模型，可替换本地 Qwen）+ Django 5.2 + Vue 3 + MySQL + Docker

• 基于 ReAct 范式自研 Agent 框架（Actuator/Critic/Replanner/Terminator），
  动态编排 10 个工具生成政策日报，非固定流水线
• 完整实现 Thought-Action-Observation 循环，LLM 基于上一步工具返回决策
• 设计 4 组消融实验验证组件贡献度，发现 Critic 必须配套 Replanner 才能转化诊断为修复
• RAG 按需调用 + episodic memory 跨会话经验复用，不同数据密度走不同路径
• state 持久化到 DB 支持 gunicorn 多 worker，人在回路工程化（5min 超时兜底）
• 179 个单元测试，覆盖率 82%，GitHub Actions CI 自动化
• 部署于云服务器，Docker Compose 三容器编排，admin IP 白名单 + fail2ban 加固
• 数据库层可迁移到达梦/人大金仓（Django ORM 屏蔽方言），支持国产化适配

在线 demo：http://服务器IP | GitHub：shirleyyshi/policy_reporter
```

### 8.2 面试高频问题预案

| 问题 | 回答要点 |
|------|----------|
| "为什么用 DeepSeek 不用 Qwen/ChatGLM？" | "DeepSeek 性价比高且国产；架构上 LLM 调用封装在 tools.py，可平滑替换为本地 Qwen 部署" |
| "政策数据如果涉密，调外部 API 怎么办？" | "可改为本地 Qwen/ChatGLM 部署，tools.py 的 OpenAI client 已封装，替换 client 即可" |
| "多 worker 下 state 怎么共享？" | "当前用 DB 持久化 + 内存 cache 双层，DB 层支持跨 worker；若加 Redis 共享层可进一步优化人在回路同步" |
| "为什么不用 LangChain？" | "自研 ReAct < 200 行核心逻辑，LangChain 抽象层重且调试难；自研便于 ablation 实验精确控制每个组件" |
| "ablation 结论可信吗？数据量这么少" | "数据量有限，ablation 更大价值是验证组件设计合理性；后续扩数据会做多 seed 平均" |
| "能换成达梦数据库吗？" | "Django ORM 屏蔽方言，只需改 DATABASE_URL + 迁移 schema，业务代码零改动" |
| "过等保了吗？" | "当前是个人项目未过等保；若部署到央企内网，会补审计日志 + 数据分级 + RBAC" |
| "RAG 用 all-MiniLM-L6-v2 对中文效果如何？" | "多语言模型基础可用；改进方向是 BGE-zh 或 m3e-base，已预留 embedding 模型可配置接口" |

### 8.3 不要在简历写的话

- ❌ "统计显著"（数据量撑不起）
- ❌ "生产级"（个人项目不算）
- ❌ "高并发"（没压测过）
- ❌ "微服务"（单体 Docker Compose）
- ❌ "全栈"（前端不是亮点）
- ❌ "LangChain"（没用，写了会被问）

---

## 九、结论

**作为央企国企科技岗（非大厂开发）的简历项目，够用**，但需要：

1. **必补**：跑一次 eval 出数据 + 画架构图 + 更新 audit 文档 + 准备央企话术（约半天）
2. **叙事调整**：强调"国产化可适配"+"工程严谨度"+"业务场景对口"，弱化"统计意义"+"前端精致度"
3. **话术准备**：多 worker / 数据量 / 国产化 / 等保 / RBAC 五个必问点，准备好"若部署到央企内网如何改造"的答案

**核心判断**：这个项目的 AI Agent 成色和工程严谨度，在央企国企科技岗求职池里属于上游。短板是企业级特性缺失，但这些可以通过话术弥补，不需要真实现。**建议先做 P0 的四项，然后进入 Phase E 简历素材整理。**
