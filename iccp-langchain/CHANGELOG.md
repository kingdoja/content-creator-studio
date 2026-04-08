# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2024-12-08

### 🎉 架构重构完成

这是一个重大版本更新，完成了从过程式架构到领域驱动设计（DDD）的全面重构。

### ✨ 新增特性

#### 核心架构
- **DDD 分层架构**：引入领域层、应用层、基础设施层和接口层
- **3 个核心 Agent**：SimpleAgent（快速问答）、ReActAgent（工具调用）、ReflectionAgent（深度反思）
- **策略模式路由**：配置驱动的路由规则，支持热重载
- **统一记忆系统**：ContextBuilder 统一管理记忆召回，超时自动降级
- **RAG 工具化**：KnowledgeSearchTool 替代独立的 RAGAgent

#### 领域模型
- `ContentTask` - 内容创作任务
- `ContentResult` - 内容创作结果
- `UserContext` - 用户上下文
- `TaskAnalysis` - 任务分析
- `BaseAgent` - Agent 接口
- `RoutingStrategy` - 路由策略接口

#### 应用服务
- `ContentService` - 内容创作服务
- `VideoAppService` - 视频生成服务
- `MemoryAppService` - 记忆管理服务
- `ContextBuilder` - 上下文构建器

#### 配置系统
- 配置驱动的路由规则（`routing_config.yaml`）
- 特性开关支持（`USE_NEW_ARCHITECTURE`）
- 统一的配置管理（`app/config/settings.py`）

#### 渐进式迁移
- `LegacyAgentAdapter` - 旧接口适配器
- 新旧架构共存支持
- 完整的迁移文档

### 🔄 变更

#### Agent 架构
- ❌ 移除 `PlanSolveAgent`（功能合并到 ReflectionAgent）
- ❌ 移除 `RAGAgent`（降级为 KnowledgeSearchTool）
- ✅ 新增 `SimpleAgent`（快速响应简单请求）
- ✅ 重构 `ReActAgent`（集成 KnowledgeSearchTool）
- ✅ 重构 `ReflectionAgent`（合并 PlanSolve 能力）

#### 路由系统
- ❌ 废弃 150+ 行的 if-else 路由逻辑
- ✅ 采用策略模式 + YAML 配置
- ✅ 支持优先级排序和动态启用/禁用

#### 记忆系统
- ❌ 移除 3 处独立的记忆召回逻辑
- ✅ 统一到 ContextBuilder
- ✅ 超时降级机制（6秒）

#### 状态管理
- ❌ 精简状态字段从 20+ 个到 8 个
- ✅ 使用不可变数据结构
- ✅ 清晰的状态流转

### 📁 项目结构优化

#### 代码组织
- 创建 `app/agents/_legacy/` 隔离旧代码
- 创建 `tests/unit/`、`tests/integration/`、`tests/legacy/` 分类测试
- 移动脚本到 `scripts/` 目录
- 添加废弃警告到旧代码

#### 文档更新
- ✅ 更新 README.md 反映新架构
- ✅ 新增《架构重构总结》
- ✅ 新增《新架构说明-重构后》
- ✅ 新增《项目结构优化建议》
- ✅ 新增《项目结构优化-执行记录》
- ✅ 更新《渐进式迁移指南》

### 🐛 修复

- 修复记忆召回重复调用问题
- 修复路由逻辑复杂度过高问题
- 修复状态管理混乱问题
- 修复 API 层业务逻辑混入问题

### 📊 性能优化

- **记忆召回**：避免重复召回，统一入口
- **路由决策**：O(n) → O(1) 复杂度
- **状态管理**：减少字段数量，避免深拷贝

### 🧪 测试

- 测试覆盖率：83%+
- 新增 14 个重构相关测试
- 所有核心功能测试通过

### 📈 指标改善

| 指标 | 重构前 | 重构后 | 改善 |
|------|--------|--------|------|
| Agent 数量 | 5 | 3 | ↓ 40% |
| 路由逻辑行数 | 150+ | 50 | ↓ 67% |
| 状态字段数 | 20+ | 8 | ↓ 60% |
| 记忆召回点 | 3 | 1 | ↓ 67% |
| 代码行数 | - | - | ↓ 30% |
| 测试覆盖率 | 60% | 83% | ↑ 23% |

### ⚠️ 破坏性变更

#### 导入路径变更
```python
# 旧代码（仍可用，但会有废弃警告）
from app.agents.router import AgentRouter
from app.agents.rag_agent import RAGAgent

# 新代码
from app.agents.router_v2 import AgentRouter
from app.tools.knowledge_search import KnowledgeSearchTool
```

#### 配置变更
```python
# 旧配置
from app.config import settings

# 新配置（推荐）
from app.config.settings import settings
```

### 🔧 迁移指南

#### 启用新架构
```bash
# .env
USE_NEW_ARCHITECTURE=true
```

#### 使用适配器（过渡期）
```python
from app.adapters.legacy_adapter import LegacyAgentAdapter

adapter = LegacyAgentAdapter(new_agent)
result = adapter.execute(task_dict, context_dict)
```

详细迁移指南请参考：[docs/渐进式迁移指南.md](docs/渐进式迁移指南.md)

### 📚 文档

- [架构重构总结](docs/架构重构总结.md)
- [新架构说明](docs/新架构说明-重构后.md)
- [项目结构优化建议](docs/项目结构优化建议.md)
- [渐进式迁移指南](docs/渐进式迁移指南.md)
- [配置驱动路由规则](docs/配置驱动路由规则-实施总结.md)

### 🙏 致谢

感谢所有参与架构重构的团队成员！

---

## [1.0.0] - 2024-11-01

### 初始版本

- 基础的多 Agent 内容创作平台
- LangGraph 编排
- 5 个 Agent（simple/react/reflection/plan_solve/rag）
- 基础的路由逻辑
- 记忆系统
- RAG 系统

---

**版本说明**：
- 主版本号（Major）：破坏性变更
- 次版本号（Minor）：新功能，向后兼容
- 修订号（Patch）：Bug 修复

**当前版本**：2.0.0（架构重构完成）
