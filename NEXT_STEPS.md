# 后续工作对照清单

> 生成于 2026-08-24。本文是执行顺序视图，勾选跟踪进度；细节与原理见 `HANDOVER.md`，演示话术见 `INTERVIEW_PLAYBOOK.md`。
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
- [ ] B3. 次日验证：8 点后 `tail -30 /var/log/crawl.log` 应见三段日志 + 各站点统计，无 telemetry 噪音（已修复，提交 5d747bc）
- [x] B4. 服务器同步最新提交——已完成（2026-08-24）：git pull（含 crawl.sh 权限位冲突处理：checkout + `git config core.filemode false`）→ backend 重建 → media 验证
- [x] B5. frontend 强制重建加载新 nginx.conf（`--force-recreate`，单文件挂载 inode 陷阱，见 HANDOVER §8）→ media 404 / static 200 / 首页 200 三项验证
- [ ] B6. 同步 D1 用户隔离：`git pull` → `docker compose up -d --build backend`（含迁移 0003，entrypoint 自动 migrate）→ 演示账号登录重跑一次 Agent → 用另一账号验证看不到对方 run

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

## 已完成存档（2026-08-24）

- 服务器同步 2026-08-23 修复：端口收窄已验证（A1-A3、A5），镜像重建后 194 passed（A4）
- C2 静态文件服务：nginx 挂共享卷直接服务 /static/（A6-A7 已验证 200）
- /media/ 显式 404（提交 fb78f8b）、ChromaDB 遥测噪音关闭（提交 5d747bc）
- crawl.sh 双修复：Docker 自动识别（2c54d27）+ python -u 禁用输出缓冲（1db604d），手动全量跑通；仓库内标记可执行位（bf23bfb）
- cron 注册完成；nginx.conf 单文件挂载 inode 陷阱记入 HANDOVER §8（0597c15）
- C1/C3 安全项降级为不做，面试口径固定
