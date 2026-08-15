# Policy Reporter Frontend

> 财税政策日报 Agent 的前端——基于 Vue 3 + Element Plus + Vite，提供政策管理、Agent 运行可视化、人在回路交互。

## 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | Vue 3（Composition API） |
| UI 库 | Element Plus |
| 路由 | Vue Router 4（懒加载） |
| 状态 | Pinia（选择状态管理） |
| HTTP | Axios |
| 构建 | Vite 5 |
| 部署 | Nginx（多阶段 Docker 构建） |

## 页面结构

| 路由 | 文件 | 功能 |
|------|------|------|
| `/login` | [Login.vue](src/views/Login.vue) | JWT 登录 |
| `/` | [Home.vue](src/views/Home.vue) | 首页：政策数量统计 + 日期选择 + 进入 Agent 运行 |
| `/central` | [CentralEditor.vue](src/views/CentralEditor.vue) | 中央政策列表（勾选导出） |
| `/local` | [LocalEditor.vue](src/views/LocalEditor.vue) | 地方政策列表（勾选导出） |
| `/legal` | [LegalEditor.vue](src/views/LegalEditor.vue) | 法律法规编辑 |
| `/agent/runs` | [AgentRuns.vue](src/views/AgentRuns.vue) | Agent 历史运行列表 |
| `/agent/run/:id` | [AgentRun.vue](src/views/AgentRun.vue) | 单次运行详情：实时 trace + 人在回路弹窗 |

## 开发

```bash
# 安装依赖
npm install

# 开发模式（默认 5173 端口，需后端跑在 8000）
npm run dev

# 生产构建（输出到 dist/，Nginx 托管）
npm run build
```

### 环境变量

复制 [.env.example](.env.example) 为 `.env`：

```env
# 后端 API 地址，开发时填 http://localhost:8000
# Docker 构建时留空（用相对路径，由 Nginx 反代）
VITE_API_BASE=
```

## 与后端联调

- 后端 API 前缀：`/api/`
- JWT 登录：`POST /api/auth/login/` → 返回 token，存 localStorage
- Agent 运行：`POST /api/agent/runs/` 创建 → `GET /api/agent/runs/{id}/state/` 每 2 秒轮询状态
- 人在回路：状态变 `waiting_human` 时弹窗，`POST /api/agent/runs/{id}/submit/` 提交用户输入

## 部署

Docker 多阶段构建（见 [Dockerfile](Dockerfile)）：
1. `node:20` 阶段：`npm ci && npm run build` 生成 dist/
2. `nginx:alpine` 阶段：拷贝 dist/ 到 `/usr/share/nginx/html`，配置 [nginx.conf](nginx.conf) 反代后端

生产环境由根目录 [docker-compose.yml](../docker-compose.yml) 编排，Nginx 同时托管前端静态文件和反代 `/api/` 到 backend 容器。
