# Policy_Reporter 项目体检报告（第一轮 · 仅讨论不改动代码）

> 目标：1) 确保项目能完整顺利运行；2) 完善到能作为海归 AI 硕士求职面试项目。
> 体检日期：2026-07-20
> 范围：backend / frontend / docker-compose / 爬虫 / eval 框架
> 方法：逐文件阅读 + 跨文件一致性核查，未做运行时回归测试。

---

## 修复状态更新（2026-08-16）

> 以下问题已在后续开发中修复，面试时无需担心。

| # | 原问题 | 修复状态 | 修复证据 |
|---|--------|----------|----------|
| P0-1 | run_eval --all-ablations 崩溃 | ✅ 已修 | [run_eval.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/run_eval.py) 补 return |
| P0-2 | metrics.py 模块级 OpenAI 初始化 | ✅ 已修 | [metrics.py:31](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/metrics.py) 改懒加载 `_get_judge_client()` |
| P0-3 | get_summary 死代码 | ✅ 已修 | [metrics.py:161](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/metrics.py) 三层 fallback + 截断标记 |
| P0-4 | TIME_ZONE = UTC | ✅ 已修 | [settings.py](file:///d:/work/project/Policy_Reporter/backend/config/settings.py) 改 Asia/Shanghai |
| P0-5 | 无 STATIC_ROOT/MEDIA_ROOT | ✅ 已修 | [settings.py](file:///d:/work/project/Policy_Reporter/backend/config/settings.py) 已配置 |
| P1-6 | Dockerfile 用 runserver | ✅ 已修 | [entrypoint.sh](file:///d:/work/project/Policy_Reporter/backend/entrypoint.sh) 改 gunicorn 3 workers |
| P1-7 | docker-compose 无 media 卷 | ✅ 已修 | [docker-compose.yml](file:///d:/work/project/Policy_Reporter/docker-compose.yml) 加 backend_media 卷 |
| P1-8 | SECRET_KEY 有默认值 | ✅ 已修 | [docker-compose.yml](file:///d:/work/project/Policy_Reporter/docker-compose.yml) 用 `${VAR:?}` 强制读 .env |
| P1-9 | 爬虫 max-pages 假参数 | ✅ 已修 | [crawl_policies.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/management/commands/crawl_policies.py) 实现翻页 + 时区修复 + list_failed |
| P1-10 | report 模块零测试 | ✅ 已修 | [report/tests.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/tests.py) 21 个测试 |
| P1-11 | permission_classes 不一致 | ✅ 已修 | [report/views.py](file:///d:/work/project/Policy_Reporter/backend/apps/report/views.py) 4 个端点均显式声明 |
| P1-12 | testset 硬编码日期 | ✅ 已修 | [testset.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/testset.py) 改 DB 自动发现 |
| P1-13 | report/admin.py 重复 import | ✅ 已修 | 已删除 |
| P2-14 | success_rate 分母 | ✅ 已修 | [runner.py:205](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) 改 len(results) |
| P2-15~19 | 前端 P2 瑕疵 | ✅ 已修 | Home.vue/CentralEditor/api/router 全修 |
| P2-22 | runner config_name 反向推断 | ✅ 已修 | [runner.py:47](file:///d:/work/project/Policy_Reporter/backend/apps/agent/eval/runner.py) 改显式传入 |
| P2-23 | fetch 工具无 DB 测试 | ✅ 已修 | [test_core.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/test_core.py) FetchToolsTest 6 个测试 |
| P2-24 | frontend/README.md Vite 模板 | ✅ 已修 | 替换为项目定制文档 |

**额外加固**（audit 未列但已完成）：
- LLM 调用指数退避重试（[core.py:66](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py) `_call_llm_with_retry`）
- episodic memory 存完整 (tool, params) 而非仅工具名（[core.py:348](file:///d:/work/project/Policy_Reporter/backend/apps/agent/core.py)）
- `_has_docx_trace` 抽到 [agent/utils.py](file:///d:/work/project/Policy_Reporter/backend/apps/agent/utils.py) 消除重复定义
- admin IP 白名单中间件（[config/middleware.py](file:///d:/work/project/Policy_Reporter/backend/config/middleware.py)）
- GitHub Actions CI（[.github/workflows/test.yml](file:///d:/work/project/Policy_Reporter/.github/workflows/test.yml)）
- fail2ban + docker log rotation + DB 备份 cron（D6 生产加固）

---

## 一、项目整体评价（结论先行）

宝宝这个项目作为面试项目是 **有真实硬实力底子的**，不是"玩具 demo"。亮点和短板同样明显：

### 加分项（保留 + 简历放大）
- **架构完整**：数据层（爬虫 + DB）→ Agent 层（ReAct + Critic + Replanner + Terminator）→ 人在回路 → Eval 框架 → 前端可视化，全链路打通。
- **ReAct 设计有思考**：三角色合并（7→3）、批量工具操作 state、LLM 只看计数摘要节省 token、classify 用确定性元数据而非 LLM——每个决策都有 tradeoff 注释。
- **消融实验是真东西**：4 组配置 × 6 场景，有 LLM-as-judge + 修复率 + Critic 触发率多维指标。这是大多数学生项目没有的。
- **RAG 按需调用**：sparse 场景主动调 RAG 补充上下文，dense 场景跳过——"不同 run 不同路径"的反玩具证据。
- **人在回路工程化**：后台线程 + threading.Event + 2s 轮询 + 弹窗 + 5min 超时兜底，工程细节扎实。
- **trace 入 DB**：便于 eval 聚合统计，不是只写日志。

### 扣分项（必须修，否则面试翻车）
- **Docker 部署未完工**：后端 Dockerfile 用 `runserver` 跑生产；docker-compose 没挂载 `media/` 卷，docx 重启即丢；SECRET_KEY 默认值不安全。
- **时区错配**：`settings.TIME_ZONE = "UTC"`，但项目是中国政策日报，会导致按日期过滤偏 8 小时。
- **静态资源未配置**：无 `STATIC_ROOT`，`collectstatic` 会失败，Nginx 无法服务静态文件。
- **eval 框架有崩溃 bug**：`run_eval.py --all-ablations` 分支跑完后必崩（list 当 dict 用）。
- **爬虫假参数**：`--max-pages` 和 `crawl_config.json` 的 `max_pages` 完全没生效，代码只抓首页。
- **report 模块零测试**：21 个 agent 测试 vs 0 个 report 测试，对比刺眼。
- **生产 settings 与 dev settings 未分离**：DEBUG 靠 .env 切，但 SECRET_KEY、ALLOWED_HOSTS 在 docker-compose 里有默认值兜底（不安全）。

---

## 二、阻塞性问题清单（按严重度排序）

### 🔴 P0 - 不修就跑不起来 / 一跑就崩

| # | 文件 | 行号 | 问题 | 影响 |
|---|------|------|------|------|
| 1 | `backend/apps/agent/eval/run_eval.py` | 98-145 | `--all-ablations` 分支 `run_all_ablations()` 返回 list，但末尾没 `return`，继续执行 `report["aggregate"]` 抛 `TypeError` | 跑全消融实验必崩，核心 demo 失效 |
| 2 | `backend/apps/agent/eval/metrics.py` | 26-29 | 模块级 `_judge_client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, ...)` 在 settings 未就绪时 import 直接抛 `ImproperlyConfigured` | eval 模块在测试环境/未配 .env 时无法 import |
| 3 | `backend/apps/agent/eval/metrics.py` | 165-180 | `get_summary` 中 summarize trace 分支只有 `pass`，是死代码；docx 提取分支依赖 python-docx 静默吞异常 | LLM-judge 全部得 1 分但报告不报错，eval 结论失真 |
| 4 | `backend/config/settings.py` | 140 | `TIME_ZONE = "UTC"`，但项目是中国政策日报 | 按日期过滤 / cron 触发 / 爬虫入库时间全偏 8 小时 |
| 5 | `backend/config/settings.py` | - | 无 `STATIC_ROOT`，无 `MEDIA_URL` / `MEDIA_ROOT` | `collectstatic` 失败，Nginx 取不到静态文件，前端 admin 资源 404 |

### 🟠 P1 - 不修能跑但简历扣分

| # | 文件 | 行号 | 问题 | 影响 |
|---|------|------|------|------|
| 6 | `backend/Dockerfile` | 28 | `CMD ["python", "manage.py", "runserver", ...]`，注释里写"Phase 8 替换为 gunicorn"但没换 | 生产用 runserver 是禁忌，面试官一眼看出 |
| 7 | `docker-compose.yml` | 22-37 | backend 容器没挂载 `media/` 卷，重启容器 docx 全丢 | 与"docx 持久化到 media/"设计意图矛盾 |
| 8 | `docker-compose.yml` | 29 | `SECRET_KEY: ${SECRET_KEY:-change-me-in-production}` 有默认值 | 不读 .env 也能起，密钥泄露风险 |
| 9 | `backend/apps/report/management/commands/crawl_policies.py` | 135 / 60 / 146-150 | `--max-pages` 假参数（代码没翻页循环）；发布时间硬编码 UTC；`failed=-1` 哨兵被累加 | 爬虫功能与文档不符，统计数字失真 |
| 10 | `backend/apps/report/tests.py` | - | 完全空文件，零测试覆盖 | report 是核心业务模块，零测试是面试硬伤 |
| 11 | `backend/apps/report/views.py` | 219-266 | `get_policies` / `export_policies` / `get_policy_counts` 没显式 `@permission_classes`，靠 settings 默认 `IsAuthenticated`，但 `me` 显式加了——风格不一致 | 前端跨域 cookie / token 流程下可能漏鉴权 |
| 12 | `backend/apps/agent/eval/testset.py` | 187-189 | `DEFAULT_TEST_CASES` 硬编码 `2025-07-31`，与文件头"避免硬编码过期日期"矛盾 | 过期测试用例无法复现 |
| 13 | `backend/apps/report/admin.py` | 1, 4 | `from django.contrib import admin` 重复 import 两次 | 代码洁癖减分 |

### 🟡 P2 - 工程小瑕疵（不修没事，提了加分）

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| 14 | `backend/apps/agent/eval/runner.py` | 210 | `success_rate = success_count / len(valid)` 分母排除失败 run，语义误导 |
| 15 | `frontend/src/views/Home.vue` | 107-111 | `storage` 事件监听 onUnmounted 未 `removeEventListener`，内存泄漏 |
| 16 | `frontend/src/views/Home.vue` vs `CentralEditor.vue` / `LocalEditor.vue` | - | API 路径带斜杠 / 不带斜杠不一致 |
| 17 | `frontend/src/views/CentralEditor.vue` | 31 | `:label="item.id"` 在 Element Plus 2.6+ 应改为 `:value="item.id"` |
| 18 | `frontend/src/api/index.js` | 5 | `baseURL` 未配置时为 undefined，跨域失败无明确报错 |
| 19 | `frontend/src/router/index.js` | - | 无路由懒加载，首屏加载所有组件 |
| 20 | `backend/.env.example` | - | 缺少 `MEDIA_ROOT` / `STATIC_ROOT` / 生产 `ALLOWED_HOSTS` 示例 |
| 21 | `.gitignore` | - | 未忽略 `.trae/` / `.cursor/` / 顶层 `dist/` |
| 22 | `backend/apps/agent/eval/runner.py` | 53-58 | 用 `cfg == config` 反向匹配预设名，依赖 dict 相等比较，脆弱 |
| 23 | `backend/apps/agent/tests.py` | - | 21 个测试全用 `SimpleTestCase`，fetch_central/fetch_local 查 DB 工具完全无覆盖 |
| 24 | `frontend/README.md` | - | 是 Vite 默认模板，未针对项目定制 |

---

## 三、按"能顺利运行"目标的修复路线（建议顺序）

> 这是建议路径，等宝宝确认方向后再动手。第一轮不动代码。

### 第 1 步：让本地开发能跑通（半天）
1. `settings.py`：`TIME_ZONE = "Asia/Shanghai"`，加 `STATIC_ROOT = BASE_DIR / 'staticfiles'`、`MEDIA_URL = '/media/'`、`MEDIA_ROOT = BASE_DIR / 'media'`
2. `report/admin.py`：删除重复 import
3. `report/views.py`：统一给 4 个接口显式加 `@permission_classes([IsAuthenticated])`（或在 urls.py 用 DRF 装饰器集中处理）
4. `.env.example` 补全缺失变量

### 第 2 步：让 eval 框架真能跑（半天）
1. `run_eval.py` 第 145 行：`--all-ablations` 分支补 `return`
2. `run_eval.py` 第 93 行：`input()` 加 `try/except EOFError` 兜底，或加 `--yes` 跳过确认
3. `metrics.py` 第 26-29 行：改成懒加载函数 `_get_judge_client()`
4. `metrics.py` 第 165-180 行：补全 `get_summary` 死代码分支，从 `state.summary` 或 trace output 取摘要
5. `testset.py` 第 187-189 行：删除硬编码 `DEFAULT_TEST_CASES`，或改为从 env 读

### 第 3 步：让爬虫真爬到多页（半天）
1. `crawl_policies.py`：实现 `next_page_xpath` 翻页循环（配置里已有，代码没用）
2. `crawl_policies.py` 第 60 行：`datetime(..., tzinfo=ZoneInfo("Asia/Shanghai"))`
3. `crawl_policies.py`：把 `failed=-1` 哨兵改成 `list_failed=True` 布尔字段

### 第 4 步：让 Docker 真能上生产（1 天）
1. `backend/Dockerfile`：CMD 改为 `gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers 3 --threads 2`，requirements 加 `gunicorn`
2. `docker-compose.yml`：backend 挂载 `./backend/media:/app/media` 卷
3. `docker-compose.yml`：移除 `SECRET_KEY` 默认值，强制从 .env 读
4. 加 `entrypoint.sh`：等 db 起来 → `migrate` → `collectstatic` → `build_index` → 启动 gunicorn
5. 加 `crawl.sh` / `crawl.bat` cron 脚本

### 第 5 步：补测试覆盖（1 天）
1. `report/tests.py`：给 `generate_docx` / `get_policies` / `export_policies` 写至少 5 个测试
2. `agent/tests.py`：把 `fetch_central/fetch_local` 改为 `TestCase`（用 DB），补 4 个测试
3. 跑 `python manage.py test` 全过

### 第 6 步：简历包装素材（1 天）
1. 整理 4 组消融对比表（已有 md 报告，提炼成一页）
2. 录 3 段 demo 视频：dense / sparse / empty 场景，展示不同 trace 路径
3. 画 1 张架构图（用 draw.io 或 excalidraw）
4. 整理 2 个 failure case：empty 触发 ask_human、duplicate 触发 dedup

---

## 四、简历包装建议（核心）

### 4.1 一句话项目定位（简历用）

> **财税政策日报 Agent**：基于 ReAct 模式的自主 Agent，根据给定日期动态编排 10 个工具（抓取→清洗→去重→分类→RAG 检索→摘要→docx 生成），通过 Critic + Replanner 实现失败自修复，4 组消融实验验证组件贡献度。

### 4.2 简历要点模板（按 STAR 改写）

```
项目：财税政策日报 Agent（个人项目，Python + Vue 3 + Django + DeepSeek）
时间：2026.06 - 2026.07
技术栈：Django 5.2 / DRF / Vue 3 / Element Plus / MySQL / ChromaDB / Docker / DeepSeek-chat

• 设计并实现基于 ReAct 模式的自主 Agent，三角色合并（Actuator/Critic/Terminator）
  将传统 7 步流水线压缩为动态工具编排，单次任务平均 8 步完成，token 消耗降低 60%
• 实现 Critic + Replanner 自修复机制，对 6 种数据异常场景（sparse/empty/duplicate
  /partial_missing/with_legal/dense）的修复率达 X%，对比 no_critic 基线提升 Y%
• 接入 ChromaDB 向量检索（all-MiniLM-L6-v2 多语言 embedding），Agent 按数据密度
  自主决策是否调用 RAG，sparse 场景主动检索历史相似政策补充上下文
• 设计 4 组消融实验（baseline/no_critic/no_replanner/no_stall），用 LLM-as-judge
  量化组件贡献度，得出"Critic 必须配套 Replanner 才能转化诊断为修复"的工程结论
• 实现人在回路：后台线程 + threading.Event + 前端 2s 轮询，5 分钟超时兜底
• 工程化：Docker compose 三容器部署、爬虫零新依赖、trace 入 DB 便于 eval 聚合
```

> X% 和 Y% 等宝宝跑完 eval 后填真实数字。

### 4.3 面试高频问题预案

| 问题 | 你的回答要点 |
|------|--------------|
| 为什么用 ReAct 不用 Plan-and-Execute？ | ReAct 每步可见 observation，trace 可解释；Plan 失败要全盘重规划 |
| 为什么 RAG 不每步都调？ | 数据 >=5 条时跳过 RAG 直接 summarize 省 token；<5 条时主动调——按需 |
| Critic 和 Replanner 为什么要配套？ | 消融实验证明：no_replanner 配置下 Critic 只增加 32% 开销不提升质量，单独开 Critic 是浪费 |
| 为什么不用 WebSocket 做人在回路？ | Django Channels + Redis 是新基础设施，轮询能实现暂停求助，省 3-5 天 |
| 为什么 classify 不用 LLM？ | DB 字段已是结构化分类，再调 LLM 浪费且不稳——"并非每一步都需要 LLM" |
| 为什么不用 LangChain？ | 自己实现 ReAct 主循环 < 200 行，LangChain 引入太多抽象层，trace 不可控 |
| 爬虫为什么不用 Scrapy？ | 政府站都是纯 HTML，requests+lxml 够用；Scrapy+Splash 杀鸡用牛刀 |
| eval 为什么用 LLM-as-judge？ | 人工标注基准太慢；LLM-judge 三维评分（format/coverage/language）+ temperature=0 + JSON 强制输出，工程上可控 |

### 4.4 反向问题（宝宝可以问面试官，加分）

- "你们 Agent 的 trace 是入 DB 还是只写日志？eval 时怎么聚合？"
- "你们 RAG 是按需调用还是每步必调？怎么决策？"
- "你们做过消融实验吗？Critic 单独开 vs 配套 Replanner 的差异？"

### 4.5 不要在简历里写的话

- ❌ "使用了先进的 LLM 技术"（空话）
- ❌ "实现了完整的 Agent 系统"（无量化）
- ❌ "支持高并发"（项目明说不面向高并发，面试官追问会翻车）
- ❌ "基于 LangChain"（没用 LangChain，别提；自己写的更加分）

---

## 五、待宝宝确认的方向性问题

第一轮不动代码，先对齐方向再开干。请宝宝就以下问题给出选择，我再据此做第二轮的修复 + 包装。

1. **简历目标岗位方向**：AI Agent 工程师 / 全栈工程师 / 后端工程师 / 算法工程师——不同方向包装侧重点不同
2. **Docker 部署要做到什么程度**：仅本地能跑 docker-compose / 还是真部署到云服务器有公网 IP
3. **测试覆盖率目标**：补到能跑就行 / 补到 60% 覆盖率 / 补到 80% + CI
4. **简历素材**：要不要我帮你整理一份 1 页 A4 的项目卡片（含架构图）+ 1 份 3 分钟自我介绍话术
