# 央企国企面试话术：内网部署改造方案

> 面试时如果被问到"如果部署到央企内网怎么改造"，按以下方案口头回答。
> 不需要真实现，但必须答得有理有据。

---

## 一、五个必问点 + 标准回答

### Q1："政策数据如果涉密，调外部 DeepSeek API 怎么办？"

**回答要点**：
> "架构上 LLM 调用封装在 `tools.py` 的 `_openai_client`，只暴露 `chat.completions.create` 一个接口。部署到央企内网时，把 DeepSeek 替换为本地 Qwen-72B 或 ChatGLM-3 部署（vLLM 推理框架提供 OpenAI 兼容 API），只改 `DEEPSEEK_BASE_URL` 指向内网地址，业务代码零改动。"
>
> "具体来说，`settings.py` 的 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_API_KEY` 都是环境变量配置的。内网部署时 BASE_URL 改成 `http://内网GPU服务器:8000/v1`，API_KEY 用内网鉴权 token 即可。"

**技术细节（追问时补充）**：
- vLLM 支持 OpenAI 兼容 API，替换成本约 1 天
- Qwen-72B 需要 2×A100 80G 或 4×A800 40G
- 如果算力有限，Qwen-14B 也能用，效果略降但部署成本低

---

### Q2："多 worker 下 Agent 状态怎么共享？人在回路怎么同步？"

**回答要点**：
> "当前用 DB 持久化 + 内存 cache 双层设计。DB 层（`AgentRun.state_json`）已经支持跨 worker 读取状态，`get_state` 方法会先查内存 cache 再回退 DB。唯一未根治的是人在回路的 `threading.Event` 是进程内的，跨 worker 不同步。"
>
> "内网部署改造方案：加 Redis 共享层。把 `_RUN_CACHE`、`_WAIT_EVENTS`、`_HUMAN_ANSWERS` 三个 dict 迁移到 Redis，`threading.Event` 替换为 Redis pub/sub 或 Redis 的 `BLPOP` 阻塞读。改动集中在 `core.py` 的 3 个全局变量，约半天工作量。"

**技术细节**：
- Redis key 设计：`agent:run:{run_id}:state` / `agent:run:{run_id}:wait` / `agent:run:{run_id}:answer`
- 人在回路用 `BLPOP` 5 分钟超时替代 `threading.Event.wait(300)`
- State 序列化已有 `_serialize_state`，直接存 Redis string

---

### Q3："数据库能换成达梦/人大金仓吗？"

**回答要点**：
> "Django ORM 屏蔽了数据库方言，业务代码零改动。只需改 `DATABASE_URL` 指向达梦/人大金仓，装对应的 Python 驱动（dmPython 或 kingbase8），Django 用 `django-dm` 或 `django-kingbase` backend。"
>
> "唯一需要注意的是 MySQL 特有的 `utf8mb4_unicode_ci` 排序规则在达梦里对应 `GB18030`，migration 文件里的 `db_table` 名称可能需要大写（达梦默认大写表名）。这些都是配置层改动，不涉及业务逻辑。"

**技术细节**：
- 达梦：`pip install dmPython`，DATABASE_URL 改 `dm://user:pass@host:port/dbname`
- 人大金仓：`pip install kingbase8`，DATABASE_URL 改 `kingbase://user:pass@host:port/dbname`
- ChromaDB 是嵌入式 SQLite 向量库，不受影响

---

### Q4："过等保 2.0 需要补什么？"

**回答要点**：
> "当前项目已有 JWT 认证、admin IP 白名单、fail2ban SSH 防护、DB 定时备份。过等保 2.0 三级还需补充：
> 1. **审计日志**：当前 `AgentTrace` 记录的是 Agent 操作步骤，需加用户操作审计（登录/导出/删除），用 Django `django-auditlog` 或自建 `AuditLog` 表
> 2. **数据分级**：政策数据标注密级（公开/内部/秘密），`CentralPolicy` 加 `security_level` 字段，导出时按密级脱敏
> 3. **RBAC**：加角色权限（管理员/编辑/只读），用 `django-guardian` 做对象级权限
> 4. **传输加密**：加 HTTPS（Let's Encrypt 或央企 CA 证书）
> 5. **安全标记**：`SECURE_SSL_REDIRECT` / `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` / `HSTS`"

**技术细节**：
- 审计日志：`django-auditlog` 自动记录 CRUD 操作，约半天
- RBAC：`django-guardian` 对象级权限，约 1 天
- 数据分级：model 加字段 + 导出时 filter，约半天

---

### Q5："ablation 结论可信吗？数据量这么少"

**回答要点**：
> "数据量确实有限，ablation 更大的价值是验证组件设计的合理性，而非追求统计显著性。比如 no_critic 配置下 success_rate 下降，能说明 Critic 有作用；no_replanner 配置下 Critic 触发率不降但建议重规划率转化不了改进行动，能说明 Critic 必须配套 Replanner。（这个指标原来叫'修复率'，我后来改成了'建议重规划率'——建议不等于修复，命名应该跟统计口径一致。）"
>
> "后续扩数据后会做多 seed 平均 + 方差分析。当前 Actuator temperature=0.3 有随机性，但 Critic temperature=0 是确定性的，所以 Critic 相关的结论相对稳定。"

**不要说的话**：
- ❌ "统计显著"（数据量撑不起）
- ❌ "P值小于0.05"（没算过）

---

## 二、反向问题（问面试官加分）

面试官问完技术问题后，通常会问"你有什么问题想问我们？"，这时可以问：

1. "你们 Agent 的 trace 是入 DB 还是只写日志？eval 时怎么聚合统计？"
   - 展示你对 Agent 可观测性的重视

2. "你们用国产大模型还是 OpenAI？内网部署用的什么推理框架？"
   - 展示国产化适配意识

3. "你们的系统过等保了吗？哪一级？审计日志怎么做的？"
   - 展示企业级安全意识

4. "你们 Agent 的工具是 LLM 决策调用还是固定流水线？有没有做过消融实验？"
   - 展示你区分"真 Agent"和"LLM Chain"的能力

---

## 三、简历项目卡片（央企国企定向）

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

---

## 四、不要在简历写的话

- ❌ "统计显著"（数据量撑不起）
- ❌ "生产级"（个人项目不算）
- ❌ "高并发"（没压测过）
- ❌ "微服务"（单体 Docker Compose）
- ❌ "全栈"（前端不是亮点）
- ❌ "LangChain"（没用，写了会被问）
- ❌ "使用了先进的 LLM 技术"（空话）
- ❌ "支持高并发"（面试官追问会翻车）
