<p align="center">
  <h1 align="center">Content Creator Studio</h1>
  <p align="center">
    <strong>Multi-Agent AI Content Creation Platform powered by LangGraph</strong>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#features">Features</a> &bull;
    <a href="#architecture">Architecture</a> &bull;
    <a href="#api-reference">API</a> &bull;
    <a href="#deployment">Deploy</a>
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
  <strong>English</strong> | <a href="./README.zh-CN.md">中文</a>
</p>

---

An intelligent content creation platform that orchestrates **5 specialized AI agents** through a LangGraph state machine — each agent handles different content tasks with automatic routing, quality gating, long-term memory, and RAG-powered knowledge retrieval.

Built for solo creators and small teams who want to produce high-quality, fact-checked content across multiple domains without prompt engineering headaches.

## Why This Project?

| Problem | Solution |
|---------|----------|
| Generic LLM outputs lack domain depth | **7 domain-specific prompt templates** (Finance, AI, Tech, Lifestyle, Books, Investment, Growth) |
| Single-agent can't handle diverse tasks | **5 specialized agents** auto-routed by task analysis |
| LLM hallucinations in factual content | **Fact-checking tools** + web search with source citations |
| No context between sessions | **Long-term memory system** — episodic, semantic & procedural |
| Hard to maintain quality at scale | **Quality gate** with automatic reflection & refinement loop |

## Features

### Multi-Agent Orchestration

Five purpose-built agents, automatically selected based on your task:

| Agent | Best For | How It Works |
|-------|----------|--------------|
| **ReAct** | Real-time data, fact-heavy content | Tool-calling loop (search, fact-check) |
| **Reflection** | Deep, polished articles | Generate → critique → refine cycle |
| **Plan-and-Solve** | Long-form, complex topics | Plan steps → execute each → synthesize |
| **RAG** | Knowledge-base powered content | Retrieve relevant docs → augmented generation |
| **Simple** | Quick Q&A, casual chat | Direct LLM response, low latency |

### Intelligent Routing

```
User Input → Task Analysis → Agent Selection → Execution → Quality Gate → Output
                                                              ↓ (fail)
                                                        Reflection Refine
```

The router analyzes complexity, domain, and real-time needs to pick the optimal agent — and remembers your preferences over time.

### Long-Term Memory

- **Episodic memory** — remembers past interactions and content
- **Semantic memory** — stores knowledge and facts
- **Procedural memory** — learns your style preferences
- **Memory linking** — connects related memories for richer context
- **Cross-module sharing** — chat, content, video, and knowledge all share the same memory layer

### Content Pipeline

- **7 domain categories** with specialized prompts and tone
- **Streaming generation** via SSE for real-time feedback
- **Multi-agent comparison** — run the same task through different agents and compare
- **Content evaluation & scoring** — automated quality assessment
- **Cover image generation** — AI-generated article covers
- **Story-to-video** — script polishing + text-to-video generation

### Tool System

- **Web Search** — Tavily + DuckDuckGo fallback with time-aware queries
- **Fact Checking** — cross-reference claims against search results
- **MCP Bridge** — plug in external MCP-compatible tools dynamically
- **Tool Registry** — unified interface, agents don't care about implementation details

### Knowledge Base (RAG)

- Upload documents → auto-chunking → embedding → vector retrieval
- Supports **in-memory** or **Milvus** vector backends
- Optional time-decay weighting for freshness-sensitive domains
- Knowledge entries are also saved as semantic memories for cross-module recall

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        LangGraph State Machine                   │
│                                                                  │
│  START → memory_load → route ──┬── react_agent ──┐               │
│                                ├── reflection    ├→ quality_gate │
│                                ├── plan_solve    │    │    │     │
│                                ├── rag_agent     │   pass  fail  │
│                                └── simple        ┘    │    │     │
│                                                  finalize  │     │
│                                                    │  reflection  │
│                                                    │  _refine     │
│                                                memory_save → END │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴────┐        ┌─────┴─────┐        ┌────┴────┐
    │ Tools   │        │  Memory   │        │   RAG   │
    │ Search  │        │ Episodic  │        │ Vector  │
    │ Fact    │        │ Semantic  │        │ Store   │
    │ Check   │        │ Procedural│        │ Milvus  │
    │ MCP     │        │ Prefs     │        │         │
    └─────────┘        └───────────┘        └─────────┘
```

### Project Structure

```
iccp-langchain/
├── app/
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Centralized configuration
│   ├── agents/                # LangGraph agents & orchestration
│   │   ├── graph.py           # State machine definition
│   │   ├── routing.py         # Intelligent agent routing
│   │   ├── react_agent.py     # ReAct tool-calling agent
│   │   ├── reflection_agent.py
│   │   ├── plan_solve_agent.py
│   │   └── simple_agent.py
│   ├── prompting/             # Domain-specific prompt optimizer
│   ├── memory/                # Long-term memory system
│   ├── rag/                   # Knowledge base & retrieval
│   ├── tools/                 # Tool registry & implementations
│   ├── services/              # Business logic layer
│   ├── api/v1/                # REST API routes
│   └── auth/                  # JWT + WeChat mini-program auth
├── frontend/                  # React 18 + Vite + TailwindCSS
├── iccp-miniprogram/          # WeChat Mini Program client
├── tests/                     # Pytest test suite
├── docker-compose.yml         # One-command deployment
└── requirements.txt           # Python dependencies
```

## Quick Start

### Prerequisites

- Python 3.11+
- An OpenAI API key (GPT-4 recommended)
- Redis (optional, for caching)

### 1. Clone & Install

```bash
git clone https://github.com/kingdoja/content-creator-studio.git
cd content-creator-studio/iccp-langchain

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4

# Optional
TAVILY_API_KEY=tvly-your-key      # Web search
REDIS_URL=redis://localhost:6379   # Caching
RAG_VECTOR_BACKEND=memory         # or "milvus"
```

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Docker (Recommended)

```bash
cd iccp-langchain
docker compose up -d
```

This starts the backend (`:8000`), frontend (`:3000`), and Redis.

## API Reference

### Content Creation

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/content/create` | Create content with auto agent routing |
| `POST` | `/api/v1/content/create/stream` | Streaming content generation (SSE) |
| `GET`  | `/api/v1/content/categories` | List available content categories |
| `POST` | `/api/v1/content/suggest-agent` | Get agent recommendation for a task |
| `POST` | `/api/v1/content/compare` | Compare outputs from multiple agents |
| `POST` | `/api/v1/content/evaluate` | Score and evaluate content quality |
| `POST` | `/api/v1/content/refine` | Refine/polish existing content |
| `POST` | `/api/v1/content/generate-cover` | Generate article cover image |
| `POST` | `/api/v1/content/generate-story-video` | Story script → video generation |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chat/sessions` | Create a new chat session |
| `POST` | `/api/v1/chat/sessions/{id}/message` | Send message |
| `POST` | `/api/v1/chat/sessions/{id}/message/stream` | Streaming chat (SSE) |

### Memory & Knowledge

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/v1/memory/recall` | Recall relevant memories |
| `GET`  | `/api/v1/memory/entries` | List memory entries |
| `PUT`  | `/api/v1/memory/preferences` | Update user preferences |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Orchestration** | LangGraph 0.2, LangChain 0.3 |
| **LLM** | OpenAI GPT-4 (configurable) |
| **Backend** | FastAPI, Uvicorn, Pydantic v2 |
| **Database** | SQLAlchemy 2.0, SQLite / PostgreSQL |
| **Vector Store** | In-memory / Milvus |
| **Cache** | Redis 7 |
| **Search** | Tavily, DuckDuckGo |
| **Frontend** | React 18, Vite 5, TailwindCSS |
| **Mini Program** | WeChat WXML/WXSS |
| **Deployment** | Docker Compose |
| **Monitoring** | Prometheus, LangSmith (optional) |

## Deployment

### Docker Compose (Production)

```bash
docker compose up -d --build
```

| Service | Port | Description |
|---------|------|-------------|
| Backend | 8000 | FastAPI + Uvicorn |
| Frontend | 3000 | React SPA via Nginx |
| Redis | 6379 | Cache & session store |

### WeChat Mini Program

The `iccp-miniprogram/` directory contains a WeChat Mini Program client that connects to the same backend API. See [`iccp-miniprogram/README.md`](iccp-langchain/iccp-miniprogram/README.md) for setup instructions.

## Configuration

Key environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | No | Model name (default: `gpt-4`) |
| `TAVILY_API_KEY` | No | Tavily search API key |
| `REDIS_URL` | No | Redis connection URL |
| `RAG_VECTOR_BACKEND` | No | `memory` (default) or `milvus` |
| `MCP_ENABLED` | No | Enable MCP tool bridge |
| `WX_APPID` | No | WeChat Mini Program App ID |
| `LANGCHAIN_TRACING_V2` | No | Enable LangSmith tracing |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with LangGraph + FastAPI for the solo creator economy.<br/>
  If this project helps you, consider giving it a star!
</p>
