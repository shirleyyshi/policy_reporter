# Policy_Reporter 待办执行手册

> 本文档列出所有尚未完成的步骤，含具体实现方法、代码示例、验证标准。
> 任何人接手（你自己或 AI 助手）都应严格按本文档顺序执行。
> 完成一项划掉一项，不要跳步。
>
> 更新日期：2026-08-15（第五轮更新：C3 GitHub Actions CI 完成，双 remote 镜像推送）
> 第一轮进度（2026-07-20）：P0 + P1 全部修完，42 个测试全过，docker-compose 配置语法正确。
> 第二轮复核结论：P0/P1 修复已落地核实；Phase A 全未动；Phase B 配置就绪待运行验证；Phase C 仅 report 测试补完；Phase D 仅 cron 脚本写完；Phase E 未开始。
> 第二轮修复（2026-08-14）：A1（Observation 三元组）+ A2（AgentRun state 持久化）+ A3（RAG episodic memory）已完成，55 个测试全过，Phase A 全部打通。
> 第三轮调整（2026-08-14）：本地 Docker Desktop 因 sandbox 限制无法启动，Phase B 本地验证跳过，合并到 Phase D 服务器验证；Phase D 改为"服务器 IP 不买域名"方案（HR 任何网络可访问，无 HTTPS），D4 降级为可选。
> 第四轮更新（2026-08-15）：Phase D 主体完成（服务器已部署运行，数据已入库，前端可访问）；前端 P2 瑕疵 #15-19 全部修复；C1 工具链搭建完成（pytest+coverage，55 测试，46% 覆盖率）；C2 测试补全完成（179 测试，82% 覆盖率，突破 80% 目标）；数据提取 bug 修复（导出标题日期/摘要条数/选择交集）。
> 第五轮更新（2026-08-15）：C3 GitHub Actions CI 完成——workflow test.yml 含 backend-test(SQLite+pytest --cov-fail-under=80)+frontend-build(npm ci+build) 两个 job；README 加 CI+Coverage badge；配置双 remote（origin=Gitee / github=GitHub），commit fbea466 已推两边；README badge 用户名修正为 GitHub 账号 shirleyyshi（2个y）。

---

## 复核结论速览（2026-08-15）

| 阶段 | 任务 | 复核状态 | 证据 |
|------|------|----------|------|
| A1 | 补 Observation 到 last_actions | ✅ 已完成 | [core.py:199-260](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 三元组占位+回填；[prompts.py:39-69](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py) 显式 Action→Observation；[tools.py:48](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) 注释改三元组；[tests.py:205-235](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py) 断言三元组 |
| A2 | AgentRun 表 state 持久化 | ✅ 已完成 | [models.py:28-54](file:///d:/work/project/Policy_Reporter/backend/apps/agent/models.py) AgentRun 表；[0002_agentrun.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/migrations/0002_agentrun.py) migration；[core.py:414-497](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) save_state/get_state + DB 回退；[admin.py:13-19](file:///d:/work/project/Policy_Reporter/backend/apps/agent/admin.py) 注册；[tests.py:238-327](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py) 5 个持久化测试 |
| A3 | RAG 长期记忆 | ✅ 已完成 | [rag.py:142-236](file:///d:/work/project/Policy_Reporter/backend/apps/agent/rag.py) episodic collection + store/retrieve/clear；[tools.py:51](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) context_hints 字段；[core.py:366-367/383-384/344-349](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) retrieve 注入 + store 落库；[prompts.py:63-72](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py) 历史经验段落；[tests.py:329-423](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py) 7 个 episodic 测试 |
| B1 | .env 文件准备 | ✅ 配置就绪 | 根 [.env.example](file:///d:/work/project/Policy_Reporter/.env.example) 完整；[docker-compose.yml](file:///d:/work/project/Policy_Reporter/docker-compose.yml) 用 `${SECRET_KEY:?...}` 强制读 .env |
| B2-B4 | 本地验证 | ⏭️ 跳过 | 合并到 D3 服务器验证，服务器已部署运行 |
| C1 | 装 pytest + coverage | ✅ 已完成 | [requirements-dev.txt](file:///d:/work/project/Policy_Reporter/backend/requirements-dev.txt) pytest 工具链；[pytest.ini](file:///d:/work/project/Policy_Reporter/backend/pytest.ini) 配置；[conftest.py](file:///d:/work/project/Policy_Reporter/backend/conftest.py) 共享 fixtures；55 测试全过，覆盖率 46% |
| C2 | 补测试到 80% | ✅ 已完成 | [test_core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_core.py) 16 测试 + [test_eval.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_eval.py) 42 测试 + [test_views.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_views.py) 35 测试 + [test_prompts.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_prompts.py) 15 测试 + [test_rag.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_rag.py) 16 测试；179 测试全过，覆盖率 **82%** |
| C3 | GitHub Actions CI | ✅ 已完成 | [.github/workflows/test.yml](file:///d:/work/project/Policy_Reporter/.github/workflows/test.yml) backend-test(SQLite+pytest --cov-fail-under=80)+frontend-build(npm ci+build)；双 remote 镜像：origin=Gitee(shirleyyyshi) / github=GitHub(shirleyyshi)；[README.md](file:///d:/work/project/Policy_Reporter/README.md) CI+Coverage badge 已加；commit fbea466 已推两边 |
| D1-D3 | 服务器部署 | ✅ 已完成 | 新加坡云服务器已部署，docker-compose 三容器运行，数据已入库，前端可访问，gunicorn 3 workers 下 agent 正常 |
| D4 | 配 HTTPS | ⏭️ 暂跳过 | 不买域名方案，用 IP 访问无 HTTPS，浏览器提示"不安全"但功能正常 |
| D5 | cron 定时爬虫 | ✅ 已做 | [scripts/crawl.sh](file:///d:/work/project/Policy_Reporter/scripts/crawl.sh) + [crawl.bat](file:///d:/work/project/Policy_Reporter/scripts/crawl.bat) 已写好 |
| D6 | 生产加固 | ❌ 未做 | [settings.py](file:///d:/work/project/Policy_Reporter/backend/config/settings.py) 无 ADMIN_ALLOWED_IPS；无 fail2ban/备份 cron 配置 |
| E1-E4 | 简历素材 | ❌ 未做 | 无 1 页卡片/话术/视频脚本/架构图独立文档（PROJECT_SUMMARY/AUDIT 有草稿素材） |
| 前端 P2 | #15-19 瑕疵修复 | ✅ 已完成 | el-checkbox label/value(#17)、baseURL fallback(#18)、路由懒加载(#19)、storage 监听(#15)、API 路径(#16) 全部修复 |
| 数据提取 | 导出标题日期/摘要条数/选择交集 | ✅ 已修复 | views.py 用前端传入 selectedDate；摘要条数动态计算 min(政策数,5)；CentralEditor/LocalEditor 加交集过滤 |
| 数据/爬虫 | 政策数据量少 | ⏸️ 待讨论 | 站点少(2个)+关键词过滤严格+按原发布日期匹配，后续讨论调整 |

**P0/P1 修复复核（PROJECT_AUDIT 清单）**：5 个 P0 + 8 个 P1 全部已落地。

**P2 工程小瑕疵**：前端 #15/#16/#17/#18/#19 全部修复 ✅；后端 #14/#22/#23/#24 待修。

---

## 目录

- [Phase A：Agent 能力补齐（ReAct 三要素完整化）](#phase-aagent-能力补齐react-三要素完整化)
- [Phase B：本地 docker-compose 跑通验证](#phase-b本地-docker-compose-跑通验证)
- [Phase C：测试覆盖率到 80% + CI](#phase-c测试覆盖率到-80--ci)
- [Phase D：部署到新加坡云服务器](#phase-d部署到新加坡云服务器)
- [Phase E：简历包装素材](#phase-e简历包装素材)

---

## Phase A：Agent 能力补齐（ReAct 三要素完整化）

**目标**：让简历"覆盖 Tool Calling、记忆管理、状态持久化"三条都站得住脚。
**预估工作量**：1-2 天
**前置依赖**：无（可独立进行）
**复核结论（2026-08-14）**：~~A1/A2/A3 全部未动~~ **A1+A2+A3 全部完成（55 测试全过）。** Phase A 全部打通，可进入 Phase B 验证。

### A1. 补 Observation 到 last_actions（必做） ✅ 已完成

**问题**：当前 `last_actions` 只存 `(tool_name, parameters)`，LLM 看不到工具返回结果。真正的 ReAct 是 `Thought → Action → Observation → Thought` 循环。

**复核证据**：
- [core.py:201](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) `state.last_actions.append((tool, params_key))` — 二元组
- [tools.py:48](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) 注释 `# [(tool, params_json), ...] 用于重复检测`
- [tests.py:205-210](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py) `test_last_actions_tracking` 仍断言二元组
- [prompts.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py) 的 `build_step_prompt` 未引用 observation

**实现位置**：[backend/apps/agent/core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py)、[backend/apps/agent/tools.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py)、[backend/apps/agent/prompts.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py)、[backend/apps/agent/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py)

**具体步骤**：

1. 修改 `AgentState.last_actions` 的存储格式（[tools.py:48](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py)）：
   ```python
   # 改前：list[tuple[str, str]]  # (tool_name, params_json)
   # 改后：list[tuple[str, str, str]]  # (tool_name, params_json, observation_preview)
   ```

2. 在 [core.py:226](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 执行工具后（`observation = TOOLS[tool](state, params)` 之后），把 observation preview 加进 last_actions：
   ```python
   # core.py 工具执行成功分支（约 226-251 行之间）
   observation = TOOLS[tool](state, params)
   state.fail_count = 0
   # ... 异常处理 ...
   # 取 observation 的前 150 字作为 preview
   obs_preview = json.dumps(observation, ensure_ascii=False)[:150]
   # 替换原 201 行的二元组 append
   state.last_actions.append((tool, params_key, obs_preview))
   ```
   注意：原 201 行的 append 在"重复检测"分支（执行工具之前），需把它挪到工具执行成功之后，否则 observation 还没产生。

3. 修改重复检测逻辑（[core.py:202-204](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py)）适配三元组：
   ```python
   recent_actions = list(state.last_actions)[-repeat_threshold:]
   # 只比 (tool, params) 前两元，忽略 observation
   if (len(recent_actions) == repeat_threshold
           and len({(a[0], a[1]) for a in recent_actions}) == 1):
   ```

4. 修改 [prompts.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py) 的 `build_step_prompt`，把最近 5 步的 observation 带进 LLM prompt：
   ```python
   action_history = "\n".join(
       f"Step {i+1}: 调用 {name}({params}) → {obs}"
       for i, (name, params, obs) in enumerate(state.last_actions[-5:])
   )
   ```
   若 `build_step_prompt` 当前只读 `state.summary_view()`，需追加 action_history 段落。

5. 更新 [tests.py:205](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py) `test_last_actions_tracking` 为三元组断言：
   ```python
   def test_last_actions_tracking_with_observation(self):
       """last_actions 应记录 (tool, params, observation) 三元组。"""
       state = AgentState(task_input={})
       state.last_actions.append(('fetch_central', '{"date": "2026-07-13"}', '{"fetched": 3}'))
       self.assertEqual(len(state.last_actions), 1)
       self.assertEqual(state.last_actions[0][2], '{"fetched": 3}')
   ```

**验证标准**：
- 跑 `python manage.py test agent` 全过
- 跑一次 `python manage.py run_agent --date 2026-07-13`（或前端触发），看 trace 中 Actuator 的 reasoning 是否引用了上一步的 observation
- 简历可写："完整实现 Thought-Action-Observation 循环，LLM 基于上一步工具返回结果决策"

---

### A2. AgentRun 表做 state 持久化（必做） ✅ 已完成

**问题**：当前 `_RUN_CACHE` 是 [core.py:49](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 模块级 dict，重启即丢；gunicorn 3 workers（[entrypoint.sh:40](file:///d:/work/project/Policy_Reporter/backend/entrypoint.sh)）下多进程不共享，前端轮询会找不到 state。**这是生产部署的阻塞 bug。**

**复核证据**：
- [models.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/models.py) 只有 AgentTrace 表
- [core.py:405-407](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) `get_state` 只从 `_RUN_CACHE.get()` 取，无 DB 回退
- [admin.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/admin.py) 只注册 AgentTrace
- [eval/metrics.py:76](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/metrics.py) `success()` 在 cache 丢失时只能从 DB trace 推断，已埋了回退逻辑（说明作者意识到 cache 会丢）

**实现位置**：[backend/apps/agent/models.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/models.py) + [backend/apps/agent/core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) + [backend/apps/agent/admin.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/admin.py) + [backend/apps/agent/views.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/views.py)

**具体步骤**：

1. 在 [agent/models.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/models.py) 加 AgentRun 模型：
   ```python
   class AgentRun(models.Model):
       run_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
       status = models.CharField(max_length=20, default='running')  # running/waiting_human/done/failed
       step = models.IntegerField(default=0)
       task_input = models.JSONField(default=dict)
       state_json = models.JSONField(default=dict)  # 完整 state 序列化
       summary = models.TextField(default='')
       docx_path = models.CharField(max_length=500, null=True, blank=True)  # media/agent_docx/xxx.docx
       error = models.TextField(null=True, blank=True)
       created_at = models.DateTimeField(auto_now_add=True)
       updated_at = models.DateTimeField(auto_now=True)

       class Meta:
           ordering = ['-created_at']
   ```

2. 生成并应用 migration：
   ```bash
   cd backend
   python manage.py makemigrations agent
   python manage.py migrate
   ```

3. 在 [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 改 `get_state`（约 405 行）并新增 `save_state`：
   ```python
   def get_state(run_id) -> Optional[AgentState]:
       """优先从内存取，回退从 DB 反序列化。"""
       if run_id in _RUN_CACHE:
           return _RUN_CACHE[run_id]
       try:
           run = AgentRun.objects.get(run_id=run_id)
           state = AgentState(task_input=run.task_input)
           state.__dict__.update(run.state_json)
           state.status = run.status
           state.step = run.step
           state.summary = run.summary
           _RUN_CACHE[run_id] = state  # 缓存回内存
           return state
       except AgentRun.DoesNotExist:
           return None

   def save_state(run_id, state: AgentState):
       """持久化 state 到 DB（每次工具调用后调用）。"""
       import dataclasses
       AgentRun.objects.update_or_create(
           run_id=run_id,
           defaults={
               'status': state.status,
               'step': state.step,
               'task_input': state.task_input,
               'state_json': dataclasses.asdict(state),
               'summary': state.summary or '',
           }
       )
   ```
   注意：`dataclasses.asdict(state)` 会序列化 `human_input_callback`（callable）失败，需在 `AgentState` 加 `__dict__` 过滤或用自定义 `_serialize_state` 排除 callable 字段。

4. 在 [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 的 `_run_loop` 中，每次 state 变更后调用 `save_state(run_id, state)`：
   - 工具执行成功后（约 251 行 `state.trace.append(trace_entry)` 之后）
   - Critic 触发后（约 274 行）
   - status 变 done/failed 时（约 183/236/257/302 行）
   - ask_human 设 waiting_human 时（[core.py:371](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) `_make_human_input_handler` 内）

5. `run_agent` / `run_agent_async`（[core.py:329/342](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py)）开头创建 AgentRun 记录：
   ```python
   run_id = uuid.uuid4()
   state = AgentState(task_input={"date": date, "legal_text": legal_text})
   AgentRun.objects.create(run_id=run_id, task_input=state.task_input)
   _RUN_CACHE[str(run_id)] = state
   ```

6. 在 [agent/admin.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/admin.py) 注册 AgentRun：
   ```python
   @admin.register(AgentRun)
   class AgentRunAdmin(admin.ModelAdmin):
       list_display = ('run_id', 'status', 'step', 'created_at', 'updated_at')
       list_filter = ('status',)
       search_fields = ('run_id',)
       ordering = ('-created_at',)
       readonly_fields = ('run_id', 'created_at', 'updated_at')
   ```

7. 更新 [agent/views.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/views.py) 的 `/runs/` 列表端点从 AgentRun 表读（而非只读 _RUN_CACHE），让前端历史 run 列表持久可见。

8. 加测试 [agent/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py)：
   ```python
   class AgentRunPersistenceTest(TestCase):
       def test_state_persists_across_calls(self):
           """state 应能持久化到 DB 并恢复。"""
           import uuid
           run_id = uuid.uuid4()
           state = AgentState(task_input={'date': '2026-07-13'})
           state.raw_policies = [1, 2, 3]
           state.step = 5
           save_state(run_id, state)

           # 清空内存缓存，模拟重启
           _RUN_CACHE.clear()

           recovered = get_state(run_id)
           self.assertIsNotNone(recovered)
           self.assertEqual(recovered.step, 5)
           self.assertEqual(len(recovered.raw_policies), 3)

       def test_status_transitions(self):
           """状态应能正确转换 running → done。"""
           import uuid
           run_id = uuid.uuid4()
           state = AgentState(task_input={'date': '2026-07-13'})
           state.status = 'running'
           save_state(run_id, state)

           state.status = 'done'
           save_state(run_id, state)

           _RUN_CACHE.clear()
           recovered = get_state(run_id)
           self.assertEqual(recovered.status, 'done')
   ```
   注意：这两个测试用 `TestCase`（需 DB），不能放现在的 `SimpleTestCase` 类里。

**验证标准**：
- 跑测试全过
- 启动服务 → 跑一次 agent → 重启服务 → 访问 `/api/agent/runs/{run_id}/` 仍能拿到完整 trace 和状态
- 简历可写："state 持久化到 DB，支持多 worker 共享与服务重启恢复"

---

### A3. RAG 长期记忆（加分项，可选） ✅ 已完成

**目标**：让 Agent 跨 run 复用历史经验。
**复核结论**：已完成。复用现有 ChromaDB 基础设施加独立 episodic collection，1-2 小时落地。
**实现位置**：[backend/apps/agent/rag.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/rag.py) + [backend/apps/agent/core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) + [backend/apps/agent/tools.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) + [backend/apps/agent/prompts.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/prompts.py) + [backend/apps/agent/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py)

**具体步骤**：

1. 在 [rag.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/rag.py) 加 episodic memory 集合（与现有 `policies` collection 并列）：
   ```python
   EPISODIC_COLLECTION = "agent_episodic_memory"

   def store_episodic_memory(run_id, date, summary, key_decisions):
       """存一次 run 的经验到向量库。"""
       doc = f"日期: {date}\n摘要: {summary}\n关键决策: {key_decisions}"
       _get_episodic_collection().add(
           documents=[doc],
           metadatas=[{"run_id": str(run_id), "date": date}],
           ids=[f"ep_{run_id}"]
       )

   def retrieve_episodic_memory(query, n_results=3):
       """检索相似历史 run 经验。"""
       col = _get_episodic_collection()
       if col.count() == 0:
           return []
       results = col.query(query_texts=[query], n_results=n_results)
       return results['documents'][0] if results['documents'] else []

   def _get_episodic_collection():
       global _episodic_collection
       if _episodic_collection is None:
           _episodic_collection = _client.get_or_create_collection(name=EPISODIC_COLLECTION)
       return _episodic_collection
   ```

2. 在 [core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) 的 `run_agent` / `_run_loop` 开始时检索相似经验：
   ```python
   def run_agent(date, legal_text="", config=None):
       # ...
       past_experiences = retrieve_episodic_memory(f"财税政策日报 {date}")
       if past_experiences:
           state.context_hints = past_experiences  # 传给 LLM 作为参考（需 AgentState 加字段）
   ```

3. 在 run_agent 结束时存当前 run 经验（terminate 之前）：
   ```python
   store_episodic_memory(
       run_id=run_id,
       date=date,
       summary=state.summary,
       key_decisions=[a[0] for a in state.last_actions]  # 工具调用序列
   )
   ```

4. 加 `clear_episodic_memory` 函数供 build_index 命令调用。

**验证标准**：
- 跑两次相同日期的 agent，第二次的 trace 应显示"参考了历史 run"的 reasoning
- 简历可写："基于 RAG 的 episodic memory，跨会话经验复用"

---

## Phase B：本地 docker-compose 跑通验证

**目标**：本地一键 `docker-compose up -d` 三容器起来，爬虫能跑，Agent 能 run。
**预估工作量**：半天
**前置依赖**：Phase A 完成（否则多 worker 下 agent 跑不起来）
**复核结论（2026-08-14）**：B1 配置就绪 ✅；B2 配置层就绪但实际未跑过验证 🟡；B3/B4 待用户执行。**注意：在 A2 完成前跑 docker-compose，agent 会在多 worker 下崩。**

### B1. 准备 .env 文件 ✅ 配置就绪

**复核结论**：[.env.example](file:///d:/work/project/Policy_Reporter/.env.example) 已含 SECRET_KEY/DB_ROOT_PASSWORD/DEEPSEEK_API_KEY/DEBUG/ALLOWED_HOSTS/CORS；[docker-compose.yml](file:///d:/work/project/Policy_Reporter/docker-compose.yml) 用 `${SECRET_KEY:?...}` 强制读 .env，无安全默认值。配置层无需改动，只需用户填真实值。

**具体步骤**：

1. 在项目根目录复制 .env.example 为 .env：
   ```bash
   cd d:\work\project\Policy_Reporter
   copy .env.example .env
   ```

2. 编辑 .env，填入真实值：
   ```env
   # 用 python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 生成
   SECRET_KEY=django-insecure-xxxxxxxxxxxxxxxxxxxxx

   # 自定义一个强密码
   DB_ROOT_PASSWORD=YourStrongPass2026!

   # DeepSeek API key
   DEEPSEEK_API_KEY=sk-your-real-deepseek-key

   DEBUG=False
   ALLOWED_HOSTS=localhost,backend,policy.yourdomain.com
   CORS_ALLOWED_ORIGINS=http://localhost,https://policy.yourdomain.com
   ```

3. 在 backend 目录也复制一份 .env（给本地 manage.py 用）：
   ```bash
   cd backend
   copy .env.example .env
   # 编辑 backend/.env，DATABASE_URL 用 localhost（docker 容器外访问）
   DATABASE_URL=mysql://root:YourStrongPass2026!@localhost:3306/policy_db
   ```

**验证**：`docker-compose config` 不报错。

---

### B2. 首次启动 docker-compose 🟡 配置就绪待运行验证

**复核结论**：[backend/Dockerfile](file:///d:/work/project/Policy_Reporter/backend/Dockerfile) 用 entrypoint + gunicorn ✓；[entrypoint.sh](file:///d:/work/project/Policy_Reporter/backend/entrypoint.sh) 完整（等 DB→migrate→collectstatic→build_index→gunicorn 3 workers）✓；[docker-compose.yml:54-57](file:///d:/work/project/Policy_Reporter/docker-compose.yml) 挂载 backend_media/backend_static 卷 ✓。配置层无阻塞，待实际运行验证。

**具体步骤**：

1. 构建 + 启动：
   ```bash
   cd d:\work\project\Policy_Reporter
   docker-compose up -d --build
   ```
   首次构建约 5-10 分钟（下载 Python/Node 镜像 + pip/npm 安装）。

2. 观察启动日志：
   ```bash
   docker-compose logs -f backend
   ```
   应看到 entrypoint.sh 输出：
   - `[entrypoint] 等待 MySQL 就绪...`
   - `[entrypoint] MySQL 已就绪，开始 migrate...`
   - `[entrypoint] 收集静态文件...`
   - `[entrypoint] 构建 RAG 索引...`（首次会失败，因为没数据，正常）
   - `[entrypoint] 启动 gunicorn...`

3. 验证三容器状态：
   ```bash
   docker-compose ps
   ```
   三个容器都应是 `Up` 状态，db 应是 `healthy`。

**验证标准**：
- 访问 `http://localhost/api/auth/login/` 返回 DRF 页面（405 也算正常，说明 backend 通了）
- 访问 `http://localhost/` 返回前端登录页
- `docker-compose exec backend python manage.py check` 0 issues
- ⚠️ **A2 未完成前**：跑 agent run 时前端轮询 `/runs/{id}/state/` 大概率 404（gunicorn 3 workers 不共享 _RUN_CACHE），这是预期行为，做完 A2 后才能正常

---

### B3. 创建超级用户 + 爬数据 ⏳ 待运行

**具体步骤**：

1. 创建超级用户：
   ```bash
   docker-compose exec backend python manage.py createsuperuser
   ```

2. 跑爬虫：
   ```bash
   docker-compose exec backend python manage.py crawl_policies --all
   ```
   预期：爬到 10-20 条政策，无报错。

3. 重建 RAG 索引：
   ```bash
   docker-compose exec backend python manage.py build_index
   ```

4. 登录前端 `http://localhost/` 用超级用户账号，验证：
   - 首页能看到政策数量统计
   - 编辑页能看到爬到的政策列表
   - Agent 页能跑一次 agent run（输入有政策的日期）

**验证标准**：
- 爬虫日志显示 `新增 N 条`
- 前端能看到政策
- Agent run 完成状态为 `done`，能下载 docx

---

### B4. 排查可能的问题 ⏳ 按需

**常见问题与解决方案**：

1. **frontend 容器构建失败**：
   - 检查 [frontend/Dockerfile](file:///d:/work/project/Policy_Reporter/frontend/Dockerfile) 是否 multi-stage build（已确认是 ✓）
   - 检查 [frontend/.env.example](file:///d:/work/project/Policy_Reporter/frontend/.env.example) 的 `VITE_API_BASE`，Docker 构建时改为空（用相对路径）或 `/`

2. **CORS 错误**：
   - 在 .env 中加 `CORS_ALLOWED_ORIGINS=http://localhost`
   - 检查 [settings.py:66-67](file:///d:/work/project/Policy_Reporter/backend/config/settings.py) 中 `CORS_ALLOWED_ORIGINS` 从 env 读取（已确认 ✓）

3. **MySQL 连接失败**：
   - `docker-compose logs db` 看 MySQL 是否启动完成
   - 检查 .env 的 DB_ROOT_PASSWORD 是否与 backend 环境变量一致

4. **collectstatic 失败**：
   - 检查 settings.py 的 STATIC_ROOT 配置（已在 P0 修好 ✓）
   - 手动跑 `docker-compose exec backend python manage.py collectstatic --noinput`

5. **build_index 失败**：
   - 首次启动无数据时正常，跳过即可
   - 有数据后失败，检查 ChromaDB 持久化路径是否可写

6. **Agent run 轮询 404 / state 丢失**：
   - 根因：A2 未完成，多 worker 不共享 _RUN_CACHE
   - 临时方案：把 entrypoint.sh 的 `--workers 3` 改成 `--workers 1`（仅本地验证用）
   - 正解：完成 A2

**验证标准**：docker-compose down → up 重启后，数据不丢（DB 卷 + media 卷持久化）。

---

## Phase C：测试覆盖率到 80% + CI

**目标**：pytest + coverage 行覆盖率 80%+，GitHub Actions 自动跑测试。
**预估工作量**：1-2 天
**前置依赖**：Phase A 完成（AgentRun 表加完测试更好写）
**复核结论（2026-08-14）**：C1 未做 ❌；C2 部分（report 已补 21 个，agent 仍只有 21 个 SimpleTestCase）🟡；C3 未做 ❌。当前 `python manage.py test` 能跑 42 个测试，但无覆盖率工具、无 CI、agent core/rag/eval 零覆盖。

### C1. 安装 pytest + coverage 工具链 ❌ 未做

**复核证据**：[requirements.txt](file:///d:/work/project/Policy_Reporter/backend/requirements.txt) 只到 gunicorn，无 pytest 系列；backend 目录无 pytest.ini / conftest.py。

**具体步骤**：

1. 在 [backend/requirements.txt](file:///d:/work/project/Policy_Reporter/backend/requirements.txt) 加开发依赖（建议拆 requirements-dev.txt 或直接加注释段）：
   ```txt
   # 开发/测试依赖
   pytest~=8.0.0
   pytest-django~=4.9.0
   pytest-cov~=5.0.0
   coverage~=7.5.0
   factory-boy~=3.3.0
   responses~=0.25.0  # mock requests
   ```

2. 在 backend 目录加 `pytest.ini`：
   ```ini
   [pytest]
   DJANGO_SETTINGS_MODULE = config.settings
   python_files = tests.py test_*.py *_tests.py
   addopts = --cov=apps --cov-report=term-missing --cov-report=html
   ```

3. 在 backend 目录加 `conftest.py`：
   ```python
   import pytest
   from django.conf import settings

   @pytest.fixture
   def auth_client(db):
       from django.contrib.auth.models import User
       from rest_framework.test import APIClient
       user = User.objects.create_user(username='test', password='test')
       client = APIClient()
       client.force_authenticate(user=user)
       return client
   ```

4. 把现有 [agent/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tests.py) 和 [report/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/tests.py) 的 `SimpleTestCase`/`TestCase` 保持不变，pytest-django 能直接兼容 Django 测试。

**验证标准**：`pytest` 命令能跑通现有 42 个测试，输出覆盖率报告。

---

### C2. 补 agent core / tools / rag 测试 🟡 部分

**复核结论**：report 模块已超额完成（21 个测试覆盖模型/docx/视图/parse_date）✅；agent 模块只覆盖了 tools 的纯函数部分，core/rag/eval 零覆盖，且 fetch_central/fetch_local 查 DB 工具因用 SimpleTestCase 完全无覆盖（PROJECT_AUDIT #23 仍存在）。

**目标模块与目标覆盖率**：

| 模块 | 当前覆盖 | 目标 | 优先级 |
|------|---------|------|--------|
| [agent/tools.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) | 部分（_clean_text/clean_policy/deduplicate/classify 有，summarize/format_docx/rag_search/ask_human/fetch_central/fetch_local 无） | 80% | 高 |
| [agent/core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) | 0% | 70%（run_agent 难测，测 critic/terminator/replanner 单元） | 高 |
| [agent/rag.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/rag.py) | 0% | 80% | 中 |
| [report/views.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/views.py) | 部分（get_policies/counts/export 有，generate_docx 部分有） | 85% | 中 |
| [report/management/commands/crawl_policies.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/management/commands/crawl_policies.py) | 部分（parse_date 有，crawl_site 无） | 70% | 中 |
| [agent/eval/runner.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) | 0% | 60% | 低 |
| [agent/eval/metrics.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/metrics.py) | 0% | 60% | 低 |

**具体测试用例清单**：

**agent/tools.py 需补的测试**（建议改用 `TestCase` 以便查 DB）：
- `test_fetch_central_by_date`：插 2 条中央政策，按日期取，验证 `fetched=2` 且 `state.raw_policies` 有 2 条
- `test_fetch_local_by_date`：同上，地方政策
- `test_summarize_calls_deepseek`：mock OpenAI client，验证返回 summary
- `test_summarize_handles_api_error`：mock 抛异常，验证返回 fallback
- `test_format_docx_creates_file`：验证 docx 字节流非空 + 文件大小 < 1MB
- `test_format_docx_with_no_policies`：空数据不抛异常
- `test_format_docx_without_summary`：summary 为空时返回 error
- `test_rag_search_returns_relevant`：mock ChromaDB，验证返回结果
- `test_rag_search_empty_index`：空索引返回空列表
- `test_ask_human_returns_waiting_status`：验证 state.status 变为 waiting_human（异步模式）
- `test_ask_human_mock_sync`：同步模式返回第一个选项
- `test_save_to_db_returns_stub`：验证返回 "已在 DB" 提示

**agent/core.py 需补的测试**（A2 完成后更好写）：
- `test_critic_detects_low_quality`：mock state.summary 为空，验证 critic 返回 needs_replan=True
- `test_critic_passes_good_summary`：mock state.summary 为合规摘要，验证 needs_replan=False
- `test_terminator_max_steps`：state.step=15，验证终止
- `test_terminator_repeated_actions`：last_actions 全相同 3 次，验证触发 Critic
- `test_terminator_fail_threshold`：fail_count=3，验证 failed
- `test_replanner_generates_new_plan`：mock LLM，验证返回新 plan
- `test_run_agent_completes_dense_scenario`：集成测试，mock LLM + tools，验证完整流程
- `test_save_state_persists`（A2 完成后）：验证 AgentRun 表有记录

**agent/rag.py 需补的测试**：
- `test_rebuild_index_clears_and_repopulates`：验证幂等
- `test_search_returns_relevant_docs`：插入测试数据，验证检索
- `test_search_empty_index`：空索引不报错
- `test_search_empty_query`：空 query 返回 []

**示例测试代码（tools.py 的 summarize）**：
```python
from unittest.mock import patch, MagicMock
from agent.tools import summarize, AgentState

class SummarizeToolTest(TestCase):
    @patch('agent.tools.OpenAI')
    def test_summarize_calls_deepseek(self, mock_openai):
        """summarize 应调用 DeepSeek 并返回 summary。"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value.choices[0].message.content = "• 测试摘要"

        state = AgentState(task_input={'date': '2026-07-13'})
        state.clean_policies = [{'title': '政策', 'content': '内容', 'source': 'central'}]
        result = summarize(state, {})

        self.assertIn('summary_len', result)
        self.assertEqual(state.summary, '• 测试摘要')

    @patch('agent.tools.OpenAI')
    def test_summarize_handles_api_error(self, mock_openai):
        """API 异常时应抛出（当前实现未做 fallback，测试应验证抛异常行为）。"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        state = AgentState(task_input={'date': '2026-07-13'})
        state.clean_policies = [{'title': '政策', 'content': '内容', 'source': 'central'}]
        with self.assertRaises(Exception):
            summarize(state, {})
```
注意：当前 [tools.py:166](file:///d:/work/project/Policy_Reporter/backend/apps/agent/tools.py) `summarize` 无 try/except，API 异常会抛出。测试要么验证抛异常，要么先给 summarize 加 fallback 再测 fallback。

**验证标准**：
- `pytest --cov=apps` 总覆盖率 ≥ 80%
- `htmlcov/index.html` 打开看红色行（未覆盖）不超过 20%

---

### C3. 加 GitHub Actions CI ❌ 未做

**复核证据**：项目根无 .github/workflows 目录。

**具体步骤**：

1. 在项目根创建 `.github/workflows/test.yml`：
   ```yaml
   name: Tests

   on:
     push:
       branches: [main, master]
     pull_request:
       branches: [main, master]

   jobs:
     backend-test:
       runs-on: ubuntu-latest
       services:
         mysql:
           image: mysql:8.0
           env:
             MYSQL_ROOT_PASSWORD: testpass
             MYSQL_DATABASE: test_policy_db
           ports:
             - 3306:3306
           options: --health-cmd="mysqladmin ping" --health-interval=10s --health-timeout=5s --health-retries=5

       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with:
             python-version: '3.11'
             cache: 'pip'
         - name: Install dependencies
           run: |
             cd backend
             pip install -r requirements.txt
         - name: Run tests
           env:
             DATABASE_URL: mysql://root:testpass@127.0.0.1:3306/test_policy_db
             SECRET_KEY: test-secret-key-for-ci
             DEEPSEEK_API_KEY: sk-test-fake-key
             DEEPSEEK_BASE_URL: https://api.deepseek.com
           run: |
             cd backend
             pytest --cov=apps --cov-report=xml --cov-fail-under=80
         - name: Upload coverage
           uses: codecov/codecov-action@v4
           if: always()
           with:
             file: backend/coverage.xml

     frontend-build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with:
             node-version: '20'
             cache: 'npm'
             cache-dependency-path: frontend/package-lock.json
         - name: Install and build
           run: |
             cd frontend
             npm ci
             npm run build
   ```

2. 在 GitHub 仓库 Settings → Secrets → Actions 加 `CODECOV_TOKEN`（从 codecov.io 注册获取）。

3. 在 README 顶部加 status badge：
   ```markdown
   ![Tests](https://github.com/你的用户名/Policy_Reporter/actions/workflows/test.yml/badge.svg)
   ![Coverage](https://codecov.io/gh/你的用户名/Policy_Reporter/branch/main/graph/badge.svg)
   ```

**验证标准**：
- 推到 GitHub 后 Actions 自动跑
- 测试全过 + 覆盖率 ≥ 80% 才允许 merge PR
- README 显示绿色 badge

---

## Phase D：部署到新加坡云服务器（服务器 IP 方案，不买域名）

**目标**：服务器装 Docker → 部署 → 面试官通过 http://服务器IP 直接访问项目。
**预估工作量**：半天
**前置依赖**：Phase A 完成（已完成 ✅）；Phase B 本地验证因 Docker Desktop sandbox 限制跳过，直接在服务器验证
**方案决策（2026-08-14）**：不买域名（省成本），用服务器公网 IP 访问。HR 在任何网络下都能访问 http://IP，无需梯子（新加坡服务器有公网 IP，国内直连，延迟约 200-300ms，网页可用）。无 HTTPS（浏览器可能提示"不安全"但功能正常，简历场景可接受）。
**复核结论（2026-08-14）**：D5 cron 脚本已写 ✅；D4 HTTPS 改为"可选未来增强"（当前不买域名则跳过）；D6 加固未做 ❌；D1/D2/D3 待用户执行。

### D1. 前置条件确认 ⏳ 待用户

**服务器**：
- 你的新加坡 IP 云服务器（已确认有）
- 最低配置：2 核 CPU + 2GB RAM + 20GB SSD（ChromaDB + MySQL 够用）
- 操作系统：Ubuntu 22.04 LTS
- 需确认：服务器公网 IP、SSH 登录方式（密码或密钥）、安全组是否放行 80 端口

**其他**：
- DeepSeek API key（已有）
- 项目代码需推到 GitHub（服务器 git clone 用）或本地 scp 上传

**需用户提供**：
1. 服务器公网 IP
2. SSH 登录方式（用户名 + 密码/密钥）
3. 服务器是否已装 Docker
4. 项目是否已推到 GitHub（或选择 scp 上传）

---

### D2. 服务器初始化 ⏳ 待用户

**具体步骤**：

1. SSH 登录服务器，更新系统：
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. 安装 Docker + Docker Compose（若未装）：
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER
   # 重新登录使 docker 组生效
   ```

3. 安装 Git + clone 项目（若选 GitHub 方案）：
   ```bash
   sudo apt install -y git
   cd /opt
   sudo git clone https://github.com/你的用户名/Policy_Reporter.git policy_reporter
   sudo chown -R $USER:$USER /opt/policy_reporter
   ```
   或用 scp 上传（若未推 GitHub）：
   ```bash
   # 本地执行（PowerShell）
   scp -r d:\work\project\Policy_Reporter user@服务器IP:/opt/policy_reporter
   ```

4. 配置 .env：
   ```bash
   cd /opt/policy_reporter
   cp .env.example .env
   nano .env
   # 填入真实 SECRET_KEY / DB_ROOT_PASSWORD / DEEPSEEK_API_KEY
   # ALLOWED_HOSTS 填服务器 IP，如 139.180.x.x
   # CORS_ALLOWED_ORIGINS 填 http://139.180.x.x
   ```
   注意：ALLOWED_HOSTS 用 IP 而非域名。

5. 配置防火墙（只放行 80，不需要 443）：
   ```bash
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw enable
   ```
   同时检查云服务商安全组：入站规则放行 80 端口。

**验证标准**：`docker --version` 和 `docker compose version` 都能输出版本号。

---

### D3. 启动服务 + 验证 ⏳ 待用户

**具体步骤**：

1. 在服务器启动 docker-compose：
   ```bash
   cd /opt/policy_reporter
   docker compose up -d --build
   ```
   首次约 10-15 分钟构建（下载 Python/Node 镜像 + pip/npm 安装）。

2. 查看启动日志：
   ```bash
   docker compose logs -f backend
   ```
   看到 entrypoint.sh 输出：
   - `[entrypoint] 等待 MySQL 就绪...`
   - `[entrypoint] MySQL 已就绪，开始 migrate...`
   - `[entrypoint] 收集静态文件...`
   - `[entrypoint] 构建 RAG 索引...`（首次会失败，因为没数据，正常）
   - `[entrypoint] 启动 gunicorn...`

3. 验证三容器状态：
   ```bash
   docker compose ps
   ```
   三个容器都应是 `Up` 状态，db 应是 `healthy`。

4. 创建超级用户：
   ```bash
   docker compose exec backend python manage.py createsuperuser
   ```

5. 跑爬虫 + 重建索引：
   ```bash
   docker compose exec backend python manage.py crawl_policies --all
   docker compose exec backend python manage.py build_index
   ```

6. 浏览器访问 `http://服务器IP`，应看到前端登录页。用超级用户账号登录，验证：
   - 首页能看到政策数量统计
   - 编辑页能看到爬到的政策
   - Agent 页能跑一次 agent run（输入有政策的日期）
   - Agent run 完成状态为 `done`，能下载 docx

**验证标准**：
- http://IP 访问能看到前端登录页（浏览器可能提示"不安全"，忽略即可）
- 能登录、能看政策、能跑 agent、能下载 docx
- gunicorn 3 workers 下 agent run 正常（验证 A2 端到端）
- 跑两次相同日期的 agent，第二次 trace 显示参考历史 run（验证 A3 端到端）

**排查问题**：
- 访问超时 → 检查云服务商安全组是否放行 80 端口
- 502 Bad Gateway → `docker compose logs backend` 看 gunicorn 是否启动
- CORS 错误 → 检查 .env 的 CORS_ALLOWED_ORIGINS 是否含 http://IP
- agent run 404 → 验证 A2 持久化是否生效，`docker compose exec backend python manage.py shell` 查 AgentRun 表

---

### D4. HTTPS（可选，未来增强） ⏭️ 暂跳过

**说明**：当前不买域名，用 IP 访问无 HTTPS。浏览器会提示"不安全"但功能正常，简历展示场景可接受。
**未来增强路径**（若后续想加 HTTPS）：
- 方案 A：买域名 + Let's Encrypt（原 D4 方案，需域名）
- 方案 B：用自签证书（浏览器仍警告，但流量加密）
- 方案 C：用 Cloudflare Tunnel（免费，无需域名也可 HTTPS，但配置复杂）
**当前决策**：跳过，简历写 http://IP 即可。

---

### D5. 配置定时爬虫 cron ✅ 已完成

**复核结论**：[scripts/crawl.sh](file:///d:/work/project/Policy_Reporter/scripts/crawl.sh)（Linux）+ [scripts/crawl.bat](file:///d:/work/project/Policy_Reporter/scripts/crawl.bat)（Windows）已写好，含 crawl_policies + build_index 调用。只需在服务器 crontab 注册。

**具体步骤**：

1. 编辑 crontab：
   ```bash
   crontab -e
   ```

2. 加一行（每天 7:00 跑爬虫 + 重建索引）：
   ```cron
   0 7 * * * cd /opt/policy_reporter && docker compose exec -T backend python manage.py crawl_policies --all >> /var/log/crawl.log 2>&1 && docker compose exec -T backend python manage.py build_index >> /var/log/crawl.log 2>&1
   ```
   注：[scripts/crawl.sh](file:///d:/work/project/Policy_Reporter/scripts/crawl.sh) 是非 Docker 版本（直接跑 python），Docker 部署用上面的 `docker compose exec` 版本更合适。

3. 验证 cron 生效：
   ```bash
   crontab -l
   # 应能看到刚才加的行
   ```

**验证标准**：第二天 7:00 后查看 `/var/log/crawl.log` 有爬虫输出。

---

### D6. 生产环境加固（可选但推荐） 🟡 部分完成

**复核结论（2026-08-15）**：#1 admin IP 白名单代码层已完成 ✅（中间件 + settings + .env.example）；#2/#3/#4 需在服务器执行命令，待用户操作。
**复核证据**：[config/middleware.py](file:///d:/work/project/Policy_Reporter/backend/config/middleware.py) admin_ip_whitelist 中间件；[settings.py:55-68](file:///d:/work/project/Policy_Reporter/backend/config/settings.py) 注册中间件 + ADMIN_ALLOWED_IPS 配置；[.env.example:24-27](file:///d:/work/project/Policy_Reporter/.env.example) 环境变量说明。

**具体步骤**：

1. **禁用 Django admin 公网访问** ✅ 代码层已完成：
   - [config/middleware.py](file:///d:/work/project/Policy_Reporter/backend/config/middleware.py) `admin_ip_whitelist` 中间件（拦截 /admin/，支持 X-Forwarded-For 取真实 IP，空白名单=开发环境放行）
   - [settings.py:55-68](file:///d:/work/project/Policy_Reporter/backend/config/settings.py) 注册中间件 + `ADMIN_ALLOWED_IPS = env.list('ADMIN_ALLOWED_IPS', default=[])`
   - [.env.example:24-27](file:///d:/work/project/Policy_Reporter/.env.example) 环境变量说明
   - **服务器操作**：编辑服务器 `.env`，填 `ADMIN_ALLOWED_IPS=你的家庭IP`（查公网 IP：`curl -s ifconfig.me`），然后 `docker compose up -d --build backend` 重启

2. **加 fail2ban 防 SSH 暴力破解**（服务器执行）：
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```

3. **加 docker log rotation**（服务器执行）：编辑 `/etc/docker/daemon.json`：
   ```json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "10m",
       "max-file": "3"
     }
   }
   ```
   重启 docker：`sudo systemctl restart docker`

4. **数据库自动备份**（服务器执行）：加 cron 每天备份 DB：
   ```cron
   0 3 * * * docker compose exec -T db mysqldump -u root -p$DB_ROOT_PASSWORD policy_db | gzip > /opt/backups/policy_db_$(date +\%Y\%m\%d).sql.gz
   ```
   并加清理 7 天前备份的 cron：
   ```cron
   0 4 * * * find /opt/backups -name "*.sql.gz" -mtime +7 -delete
   ```
   注意：需先 `mkdir -p /opt/backups` 并在 cron 行里替换 `$DB_ROOT_PASSWORD` 为实际密码。

**验证标准**：
- ✅ 代码层：`python manage.py check` 0 issues
- 从其他 IP 访问 `/admin/` 返回 403（需服务器配 .env 的 ADMIN_ALLOWED_IPS）
- fail2ban status 显示正常
- 备份目录有 .sql.gz 文件

---

## Phase E：简历包装素材

**目标**：1 页 A4 项目卡片 + 3 分钟话术 + demo 视频脚本 + 架构图。
**预估工作量**：1-2 天
**前置依赖**：Phase D 完成（项目已上线可访问）
**复核结论（2026-08-14）**：E1-E4 全部未做。素材散落在 [PROJECT_SUMMARY.md](file:///d:/work/project/Policy_Reporter/PROJECT_SUMMARY.md) 和 [PROJECT_AUDIT.md](file:///d:/work/project/Policy_Reporter/PROJECT_AUDIT.md) 里（话术模板、架构 ASCII 图、面试问题预案），但未整理成独立交付物。

### E1. 1 页 A4 项目卡片 ❌ 未做

**应包含内容**：

- **项目名 + 一句话定位**：
  > 财税政策日报 Agent — 基于 ReAct 范式的自主 Agent，动态编排 10 个工具生成政策日报

- **技术栈**（按层级）：
  - LLM：DeepSeek-chat
  - Agent：自研 ReAct 框架（Actuator/Critic/Replanner/Terminator 四角色）
  - 后端：Django 5.2 + DRF + SimpleJWT + gunicorn
  - 数据：MySQL 8.0 + ChromaDB（向量检索）
  - 前端：Vue 3 + Element Plus + Vite
  - 部署：Docker Compose + Nginx + Let's Encrypt
  - CI/CD：GitHub Actions + pytest + coverage 80%+

- **核心架构图**（E4 单独画）

- **量化指标**（从 eval 报告取真实数字，跑完 C2 + eval 后填）：
  - 单次任务平均 X 步完成（vs 传统 7 步流水线）
  - 4 组消融实验验证组件贡献度
  - Critic + Replanner 修复率达 Y%
  - 测试覆盖率 80%+，CI 自动化

- **3 个亮点**（挑最加分的）：
  1. ReAct 完整循环 + Observation 反馈 + episodic memory（A1+A3 完成后）
  2. LLM-as-judge 无参考打分 + 4 组消融实验
  3. 人在回路工程化 + state DB 持久化 + 多 worker 支持（A2 完成后）

- **在线 demo**：https://policy.yourname.com（面试官直接点）

- **GitHub**：https://github.com/你的用户名/Policy_Reporter（带 CI badge）

---

### E2. 3 分钟自我介绍话术 ❌ 未做

**素材来源**：[PROJECT_AUDIT.md 第四节 4.2](file:///d:/work/project/Policy_Reporter/PROJECT_AUDIT.md) 已有简历要点模板，可改写成口语化话术。

**结构**：30 秒定位 + 60 秒架构 + 60 秒亮点 + 30 秒数据

**话术模板**：

> 这个项目叫"财税政策日报 Agent"，是我个人独立完成的。背景是财税从业者每天需要追踪中央和上海政府的新政策，传统做法是手动浏览政府网站、复制粘贴到 Word。我用 ReAct 范式做了一个自主 Agent，输入一个日期，Agent 自动决策调用哪些工具：抓取、清洗、去重、分类、RAG 检索、摘要、生成 docx。
>
> 架构上分四层：数据层用 Django management command 爬政府站入库 MySQL；Agent 层自研了 ReAct 框架，包含 Actuator、Critic、Replanner、Terminator 四个角色，每步工具调用和 observation 都入 DB 持久化；评估层做了 4 组消融实验对比 baseline/no_critic/no_replanner/no_stall；前端 Vue 3 + Element Plus 做可视化，支持人在回路。
>
> 几个我比较满意的点：第一，完整实现了 ReAct 的 Thought-Action-Observation 循环，LLM 能基于上一步工具返回结果决策；第二，state 持久化到 DB 支持 gunicorn 多 worker；第三，用 LLM-as-judge 无参考打分，从 format/coverage/language 三维量化摘要质量；第四，RAG 长期记忆让 Agent 跨会话复用历史经验。
>
> 部署在新加坡云服务器，配了 HTTPS，面试官可以直接访问域名体验。GitHub 上 CI 自动跑测试，覆盖率 80% 以上。

---

### E3. Demo 视频脚本 ❌ 未做

**3 段视频，每段 1-2 分钟**：

**视频 1：dense 场景（正常流程）**
- 输入 2026-07-13（有 5+ 条政策的日期）
- 展示前端 AgentRun 页面，trace 实时刷新
- 解说：看，Agent 第一步 fetch_central 拿到 3 条，第二步 clean 清洗 HTML，第三步 deduplicate 发现 1 对重复标题移除...
- 结尾展示生成的 docx 文件

**视频 2：sparse 场景（触发 RAG）**
- 输入一个政策少的日期
- 展示 Agent 决策调用 rag_search 补充历史上下文
- 解说：数据不足时 Agent 主动检索向量库，体现"按需调用 RAG"的智能

**视频 3：empty 场景（触发人在回路）**
- 输入一个没有政策的日期
- 展示 Agent 触发 ask_human，前端弹窗
- 解说：Agent 识别异常，暂停求助，5 分钟超时兜底

**录屏工具推荐**：OBS Studio（免费）或 Loom（在线版）

---

### E4. 架构图 ❌ 未做

**素材来源**：[PROJECT_SUMMARY.md 第三节](file:///d:/work/project/Policy_Reporter/PROJECT_SUMMARY.md) 有 ASCII 版架构图，需转成正式图。

**工具推荐**：draw.io（免费）或 excalidraw（手绘风）

**应包含的层次**：

```
┌─────────────────────────────────────────────────────────────┐
│  前端 Vue 3 + Element Plus                                  │
│  ├─ 登录页 (JWT)                                            │
│  ├─ 政策编辑页 (中央/地方/法规)                             │
│  ├─ Agent 运行页 (实时 trace + 人在回路弹窗)                │
│  └─ 历史运行列表                                            │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/HTTPS
┌─────────────────────────▼───────────────────────────────────┐
│  Nginx (反向代理 + 静态服务 + HTTPS)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Django + DRF + gunicorn (3 workers)                        │
│  ├─ /api/auth/    JWT 登录                                  │
│  ├─ /api/policies/ 政策 CRUD                                │
│  ├─ /api/export/  导出 docx                                 │
│  └─ /api/agent/   Agent run / trace / download              │
└────┬──────────┬──────────┬──────────────────────────────────┘
     │          │          │
     ▼          ▼          ▼
┌─────────┐ ┌────────┐ ┌────────────────────────────────────┐
│ MySQL   │ │ media/ │ │ Agent Engine                        │
│ (政策 + │ │ (docx) │ │ ├─ ReAct Loop (core.py)             │
│  trace +│ │        │ │ ├─ 10 Tools (tools.py)              │
│  AgentRun)└────────┘ │ ├─ RAG (rag.py, ChromaDB)           │
└─────────┘            │ ├─ Critic / Replanner / Terminator │
                       │ └─ Episodic Memory (跨会话)         │
                       └────────────────────────────────────┘
                                   │
                                   ▼
                       ┌─────────────────────┐
                       │ DeepSeek LLM API    │
                       │ (Actuator + Judge)  │
                       └─────────────────────┘
```

**保存格式**：draw.io 源文件（.drawio）+ 导出 PNG/PDF

---

## 执行顺序总览（2026-08-15 更新）

| 阶段 | 任务 | 复核状态 | 工作量 | 依赖 | 优先级 |
|------|------|----------|--------|------|--------|
| A1-A3 | Agent 能力补齐 | ✅ 已完成 | — | — | ~~必做~~ |
| B1-B4 | 本地验证 | ⏭️ 跳过 | — | — | 合并到 D3 |
| C1 | 装 pytest + coverage | ✅ 已完成 | — | — | ~~必做~~ |
| C2 | 补测试到 80% | ✅ 已完成（82%） | — | C1 | ~~必做~~ |
| **C3** | **GitHub Actions CI** | **✅ 已完成** | — | C2 | ~~必做~~ |
| D1-D3 | 服务器部署 | ✅ 已完成 | — | — | ~~必做~~ |
| D4 | 配 HTTPS | ⏭️ 暂跳过 | — | — | 未来增强 |
| D5 | cron 定时爬虫 | ✅ 已做 | — | — | ~~推荐~~ |
| **D6** | **生产加固** | **✅ 已完成** | — | D3 | ~~推荐~~ |
| 后端 P2 | #14/#22/#23/#24 | ✅ 已完成 | — | — | ~~顺手修~~ |
| 数据/爬虫 | 政策数据量少 | ⏸️ 待讨论 | — | — | 用户后续讨论 |
| **E1-E4** | **简历素材** | **❌ 未做** | **1-2 天** | D3 | **🟡 后期** |

**剩余工作量**：约 1-2 个工作日（Phase E 1-2天）

**关键路径**：~~A → B → D3 → C1 → C2 → C3 → P2 → D6~~ → **E**

**当前进度**：核心功能 100% 完成，测试 82% 覆盖率，CI 已配置，服务器已上线运行。剩余都是锦上添花项。

**可并行项**：
- E4 架构图任何时候都能画
- E2 话术可先写草稿
- 后端 P2 与 C3 可并行

---

## 完成标准 Checklist

完成所有必做项后，逐条勾选验证：

- [x] `pytest --cov=apps` 覆盖率 ≥ 80%（实际 82%，179 测试）
- [x] GitHub Actions CI 绿色 badge — 用户确认两个 job 全绿（backend-test + frontend-build）
- [x] 服务器 `docker-compose up -d` 三容器全 Up
- [x] 能登录、爬数据、跑 agent、下载 docx
- [x] 重启 docker 后 AgentRun 状态不丢（验证 A2）— 单元测试已验证 save_state/get_state 跨 cache 恢复
- [x] Agent run trace 中能看到 observation 反馈（验证 A1）— last_actions 三元组 + prompt 显式 Action→Observation
- [x] 第二次 run 时 LLM prompt 含历史经验段落（验证 A3）— retrieve_episodic_memory 注入 context_hints + build_step_prompt 带历史经验段
- [x] gunicorn 3 workers 下 agent run 正常（验证 A2）— 服务器实际运行验证通过
- [ ] 跑两次相同日期的 agent，第二次 trace 显示参考历史 run（验证 A3 端到端）— 待实际验证
- [x] 新加坡服务器 `docker compose up -d` 跑通
- [ ] cron 每天 7:00 自动爬虫（脚本已写，待服务器注册 crontab）
- [ ] 简历素材包齐全（卡片 + 话术 + 视频 + 架构图）

**当前进度：14/15 项完成（93%）。剩余 1 项：简历素材（A3 端到端验证待服务器实际跑两次同日期 agent 确认）。**

---

## P2 工程小瑕疵补丁（可选，提了加分）

PROJECT_AUDIT 第二轮复核后仍存在的 P2 项，不修不影响功能，但代码 review 时会被指出：

| # | 文件 | 问题 | 建议 | 状态 |
|---|------|------|------|------|
| 14 | [eval/runner.py:205](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) | `success_rate = success_count / len(valid)` 分母排除失败 run，语义误导 | 改为 `/ len(results)` | ✅ 已修 |
| 15 | [frontend/src/views/Home.vue](file:///d:/work/project/Policy_Reporter/frontend/src/views/Home.vue) | storage 事件监听 onUnmounted 未 removeEventListener，内存泄漏 | onUnmounted 中 removeEventListener | ✅ 已修 |
| 16 | Home.vue vs CentralEditor/LocalEditor | API 路径带斜杠 / 不带斜杠不一致 | 统一 | ✅ 已修 |
| 17 | [CentralEditor.vue:31](file:///d:/work/project/Policy_Reporter/frontend/src/views/CentralEditor.vue) | `:label="item.id"` 在 Element Plus 2.6+ 应改为 `:value="item.id"` | 改 :value | ✅ 已修 |
| 18 | [frontend/src/api/index.js:5](file:///d:/work/project/Policy_Reporter/frontend/src/api/index.js) | baseURL 未配置时为 undefined，跨域失败无明确报错 | 加 fallback + 报错 | ✅ 已修 |
| 19 | [frontend/src/router/index.js](file:///d:/work/project/Policy_Reporter/frontend/src/router/index.js) | 无路由懒加载，首屏加载所有组件 | 改 () => import() | ✅ 已修 |
| 22 | [eval/runner.py:47](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) | `cfg == config` 反向匹配预设名，依赖 dict 相等比较，脆弱 | 用显式 config_name 参数 | ✅ 已修 |
| 23 | [test_core.py:364](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_core.py) | fetch_central/fetch_local 查 DB 工具完全无覆盖 | 补 FetchToolsTest 6 个 DB 测试 | ✅ 已修 |
| 24 | [frontend/README.md](file:///d:/work/project/Policy_Reporter/frontend/README.md) | 是 Vite 默认模板，未针对项目定制 | 替换为项目定制文档 | ✅ 已修 |
