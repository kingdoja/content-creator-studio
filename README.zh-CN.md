<p align="center">
  <h1 align="center">Content Creator Studio</h1>
  <p align="center">
    <strong>基于 LangGraph 的多 Agent 智能内容创作平台</strong>
  </p>
  <p align="center">
    <a href="#快速开始">快速开始</a> &bull;
    <a href="#核心功能">核心功能</a> &bull;
    <a href="#系统架构">架构</a> &bull;
    <a href="#api-接口">API</a> &bull;
    <a href="#部署">部署</a>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-0.2-purple?logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/LangChain-0.3-green?logo=langchain&logoColor=white" alt="LangChain" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License" />
</p>

<p align="center">
  <a href="./README.md">English</a> | <strong>中文</strong>
</p>

---

一个智能内容创作平台，通过 LangGraph 状态机编排 **5 个专业 AI Agent** —— 每个 Agent 处理不同类型的内容任务，支持自动路由、质量门控、长期记忆和 RAG 知识检索。

专为独立创作者和小团队打造，无需复杂的 Prompt 工程，即可在多个领域产出高质量、经过事实核查的内容。

## 为什么做这个项目？

| 痛点 | 解决方案 |
|------|----------|
| 通用大模型输出缺乏领域深度 | **7 个领域专属 Prompt 模板**（财经、AI、科技、生活、书籍、投资、成长） |
| 单一 Agent 难以应对多样化任务 | **5 个专业 Agent** 根据任务自动路由分配 |
| 大模型在事实性内容上容易"幻觉" | **事实核查工具** + 联网搜索 + 来源引用 |
| 会话之间没有上下文延续 | **长期记忆系统** —— 情景记忆、语义记忆、程序记忆 |
| 大规模产出难以保证质量 | **质量门控** + 自动反思修正循环 |

## 核心功能

### 多 Agent 编排

五个专用 Agent，根据任务自动选择最合适的执行者：

| Agent | 最佳场景 | 工作方式 |
|-------|----------|----------|
| **ReAct** | 实时数据、事实密集型内容 | 工具调用循环（搜索 → 核查 → 生成） |
| **Reflection** | 深度、精打磨的文章 | 生成 → 自我批判 → 迭代优化 |
| **Plan-and-Solve** | 长文、复杂主题 | 规划步骤 → 逐步执行 → 综合整理 |
| **RAG** | 基于知识库的内容 | 检索相关文档 → 增强生成 |
| **Simple** | 快速问答、日常闲聊 | 直接调用大模型，低延迟 |

### 智能路由

```
用户输入 → 任务分析 → Agent 选择 → 执行 → 质量门控 → 输出
                                               ↓ (不通过)
                                          反思修正 → 重新输出
```

路由器会分析任务复杂度、所属领域和实时性需求，选择最优 Agent 执行 —— 并随时间学习你的使用偏好。

### 长期记忆系统

- **情景记忆（Episodic）** —— 记住过去的交互和创作内容
- **语义记忆（Semantic）** —— 存储知识和事实
- **程序记忆（Procedural）** —— 学习你的风格偏好
- **记忆链接** —— 关联相关记忆，提供更丰富的上下文
- **跨模块共享** —— 对话、内容创作、视频、知识库共享同一记忆层

### 内容创作管线

- **7 个领域板块** —— 各有专属 Prompt 和语气风格
- **流式生成** —— 基于 SSE 实时输出，所见即所得
- **多 Agent 对比** —— 同一任务交给不同 Agent，对比输出效果
- **内容评估评分** —— 自动化质量打分
- **封面图生成** —— AI 生成文章封面
- **剧情转视频** —— 剧本润色 + 文生视频

### 工具系统

- **联网搜索** —— Tavily + DuckDuckGo 双引擎，时效性查询自动加时间约束
- **事实核查** —— 交叉验证内容中的关键声明
- **MCP 桥接** —— 动态挂载外部 MCP 兼容工具
- **工具注册中心** —— 统一接口，Agent 无需关心底层实现

### 知识库（RAG）

- 上传文档 → 自动分块 → Embedding → 向量检索
- 支持 **内存** 或 **Milvus** 向量后端
- 可选时间衰减加权，适合时效敏感的领域
- 知识条目同步写入语义记忆，实现跨模块召回

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     LangGraph 状态机编排                          │
│                                                                  │
│  START → 记忆加载 → 路由 ──┬── ReAct Agent   ──┐                 │
│                            ├── Reflection     ├→ 质量门控        │
│                            ├── Plan-Solve     │   │    │        │
│                            ├── RAG Agent      │  通过  不通过     │
│                            └── Simple         ┘   │    │        │
│                                              最终整理   │        │
│                                                │  反思修正        │
│                                              记忆保存 → END      │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴────┐        ┌─────┴─────┐        ┌────┴────┐
    │  工具层  │        │  记忆层    │        │ RAG 层  │
    │ 联网搜索 │        │ 情景记忆   │        │ 向量存储 │
    │ 事实核查 │        │ 语义记忆   │        │ Milvus  │
    │ MCP桥接  │        │ 程序记忆   │        │         │
    └─────────┘        └───────────┘        └─────────┘
```

### 项目结构

```
iccp-langchain/
├── app/
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 统一配置
│   ├── agents/                # LangGraph Agent 与编排
│   │   ├── graph.py           # 状态机定义
│   │   ├── routing.py         # 智能路由逻辑
│   │   ├── react_agent.py     # ReAct 工具调用 Agent
│   │   ├── reflection_agent.py
│   │   ├── plan_solve_agent.py
│   │   └── simple_agent.py
│   ├── prompting/             # 领域 Prompt 优化器
│   ├── memory/                # 长期记忆系统
│   ├── rag/                   # 知识库与检索
│   ├── tools/                 # 工具注册中心与实现
│   ├── services/              # 业务逻辑层
│   ├── api/v1/                # REST API 路由
│   └── auth/                  # JWT + 微信小程序认证
├── frontend/                  # React 18 + Vite + TailwindCSS
├── iccp-miniprogram/          # 微信小程序客户端
├── tests/                     # Pytest 测试套件
├── docker-compose.yml         # 一键部署
└── requirements.txt           # Python 依赖
```

## 快速开始

### 环境要求

- Python 3.11+
- OpenAI API Key（推荐 GPT-4）
- Redis（可选，用于缓存）

### 1. 克隆与安装

```bash
git clone https://github.com/kingdoja/content-creator-studio.git
cd content-creator-studio/iccp-langchain

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的密钥：

```env
OPENAI_API_KEY=sk-你的密钥
OPENAI_MODEL=gpt-4

# 可选配置
TAVILY_API_KEY=tvly-你的密钥      # 联网搜索
REDIS_URL=redis://localhost:6379   # 缓存
RAG_VECTOR_BACKEND=memory         # 或 "milvus"
```

### 3. 启动

```bash
uvicorn app.main:app --reload --port 8000
```

API 地址：`http://localhost:8000`，交互式文档：`http://localhost:8000/docs`。

### Docker 一键启动（推荐）

```bash
cd iccp-langchain
docker compose up -d
```

自动启动后端（`:8000`）、前端（`:3000`）和 Redis。

## API 接口

### 内容创作

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/v1/content/create` | 创建内容（自动路由 Agent） |
| `POST` | `/api/v1/content/create/stream` | 流式内容生成（SSE） |
| `GET`  | `/api/v1/content/categories` | 获取内容板块列表 |
| `POST` | `/api/v1/content/suggest-agent` | 获取 Agent 推荐 |
| `POST` | `/api/v1/content/compare` | 多 Agent 对比输出 |
| `POST` | `/api/v1/content/evaluate` | 内容质量评估 |
| `POST` | `/api/v1/content/refine` | 内容润色优化 |
| `POST` | `/api/v1/content/generate-cover` | 生成文章封面图 |
| `POST` | `/api/v1/content/generate-story-video` | 剧情润色 + 文生视频 |

### 对话

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/v1/chat/sessions` | 创建对话会话 |
| `POST` | `/api/v1/chat/sessions/{id}/message` | 发送消息 |
| `POST` | `/api/v1/chat/sessions/{id}/message/stream` | 流式对话（SSE） |

### 记忆与知识库

| 方法 | 端点 | 说明 |
|------|------|------|
| `GET`  | `/api/v1/memory/recall` | 召回相关记忆 |
| `GET`  | `/api/v1/memory/entries` | 记忆条目列表 |
| `PUT`  | `/api/v1/memory/preferences` | 更新用户偏好 |

## 技术栈

| 层级 | 技术 |
|------|------|
| **编排引擎** | LangGraph 0.2、LangChain 0.3 |
| **大语言模型** | OpenAI GPT-4（可配置） |
| **后端框架** | FastAPI、Uvicorn、Pydantic v2 |
| **数据库** | SQLAlchemy 2.0、SQLite / PostgreSQL |
| **向量存储** | 内存 / Milvus |
| **缓存** | Redis 7 |
| **搜索引擎** | Tavily、DuckDuckGo |
| **前端** | React 18、Vite 5、TailwindCSS |
| **小程序** | 微信小程序（WXML/WXSS） |
| **部署** | Docker Compose |
| **监控** | Prometheus、LangSmith（可选） |

## 部署

### Docker Compose（生产环境）

```bash
docker compose up -d --build
```

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 | 8000 | FastAPI + Uvicorn |
| 前端 | 3000 | React SPA（Nginx 托管） |
| Redis | 6379 | 缓存与会话存储 |

### 微信小程序

`iccp-miniprogram/` 目录包含微信小程序客户端，对接同一套后端 API。详见 [`iccp-miniprogram/README.md`](iccp-langchain/iccp-miniprogram/README.md)。

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | 是 | OpenAI API 密钥 |
| `OPENAI_MODEL` | 否 | 模型名称（默认 `gpt-4`） |
| `TAVILY_API_KEY` | 否 | Tavily 搜索 API 密钥 |
| `REDIS_URL` | 否 | Redis 连接地址 |
| `RAG_VECTOR_BACKEND` | 否 | `memory`（默认）或 `milvus` |
| `MCP_ENABLED` | 否 | 启用 MCP 工具桥接 |
| `WX_APPID` | 否 | 微信小程序 App ID |
| `LANGCHAIN_TRACING_V2` | 否 | 启用 LangSmith 追踪 |

## 参与贡献

欢迎贡献！请按以下步骤操作：

1. Fork 本仓库
2. 创建功能分支（`git checkout -b feature/amazing-feature`）
3. 提交更改（`git commit -m '添加某某功能'`）
4. 推送分支（`git push origin feature/amazing-feature`）
5. 提交 Pull Request

## 许可证

本项目基于 MIT 许可证开源 —— 详见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  基于 LangGraph + FastAPI 构建，为独立创作者而生。<br/>
  如果这个项目对你有帮助，欢迎点个 Star！
</p>
