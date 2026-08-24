# 后续工作对照清单

> 生成于 2026-08-24。本文是执行顺序视图，勾选跟踪进度；细节与原理见 `HANDOVER.md`，演示话术见 `INTERVIEW_PLAYBOOK.md`。
> 服务器命令均在 `/opt/policy_reporter` 的 Web 面板/终端执行。

## A. 立即执行：同步 2026-08-23 修复到服务器（唯一有顺序依赖的事）

- [ ] A1. `git pull origin main`，然后 `docker compose up -d`（端口映射变更必须重建全部容器，仅 `--build backend` 不够）
- [ ] A2. `.env` 中填写 `ADMIN_ALLOWED_IPS=<常用出口IP>`（逗号分隔；留空=不限制），改完再执行一次 `docker compose up -d`
- [ ] A3. 验证端口已收窄：`docker compose ps` 正常 + `ss -tlnp | grep -E '3306|8000'` 只显示 127.0.0.1 绑定
- [ ] A4. 容器内回归：`docker compose exec backend pytest --tb=short -q`，应 194 passed
- [ ] A5. 浏览器走 Nginx 入口确认登录/首页正常（你只用网页访问的话对端口改绑无感）

## B. 一次性运维

- [ ] B1. 注册 cron 每日 8:00 采集：`scripts/crawl.sh` 已就绪，按脚本头部注释注册（HANDOVER §5）
- [ ] B2. 注册时确认 cron 脚本里含采集后 `build_index` 重建索引（否则 RAG 检索旧索引）

## C. P0 剩余安全项（量力而行，做不完降级为面试话术）

- [ ] C1. HTTPS + HTTP 安全响应头——前置条件：域名；做不完就按"内网部署时按等保要求实施"口径讲
- [ ] C2. `/static/`、`/media/` 静态文件服务——当前 Nginx 转发给 gunicorn 但 Django 无对应路由；改为 Nginx 直接挂载共享卷（可交给 AI 改）
- [ ] C3. 登录/API 限流、备份恢复演练、密钥轮换

## D. P1 演示价值提升（按面试 ROI 排序，均可交给 AI 实现）

- [ ] D1. AgentRun 用户隔离——加 user 外键 + queryset 过滤，半天；多用户系统必问点
- [ ] D2. 政策详情页 + 来源/发布日期/采集日期展示——让"可追溯"从口号变页面，直接支撑演示 T2
- [ ] D3. 前端接 refresh token——当前 access token 2 小时过期即被踢出
- [ ] D4. Celery/RQ + Redis 异步化——2-3 天，最大一块；时间不够就不做，但 PLAYBOOK §4.2 "多 worker 边界 + Redis 方案"必须练熟（不做也是面试考点）

## E. P2 可信度改进（不实施，但要能说出边界与方向）

- [ ] E1. RAG 正文片段真正参与摘要上下文（当前 rag_search 只返回标题/链接/相似度）
- [ ] E2. 评估集版本化 + `eval_reports/` 入库（README 消融表目前无法复现）
- [ ] E3. "Critic 修复率"改名"建议重规划率"（README + 话术口径）
- [ ] E4. 接口分页、健康检查、爬虫失败告警、robots 记录

## F. 周期性运维（每周约 10 分钟）

- [ ] F1. 抽检日期解析质量（无法解析日期时会以当前时间写库，HANDOVER §4）
- [ ] F2. 分类分布 + 空正文抽检（命令在 HANDOVER §5 质量抽检段）
- [ ] F3. 盯三个脆弱点：财政部（间歇 502）、商务部（内部 JSON 接口）、粤文件按标题含"广东"分流
- [ ] F4. DeepSeek 账户余额

## G. 面试准备（投递前 1-2 周集中做）

- [ ] G1. 按 `INTERVIEW_PLAYBOOK.md` §6 的 24 小时清单逐项执行（demo 账号、D1/D2 日期、预跑 T4/T5、容器 healthy、余额）
- [ ] G2. 背熟核心数字：166 条 / 194 测试 / 80% 覆盖率门槛 / 消融表
- [ ] G3. 练到脱口而出：§4.3"广东不是上海"、§4.2"多 worker 边界 + Redis 方案"
- [ ] G4. 3 分钟 STAR 介绍（§1.3）对着镜子讲两遍

## 推荐路线（时间紧张时）

A → B → G → D1 + D2 → 其余按余量取舍。C/E 做不完的价值在于面试时能精确说出"为什么还没做、怎么做"。

## 已完成存档（2026-08-23）

- 端口 3306/8000 改绑 127.0.0.1、ADMIN_ALLOWED_IPS 传入容器、中间件防 XFF 伪造（提交 4582821）
- Critic 解析失败记 warning、publish_time 反序列化恢复 datetime（提交 4582821）
- 历史文档清理与死代码删除（提交 6a749f4），均已推送 Gitee + GitHub
