# Legacy Agents - DEPRECATED ⚠️

**警告：此目录包含已废弃的代码，仅用于向后兼容。**

## 废弃说明

| 文件 | 状态 | 替代方案 |
|------|------|----------|
| `plan_solve_agent.py` | ❌ 已废弃 | 功能已合并到 `reflection_agent.py` |
| `rag_agent.py` | ❌ 已废弃 | 已降级为 `tools/knowledge_search.py` |
| `router.py` | ❌ 已废弃 | 使用 `router_v2.py` |
| `routing.py` | ❌ 已废弃 | 使用 `analyzer.py` + `strategies.py` |

## 迁移指南

### 从旧架构迁移到新架构

1. **设置特性开关**
   ```bash
   # .env
   USE_NEW_ARCHITECTURE=true
   ```

2. **更新导入语句**
   ```python
   # 旧代码
   from app.agents.router import AgentRouter
   from app.agents.rag_agent import RAGAgent
   
   # 新代码
   from app.agents.router_v2 import AgentRouter
   from app.tools.knowledge_search import KnowledgeSearchTool
   ```

3. **使用适配器（过渡期）**
   ```python
   from app.adapters.legacy_adapter import LegacyAgentAdapter
   
   # 包装旧接口
   adapter = LegacyAgentAdapter(new_agent)
   result = adapter.execute(task_dict, context_dict)
   ```

## 删除计划

这些文件将在以下条件满足后删除：

- ✅ 新架构稳定运行 3 个月
- ✅ 所有用户迁移到新架构
- ✅ `USE_NEW_ARCHITECTURE=true` 成为默认配置

**预计删除时间**：2025年3月

## 详细文档

- [架构重构总结](../../../docs/架构重构总结.md)
- [渐进式迁移指南](../../../docs/渐进式迁移指南.md)
- [新架构说明](../../../docs/新架构说明-重构后.md)

## 支持

如有迁移问题，请参考文档或联系开发团队。
