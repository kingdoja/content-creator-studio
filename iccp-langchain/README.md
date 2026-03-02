# ICCP LangChain - 多Agent内容创作平台

基于 **LangGraph + LangChain** 的多Agent智能内容创作平台，支持多板块 Prompt 优化、动态图编排路由、工具调用和可解释执行轨迹。

## 功能特性

- ✅ **多板块内容创作**：财经、人工智能、生活、科技、书籍、投资、成长等7+板块
- ✅ **LangGraph 动态编排**：路由执行 → 质量门控 → 必要时反思修订
- ✅ **三种 Agent**：ReAct（工具调用）、Reflection（反思改进）、Plan-and-Solve（规划分步）
- ✅ **智能路由**：根据任务特征（实时数据、深度、规划）自动选 Agent
- ✅ **工具调用**：LangChain 工具（网络搜索、事实核查）
- ✅ **可插拔工具层**：内置工具 + 自定义函数 + MCP 桥接（可选开关）
- ✅ **直白犀利表达**：prompt 要求要点与痛点先行、言语直白
- ✅ **Web 界面**：响应式前端，可直接使用

## 技术栈

- **后端**：FastAPI
- **图编排**：LangGraph（StateGraph、条件边）
- **Agent/工具**：LangChain（ReAct、Tools）
- **LLM**：OpenAI GPT-4
- **工具**：Tavily Search、DuckDuckGo
- **外部工具接入**：ToolRegistry + MCP Bridge（HTTP Gateway，可选）
- **前端**：原生 HTML/CSS/JavaScript（响应式）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

（内含 `langgraph`，用于图编排；若本地未装过，需执行上述命令。）

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

主要配置项：
- `OPENAI_API_KEY`: OpenAI API密钥（必需）
- `TAVILY_API_KEY`: Tavily搜索API密钥（可选，用于更好的搜索效果）
- `RAG_VECTOR_BACKEND`: RAG向量检索后端（`memory`/`milvus`，默认 `memory`）

### 3. 运行应用

```bash
python -m app.main
```

或使用uvicorn：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问界面

启动后访问：
- **前端界面**：http://localhost:8000/
- **API文档**：http://localhost:8000/docs
- **健康检查**：http://localhost:8000/health

### 5. 验证 LangGraph 编排（可选）

确认图构建与调用正常：

```bash
# 需已设置 OPENAI_API_KEY（.env 或环境变量）
python test_graph.py
```

## 使用说明

### Web界面使用

1. 打开浏览器访问 http://localhost:8000/
2. 选择内容板块（财经、AI、生活等）
3. 输入主题和可选要求
4. 选择内容长度和风格
5. 点击"开始创作"按钮
6. 等待AI生成内容（可能需要30秒-2分钟）
7. 查看生成的内容，可以点击"复制内容"按钮复制

### API使用

```bash
# 创建内容
curl -X POST "http://localhost:8000/api/v1/content/create" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "ai",
    "topic": "AI发展趋势",
    "length": "medium",
    "style": "professional"
  }'

# 获取板块列表
curl "http://localhost:8000/api/v1/content/categories"

# 获取Agent建议
curl -X POST "http://localhost:8000/api/v1/content/suggest-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "finance",
    "topic": "2024年投资策略"
  }'
```

## 工具架构（面试可讲）

- 默认采用 **内置工具 + 自定义函数**，保证稳定和低成本。
- 通过 `ToolRegistry` 做统一注册，Agent 不感知底层实现细节。
- `BaseTool.to_langchain_tool()` 支持 **字符串与 JSON 双输入**，便于结构化参数传递。
- 需要接入外部生态时，启用 `MCP_ENABLED=true` 并通过 `MCP_TOOLS_JSON` 动态挂载 MCP 桥接工具（`app/tools/mcp_bridge.py`）。
- 建议生产上让 MCP 走独立网关（鉴权、限流、审计），避免业务服务直接暴露 MCP 调用权限。

## 项目结构

```
iccp-langchain/
├── app/
│   ├── main.py              # FastAPI 入口（含静态文件）
│   ├── config.py            # 配置管理
│   ├── agents/              # Agent 与图编排
│   │   ├── graph.py         # LangGraph 编排（route → react|reflection|plan_solve）
│   │   ├── router.py        # 路由逻辑与 get_suggestion（被 graph 复用）
│   │   ├── react_agent.py   # ReAct Agent
│   │   ├── reflection_agent.py  # Reflection Agent
│   │   └── plan_solve_agent.py  # Plan-and-Solve Agent
│   ├── tools/               # 工具系统
│   │   ├── web_search.py    # 网络搜索工具
│   │   ├── fact_check.py    # 事实核查工具
│   │   └── registry.py      # 工具注册表
│   ├── categories/          # 板块系统
│   │   ├── config.py        # 板块配置
│   │   ├── loader.py        # Prompt加载器
│   │   └── prompts/         # Prompt模板
│   ├── llm/                 # LLM客户端
│   └── api/                 # API路由
│       └── v1/
│           └── content.py   # 内容创作API
├── static/                  # 前端静态文件
│   └── index.html           # 前端界面
├── requirements.txt
├── .env.example
└── README.md
```

## 前端界面功能

- ✅ 美观的响应式设计
- ✅ 板块选择下拉框
- ✅ 主题和需求输入
- ✅ 内容长度和风格选择
- ✅ 实时加载状态显示
- ✅ 生成结果展示（包含Agent信息、工具使用、迭代次数）
- ✅ 一键复制功能
- ✅ 错误提示

## LangGraph 流程与路由策略

请求进入后由 **LangGraph** 执行：`START → route → [react | reflection | plan_solve] → quality_gate → [finalize | reflection_refine] → END`。  

原 LangChain 与重构后 LangGraph 的**区别与框架流程**说明见：[docs/LangChain与LangGraph架构说明.md](docs/LangChain与LangGraph架构说明.md)。

1. **需要实时数据** → ReAct Agent  
   - 工具搜索、事实核查  
   - 适合财经、科技等需最新数据的板块  

2. **需要高质量内容** → Reflection Agent  
   - 生成-反思-改进循环  
   - 适合专业风格、深度内容  

3. **需要结构化规划** → Plan-and-Solve Agent  
   - 制定计划、分步执行、整合  
   - 适合长文、复杂主题  

4. **默认** → ReAct Agent  
   - 最通用方案  

5. **质量门控**  
   - 首轮执行后检查内容可用性与实时任务工具使用情况  
   - 不通过时自动进入 Reflection 修订并输出执行轨迹  

## 开发计划

- [ ] 数据库集成（PostgreSQL）
- [ ] Redis缓存
- [ ] RAG系统（Milvus）
- [ ] 用户认证和授权
- [ ] 异步任务处理（Celery）
- [ ] 任务历史记录
- [ ] 流式输出（实时显示生成过程）

## 常见问题

### Q: 为什么生成内容很慢？
A: 内容生成需要调用LLM API，可能需要30秒-2分钟。如果使用了工具（如搜索），时间会更长。

### Q: 如何提高生成速度？
A: 
1. 使用更快的模型（如gpt-3.5-turbo）
2. 减少内容长度
3. 不使用需要实时数据的板块

### Q: 前端界面无法访问？
A: 确保：
1. 后端服务已启动（`python -m app.main`）
2. 访问 http://localhost:8000/（不是8000/docs）
3. 检查浏览器控制台是否有错误

### Q: API调用失败？
A: 检查：
1. OPENAI_API_KEY是否正确设置
2. 网络连接是否正常
3. API配额是否充足

## 许可证

MIT License
