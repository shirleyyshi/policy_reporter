# Policy Reporter

> 基于 ReAct 范式的财税政策日报自主 Agent — 输入一个日期，Agent 自动编排工具链生成政策日报 Word 文档。

![CI](https://github.com/shirleyyshi/policy_reporter/actions/workflows/test.yml/badge.svg)
![Coverage](https://codecov.io/gh/shirleyyshi/policy_reporter/branch/main/graph/badge.svg)

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM | DeepSeek-chat |
| Agent | 自研 ReAct 框架（Actuator / Critic / Replanner / Terminator） |
| 后端 | Django 5.2 + DRF + SimpleJWT + gunicorn |
| 数据 | MySQL 8.0 + ChromaDB（向量检索） |
| 前端 | Vue 3 + Element Plus + Vite |
| 部署 | Docker Compose + Nginx |
| 测试 | pytest + pytest-cov（覆盖率 82%，179 个测试） |

## 核心能力

- **ReAct 完整循环**：Thought → Action → Observation → Thought，LLM 基于上一步工具返回结果决策
- **10 个工具动态编排**：抓取 / 清洗 / 去重 / 分类 / RAG 检索 / 摘要 / 格式化 / 人在回路
- **Critic 质量检查**：检测原地打转 / 数据为空 / 摘要质量差，触发 Replanner
- **State DB 持久化**：支持 gunicorn 多 worker，服务重启后状态不丢
- **RAG episodic memory**：跨会话经验复用，第二次运行参考历史决策
- **LLM-as-judge 评估**：format / coverage / language 三维无参考打分 + 4 组消融实验

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/shirleyyshi/policy_reporter.git
cd policy_reporter

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 SECRET_KEY / DB_ROOT_PASSWORD / DEEPSEEK_API_KEY

# 3. 启动
docker-compose up -d --build

# 4. 创建超级用户 + 爬数据
docker-compose exec backend python manage.py createsuperuser
docker-compose exec backend python manage.py crawl_policies --all
docker-compose exec backend python manage.py build_index

# 5. 访问 http://localhost
```

## 运行测试

```bash
cd backend
pip install -r requirements-dev.txt
pytest --cov=apps --cov-report=term-missing
```

## 项目结构

```
├── backend/                # Django 后端
│   ├── apps/
│   │   ├── agent/          # ReAct Agent 引擎
│   │   │   ├── core.py     # 主循环（Actuator/Critic/Terminator）
│   │   │   ├── tools.py    # 10 个工具
│   │   │   ├── rag.py      # ChromaDB 向量检索 + episodic memory
│   │   │   ├── prompts.py  # LLM prompt 构造
│   │   │   ├── eval/       # 消融实验 + LLM-as-judge
│   │   │   └── test_*.py   # 单元测试
│   │   └── report/         # 政策 CRUD + 爬虫 + docx 导出
│   ├── config/             # Django settings
│   ├── conftest.py         # pytest 共享 fixtures
│   └── pytest.ini          # pytest 配置
├── frontend/               # Vue 3 前端
│   └── src/views/          # 登录/首页/编辑页/Agent 运行页
├── .github/workflows/      # GitHub Actions CI
├── docker-compose.yml      # 三容器编排（db + backend + frontend）
└── scripts/                # 爬虫定时脚本
```
