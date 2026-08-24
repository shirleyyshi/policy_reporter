# 后续工作对照清单

> 生成于 2026-08-24。本文是执行顺序视图，勾选跟踪进度；细节与原理见 `HANDOVER.md`，演示话术见 `interview/INTERVIEW_PLAYBOOK.md`。
> 服务器命令均在 `/opt/policy_reporter` 的 Web 面板/终端执行。

## A. 立即执行：同步 2026-08-23 修复到服务器（已完成，2026-08-24）

- [x] A1. `git pull origin main`，然后 `docker compose up -d`（端口映射变更必须重建全部容器，仅 `--build backend` 不够）
- [x] A2. `.env` 留空 `ADMIN_ALLOWED_IPS`（=不启用白名单，admin 另有登录密码兜底）
- [x] A3. 验证端口已收窄：`docker compose ps` 正常 + `ss -tlnp | grep -E '3306|8000'` 只显示 127.0.0.1 绑定（已确认）
- [x] A4. 容器内回归：已重建镜像并确认 194 passed（2026-08-24）
- [x] A5. 浏览器走 Nginx 入口确认登录/首页正常

## A2. 同步 2026-08-24 静态文件修复（C2 产物）

- [x] A6. `git pull` 后 `docker compose up -d`——已完成，frontend 已重建（2026-08-24）
- [x] A7. 验证 admin 静态样式：`curl http://localhost/static/admin/css/base.css` 返回 200（2026-08-24）
- [x] A8. 验证 `/media/`——首次测得 200，系 SPA 兜底返回 index.html（无文件泄露，语义误导）；已加显式 404 并推送（提交 fb78f8b），服务器拉取重建后应为 404

## B. 一次性运维

- [x] B1. 注册 cron 每日 8:00 采集——已完成（2026-08-24）：`crontab -e` 注册 `0 8 * * *`，`crontab -l` 确认
- [x] B2. 确认 cron 脚本含 build_index——已验证：脚本内采集后自动重建索引（本次输出"中央 103 + 地方 73 = 176 条"）
- [ ] B3. 次日验证：cron 于 08-24 下午注册（`0 8 * * *` 每天 8:00），**首次自动执行为 08-25 早上 8 点**。当天 8:30 后 `tail -30 /var/log/crawl.log` 应见三段日志 + 各站点统计，无 telemetry 噪音（已修复，提交 5d747bc）
- [x] B4. 服务器同步最新提交——已完成（2026-08-24）：git pull（含 crawl.sh 权限位冲突处理：checkout + `git config core.filemode false`）→ backend 重建 → media 验证
- [x] B5. frontend 强制重建加载新 nginx.conf（`--force-recreate`，单文件挂载 inode 陷阱，见 HANDOVER §8）→ media 404 / static 200 / 首页 200 三项验证
- [x] B6. 同步 D1/D2/D3/E3/E4a——服务器部分已完成（08-24：`up -d --build` 拉齐全部提交至 3602a2f，backend `(healthy)`，`/api/health/` 返回 ok；中途踩 healthcheck×ALLOWED_HOSTS 400 坑，见 HANDOVER §8）。剩余浏览器验证见 B7
- [ ] B7. 浏览器验证（D1/D2 功能落地 + 顺手看 D3）：
  - [ ] ① 政策详情页（D2）：登录 → 主页选有数据的日期 → 进"中央政策"编辑页 → **点击任一政策标题**（应为可点击链接）→ 详情页应显示：全文、分类标签、发文日期、"采集于 xx"/"手动录入"标识、"查看原文 ↗" → 点"查看原文"应新标签打开政府原页且标题一致
  - [ ] ② 重跑 Agent（D1）：进"Agent 自主生成"页 → 选有政策的日期 → 启动 → 进度条逐步推进（可能弹人在回路问题，回答后继续）→ 完成后下载 docx → 进"历史运行"应看到这条新记录（**改造前的旧记录不显示是预期行为**，它们 user 字段为空）
  - [ ] ③ 用户隔离（D1，可选但建议做）：服务器 `docker compose exec backend python manage.py createsuperuser` 建第二个账号 → 登录新账号 → "历史运行"应为空；再从浏览器地址栏复制第一个账号某条 run 的 trace URL 用新账号打开 → 应显示不存在（404 页面），证明隔离生效
  - [ ] ④ token 续期（D3）：无需专门验证——登录后放置超过 2 小时再操作，不掉线即说明自动续期在工作；平时使用中自然观察即可

### 脚本验证结论（2026-08-24，供面试参考）

- 增量去重正常：161 条跳过、0 重复入库；失败详情页不写库（财政部 12/34 详情页 502 属新加坡 IP 访问 mof 子域的已知环境问题，每次重跑有概率补上）
- 全程 18 分钟：礼貌限速（1~3s/详情页）+ 502 重试退避（3/6/9s）的预期成本
- 已知边界：商务部 jpaas API 第 2 页返回同第 1 页（去重兜住）；粤文件共享列表页仅 1 条命中

## C. P0 剩余安全项（2026-08-24 结项）

- [x] C1. HTTPS + HTTP 安全响应头——**降级为不做**（前置条件是域名；面试口径："HTTP/IP 部署，内网落地时按等保要求补 HTTPS 与安全响应头"）
- [x] C2. `/static/`、`/media/` 静态文件服务——已完成（2026-08-24）：`backend_static` 共享卷挂入 frontend，nginx `alias` 直接服务 admin 静态；`/media/` 反代移除（docx 走鉴权 API，暴露 media 反而绕过登录）。同步见 A6-A8
- [x] C3. 登录/API 限流、备份恢复演练、密钥轮换——**随 C1 降级为不做**，面试同口径

## D. P1 演示价值提升（按面试 ROI 排序，均可交给 AI 实现）

- [x] D1. AgentRun 用户隔离——已完成（2026-08-24）：`user` 外键 + 迁移 0003；trace/answer/download 越权 404（不泄露存在性）、列表只含本人、历史 run（user=null）不可见、未登录 401；新增 7 个隔离测试，全量 201 passed。**部署后需用演示账号重跑一次 Agent**（旧 run 无归属不再显示，T6 历史回看依赖）
- [x] D2. 政策详情页 + 来源/发布日期/采集日期展示——已完成（2026-08-24）：`/api/policies/detail/` + `PolicyDetail.vue`（`/policy/:source/:id`），编辑页标题可点击；详情页含原文链接与采集时间/手动录入标记。新增 8 个后端测试（含非数字 id 404、source 校验 400）
- [x] D3. 前端接 refresh token——已完成（2026-08-24）：401 拦截器单飞刷新 + 重放原请求，登录接口 401 不触发；access 2h 过期静默续期
- [x] D4. Celery/RQ + Redis 异步化——**决定不做**（2026-08-24）：工作量 2-3 天且演示价值增量低。面试不回避，按 PLAYBOOK §4.2 话术讲"多 worker 边界 + Redis 方案"（当前单 worker 内线程 + DB 状态持久化的取舍，以及迁移路径），见 G3

## E. P2 可信度改进（2026-08-24 分级：E3/E4a 做，其余明确不做）

- [ ] E1. RAG 正文片段真正参与摘要上下文——**不做**：会引出 embedding 选型/chunk 策略/rerank/效果评估一连串深水区提问，当前口径"rag_search 是检索建议"反而干净（话术见 PLAYBOOK §3）
- [ ] E2. 评估集版本化 + `eval_reports/` 入库——**不做**：重跑消融要花 DeepSeek 费用；面试口径"历史结果，复现路径已知（run_eval），评估方法论可讲"（PLAYBOOK §5）
- [x] E3. "Critic 修复率"改名"建议重规划率"——已完成（2026-08-24）：代码显示文案（metrics/reporter/runner/run_eval）+ README 消融表 + PLAYBOOK T10 + PREP Q5 全部更名；英文 key `critic_replan_rate` 本就准确未动。改名理由本身是面试加分点（指标口径严谨）
- [x] E4a. 健康检查端点 `/api/health/`——已完成（2026-08-24）：匿名可访问（探活不带凭据），返回 status/db；DB 异常返回 503。docker-compose backend 挂 healthcheck（python urllib 探活），frontend 改为 `condition: service_healthy` 启动顺序。新增 2 个测试
- [ ] E4b. 接口分页——**不做**：166 条数据分页价值低，且引出深度分页/cursor 等提问；前端三处列表全要改
- [ ] E4c. 爬虫失败告警 / robots 记录——**不做**：需接通知渠道（第三方依赖）；现状口径"失败不落库 + 日志可查 + 每周抽检（F 区）"已自洽

## F. 周期性运维（每周约 10 分钟）

- [ ] F1. 抽检日期解析质量（无法解析日期时会以当前时间写库，HANDOVER §4）
- [ ] F2. 分类分布 + 空正文抽检（命令在 HANDOVER §5 质量抽检段）
- [ ] F3. 盯三个脆弱点：财政部（间歇 502）、商务部（内部 JSON 接口）、粤文件按标题含"广东"分流
- [ ] F4. DeepSeek 账户余额

## G. 面试准备（投递前 1-2 周集中做）

- [ ] G1. 按 `interview/INTERVIEW_PLAYBOOK.md` §6 的 24 小时清单逐项执行（demo 账号、D1/D2 日期、预跑 T4/T5、容器 healthy、余额）
- [ ] G2. 背熟核心数字：166 条 / 约 210 测试 / 80% 覆盖率门槛 / 消融表（指标口径：建议重规划率）
- [ ] G3. 练到脱口而出：§4.3"广东不是上海"、§4.2"多 worker 边界 + Redis 方案"、§4.2"用户隔离 404 防枚举"
- [ ] G4. 3 分钟 STAR 介绍（§1.3）对着镜子讲两遍
- [ ] G5. 熟读 `ARCHITECTURE.md`（零基础架构图）——应对"给非技术的人讲清楚系统"类问题；面试官不同背景时按该文档的分层切换详略
- [ ] G6. 用 `PROJECT_INTRO.md` 的中英文简历条目更新简历（可裁到 4 条）；英文版留作外企/英文 JD 备用
- [ ] G7. 过一遍 `RUNBOOK.md` 故障排查表——"线上出问题你怎么办"类问题的答题素材（健康检查→容器日志→单站 dry-run 的排查顺序）

## 推荐路线（时间紧张时）

A → B → G → D1 + D2 → 其余按余量取舍。C/E 做不完的价值在于面试时能精确说出"为什么还没做、怎么做"。

## 已完成存档（2026-08-23）

- 端口 3306/8000 改绑 127.0.0.1、ADMIN_ALLOWED_IPS 传入容器、中间件防 XFF 伪造（提交 4582821）
- Critic 解析失败记 warning、publish_time 反序列化恢复 datetime（提交 4582821）
- 历史文档清理与死代码删除（提交 6a749f4），均已推送 Gitee + GitHub

## 已完成存档（2026-08-24）

- 服务器同步 2026-08-23 修复：端口收窄已验证（A1-A3、A5），镜像重建后 194 passed（A4）
- C2 静态文件服务：nginx 挂共享卷直接服务 /static/（A6-A7 已验证 200）
- /media/ 显式 404（提交 fb78f8b）、ChromaDB 遥测噪音关闭（提交 5d747bc）
- crawl.sh 双修复：Docker 自动识别（2c54d27）+ python -u 禁用输出缓冲（1db604d），手动全量跑通；仓库内标记可执行位（bf23bfb）
- cron 注册完成；nginx.conf 单文件挂载 inode 陷阱记入 HANDOVER §8（0597c15）
- C1/C3 安全项降级为不做，面试口径固定
