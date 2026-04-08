<p align="center">
  <h1 align="center">Content Creator Studio</h1>
  <p align="center">
    <strong>基于 LangGraph、FastAPI 与渐进式 DDD 重构的多 Agent 内容创作平台。</strong>
  </p>
  <p align="center">
    <a href="#项目概览">项目概览</a> &bull;
    <a href="#当前架构">当前架构</a> &bull;
    <a href="#快速开始">快速开始</a> &bull;
    <a href="#接口概览">接口概览</a> &bull;
    <a href="#仓库结构">仓库结构</a>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-编排-purple?logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License" />
</p>

<p align="center">
  <a href="./README.md">English</a> | <strong>中文</strong>
</p>

---

## 项目概览

Content Creator Studio 面向独立创作者和小团队，提供基于 AI 的内容创作工作流。后端使用 LangGraph 负责编排 Agent 执行，FastAPI 提供 HTTP 接口，同时逐步引入 DDD 分层，将领域模型、应用服务、适配器和基础设施解耦。

当前仓库已经进入重构阶段：新架构代码已经落地，同时保留了部分旧路径与兼容层，便于渐进式迁移。

## 当前架构

### 当前主流程中的 3 个核心 Agent

| Agent | 适用场景 | 说明 |
| --- | --- | --- |
| `SimpleAgent` | 简单问答、轻量请求 | 延迟最低 |
| `ReActAgent` | 搜索、工具调用、事实型任务 | 集成联网检索与知识检索工具 |
| `ReflectionAgent` | 高质量长文、深度生成 | 支持反思与多轮优化 |

### 相比旧版设计的主要变化

- `PlanSolveAgent` 已不再作为主流程的活跃节点，相关能力逐步合并进 `ReflectionAgent`
- `RAGAgent` 已下沉为通用工具 `KnowledgeSearchTool`
- 路由从硬编码逻辑逐步迁移到基于策略和 YAML 配置的模式，配置文件位于 `app/config/routing_config.yaml`
- 记忆召回与持久化统一收敛到 `ContextBuilder`、`MemoryAppService` 等应用服务
- 旧实现仍保留在 `app/agents/_legacy/` 与 `app/adapters/` 中，方便兼容和迁移

### 当前能力范围

- 基于 LangGraph 的路由、质量门控、反思修订、记忆保存执行链
- 覆盖聊天、内容、知识库的长期记忆能力
- 支持内存向量库或 Milvus 的知识检索
- 支持流式输出、视频生成流程和观测接口
- 支持通过工具注册表和 MCP Bridge 接入外部工具

## 快速开始

### 环境要求

- Python 3.11+
- 可用的 LLM 服务 API Key
- 可选：Redis、Milvus

### 本地启动

```bash
git clone https://github.com/kingdoja/content-creator-studio.git
cd content-creator-studio/iccp-langchain

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- 首页：`http://localhost:8000/`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

## 接口概览

`app.main` 当前挂载的主要接口分组包括：

- `/api/v1/content`：内容生成、封面生成、评估、视频相关流程
- `/api/v1/chat`：聊天会话与消息
- `/api/v1/knowledge`：知识库相关能力
- `/api/v1/memory`：记忆召回与偏好设置
- `/api/v1/observability`、`/api/v1/metrics`：监控与观测
- `/api/v1/auth`：认证与微信相关认证接口

## 仓库结构

```text
onePersonCompany/
├── iccp-langchain/           # 主应用：FastAPI + LangGraph
├── docs/                     # 本地文档目录（已忽略）
├── ideas/                    # 本地想法记录（已忽略）
├── miniprogram/              # 本地小程序工作目录（已忽略）
├── web/                      # 本地 Web 实验目录（已忽略）
└── _local_only/              # 本地专用文件（已忽略）
```

`iccp-langchain/` 内部主要结构：

```text
app/
├── agents/                   # graph、router_v2、分析器、核心 agent、legacy agent
├── adapters/                 # 兼容适配层
├── api/v1/                   # HTTP 路由
├── config/                   # settings 与路由配置
├── domain/                   # 领域模型与接口
├── memory/                   # 记忆基础设施
├── observability/            # tracing 与监控
├── rag/                      # embedding 与向量索引
├── services/                 # 应用服务
└── tools/                    # web search、fact check、knowledge search、MCP bridge
tests/                        # 自动化测试
scripts/                      # 迁移与校验脚本
```

## 贡献说明

- 仓库现在会忽略本地 AI 协作目录和运行时生成的封面图片
- 运行时产物默认不进入版本控制，除非它们本身就是产品交付物
- 更详细的后端说明见 [`iccp-langchain/README.md`](./iccp-langchain/README.md)
- 本次架构重构的变更说明见 [`iccp-langchain/CHANGELOG.md`](./iccp-langchain/CHANGELOG.md)

## 许可证

MIT
