<p align="center">
  <h1 align="center">Content Creator Studio</h1>
  <p align="center">
    <strong>Multi-agent AI content creation platform built with LangGraph, FastAPI, and a progressively refactored DDD architecture.</strong>
  </p>
  <p align="center">
    <a href="#overview">Overview</a> &bull;
    <a href="#current-architecture">Architecture</a> &bull;
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#api-surface">API</a> &bull;
    <a href="#repository-layout">Layout</a>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-Orchestrated-purple?logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License" />
</p>

<p align="center">
  <strong>English</strong> | <a href="./README.zh-CN.md">中文</a>
</p>

---

## Overview

Content Creator Studio is an AI-assisted content workflow for solo creators and small teams. The backend uses LangGraph to orchestrate agent execution, FastAPI to expose HTTP APIs, and a progressively introduced DDD structure to separate domain logic, application services, adapters, and infrastructure.

The repository now reflects a refactor in progress: the new architecture is live in the codebase, while selected legacy paths are preserved for compatibility and migration.

## Current Architecture

### Active agents

The current graph routes requests to **3 core agents**:

| Agent | Best for | Notes |
| --- | --- | --- |
| `SimpleAgent` | quick chat and lightweight tasks | fastest path |
| `ReActAgent` | search, tool use, factual tasks | integrates tool calling and knowledge search |
| `ReflectionAgent` | high-quality long-form output | supports refinement and deeper reasoning |

### Key changes from the older design

- `PlanSolveAgent` is no longer part of the active main flow; its capability is being consolidated into `ReflectionAgent`.
- `RAGAgent` has been downgraded into a reusable tool, `KnowledgeSearchTool`.
- Routing is moving from hard-coded logic to strategy-based configuration via `app/config/routing_config.yaml`.
- Memory recall and persistence are centralized through application services such as `ContextBuilder` and `MemoryAppService`.
- Legacy compatibility is still available under `app/agents/_legacy/` and `app/adapters/`.

### Main capabilities

- LangGraph-driven execution with routing, quality gate, refinement, and memory save steps
- Long-term memory for chat, content, and knowledge flows
- Knowledge retrieval backed by in-memory vectors or Milvus
- Streaming APIs, video generation workflow, and observability endpoints
- Configurable external tool integration through the tool registry and MCP bridge

## Quick Start

### Prerequisites

- Python 3.11+
- An API key compatible with the configured LLM provider
- Optional: Redis and Milvus for extended features

### Run locally

```bash
git clone https://github.com/kingdoja/content-creator-studio.git
cd content-creator-studio/iccp-langchain

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

After startup:

- App root: `http://localhost:8000/`
- OpenAPI docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## API Surface

Important API groups currently exposed from `app.main`:

- `/api/v1/content` for content creation, cover generation, evaluation, and video-related flows
- `/api/v1/chat` for chat sessions and messaging
- `/api/v1/knowledge` for knowledge base operations
- `/api/v1/memory` for recall and preference APIs
- `/api/v1/observability` and `/api/v1/metrics` for monitoring
- `/api/v1/auth` for authentication and WeChat-related auth routes

## Repository Layout

```text
onePersonCompany/
├── iccp-langchain/           # Main FastAPI + LangGraph application
├── docs/                     # Local project notes (ignored from Git)
├── ideas/                    # Local ideation notes (ignored from Git)
├── miniprogram/              # Local mini-program work area (ignored from Git)
├── web/                      # Local web experiments (ignored from Git)
└── _local_only/              # Local-only files (ignored from Git)
```

Inside `iccp-langchain/`:

```text
app/
├── agents/                   # graph, router_v2, analyzers, core agents, legacy agents
├── adapters/                 # compatibility adapters
├── api/v1/                   # HTTP routes
├── config/                   # settings and routing config
├── domain/                   # domain models and interfaces
├── memory/                   # memory infra
├── observability/            # tracing and monitoring helpers
├── rag/                      # embeddings and vector index
├── services/                 # application services
└── tools/                    # web search, fact check, knowledge search, MCP bridge
tests/                        # automated tests
scripts/                      # migration and verification utilities
```

## Notes For Contributors

- The repo intentionally ignores local AI-tooling directories and generated cover images.
- Runtime-generated assets should stay out of version control unless there is a strong product reason to ship them.
- The most detailed backend documentation is in [`iccp-langchain/README.md`](./iccp-langchain/README.md).
- Release notes for the architecture refactor live in [`iccp-langchain/CHANGELOG.md`](./iccp-langchain/CHANGELOG.md).

## License

MIT
