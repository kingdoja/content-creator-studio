"""
Agent 路由器：持有三个 Agent 实例，提供 get_suggestion；执行入口统一走 LangGraph。

支持渐进式迁移：通过 USE_NEW_ARCHITECTURE 特性开关控制新旧代码路径。
Requirements: 10.1, 10.2
"""
from typing import Dict, Any

from app.agents.react_agent import ReActAgent
from app.agents.reflection_agent import ReflectionAgent
from .plan_solve_agent import PlanSolveAgent
from .rag_agent import RAGAgent
from app.agents.simple_agent import SimpleAgent
from . import routing
import logging

logger = logging.getLogger(__name__)


class AgentRouter:
    """
    持有 ReAct / Reflection / PlanSolve 三个 Agent，路由逻辑委托给 routing 模块。
    
    支持渐进式迁移：
    - 当 USE_NEW_ARCHITECTURE=False 时，使用旧的 routing.py 逻辑
    - 当 USE_NEW_ARCHITECTURE=True 时，使用新的 router_v2.py + 策略模式
    """

    def __init__(self):
        self.react_agent = ReActAgent()
        self.reflection_agent = ReflectionAgent()
        self.plan_solve_agent = PlanSolveAgent()
        self.rag_agent = RAGAgent()
        self.simple_agent = SimpleAgent()
        self._agents = {
            routing.AGENT_REACT: self.react_agent,
            routing.AGENT_REFLECTION: self.reflection_agent,
            routing.AGENT_PLAN_SOLVE: self.plan_solve_agent,
            routing.AGENT_RAG: self.rag_agent,
            routing.AGENT_SIMPLE: self.simple_agent,
        }
        
        # Initialize new router for gradual migration
        self._router_v2 = None
        self._use_new_architecture = False
        try:
            from app.config import USE_NEW_ARCHITECTURE
            self._use_new_architecture = USE_NEW_ARCHITECTURE
            if self._use_new_architecture:
                from app.agents.router_v2 import get_router_v2
                self._router_v2 = get_router_v2()
                logger.info("AgentRouter initialized with NEW architecture (router_v2)")
            else:
                logger.info("AgentRouter initialized with LEGACY architecture (routing.py)")
        except Exception as exc:
            logger.warning("Failed to initialize new architecture, falling back to legacy: %s", exc)

    async def route(self, task: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """通过 LangGraph 执行任务（单一执行路径），返回与 create_content API 一致的结构"""
        from app.agents.graph import get_content_creation_graph
        graph = get_content_creation_graph()
        initial_state: Dict[str, Any] = {"task": task}
        if context:
            initial_state.update(context)
        final_state = await graph.ainvoke(initial_state)
        return _state_to_result(final_state)

    def get_suggestion(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取 Agent 选择建议（与 LangGraph 路由逻辑一致）。
        
        支持新旧架构：
        - 旧架构：使用 routing.analyze_task + routing.select_agent_name
        - 新架构：使用 router_v2.route_from_task
        """
        if self._use_new_architecture and self._router_v2:
            # New architecture path
            try:
                agent_name, analysis = self._router_v2.route_from_task(task)
                analysis_dict = {
                    "complexity": analysis.complexity,
                    "task_type": analysis.task_type,
                    "requires_knowledge": analysis.requires_knowledge,
                    "requires_real_time_data": analysis.requires_real_time_data,
                    "requires_reflection": analysis.requires_reflection,
                    "estimated_iterations": analysis.estimated_iterations,
                }
                reason = _suggestion_reason_v2(analysis, agent_name)
                return {
                    "recommended": agent_name,
                    "analysis": analysis_dict,
                    "reason": reason,
                }
            except Exception as exc:
                logger.error("New architecture routing failed, falling back to legacy: %s", exc)
                # Fall through to legacy path
        
        # Legacy architecture path
        analysis = routing.analyze_task(task)
        agent_name = routing.select_agent_name(analysis)
        agent = self._agents[agent_name]
        reason = _suggestion_reason(analysis, agent_name)
        return {
            "recommended": agent.name,
            "analysis": analysis,
            "reason": reason,
        }


# 全局单例（避免每次请求都重建 Agent）
_agent_router: AgentRouter | None = None


def get_agent_router() -> AgentRouter:
    """获取 AgentRouter 单例。"""
    global _agent_router
    if _agent_router is None:
        _agent_router = AgentRouter()
    return _agent_router


def _state_to_result(state: Dict[str, Any]) -> Dict[str, Any]:
    """将图最终状态转为 route() 的返回格式，兼容新旧状态结构。"""
    result = state.get("result")
    if result is not None and hasattr(result, "success"):
        # New domain-object state
        analysis = state.get("analysis")
        analysis_dict = None
        if analysis is not None and hasattr(analysis, "task_type"):
            analysis_dict = {
                "complexity": analysis.complexity,
                "task_type": analysis.task_type,
                "requires_knowledge": analysis.requires_knowledge,
                "requires_real_time_data": analysis.requires_real_time_data,
                "requires_reflection": analysis.requires_reflection,
                "estimated_iterations": analysis.estimated_iterations,
            }
        return {
            "success": result.success,
            "content": result.content,
            "agent": result.agent,
            "tools_used": list(result.tools_used),
            "iterations": result.iterations,
            "agent_selected": result.agent,
            "task_analysis": analysis_dict,
            "quality_gate_passed": state.get("quality_passed"),
            "quality_gate_reason": None,
            "execution_trace": state.get("execution_trace", []),
            "error": result.error,
            "metadata": result.metadata,
        }
    # Legacy flat-field state
    return {
        "success": state.get("success", False),
        "content": state.get("content", ""),
        "agent": state.get("agent", ""),
        "tools_used": state.get("tools_used", []),
        "iterations": state.get("iterations", 0),
        "agent_selected": state.get("agent_selected"),
        "task_analysis": state.get("task_analysis"),
        "quality_gate_passed": state.get("quality_gate_passed"),
        "quality_gate_reason": state.get("quality_gate_reason"),
        "execution_trace": state.get("execution_trace", []),
        "error": state.get("error"),
        "metadata": state.get("metadata"),
    }


def _suggestion_reason(analysis: Dict[str, Any], agent_name: str) -> str:
    """根据分析与所选 Agent 生成建议原因（旧架构）"""
    if analysis.get("requires_simple_qa"):
        return "识别为简单问答，选择 Simple Agent 进行快速简洁回答"
    if analysis.get("requires_real_time_data"):
        return "需要实时数据，选择 ReAct Agent 进行信息检索"
    if analysis.get("requires_knowledge"):
        return "任务包含私有资料约束，选择 RAG Agent 基于知识库检索后生成"
    if analysis.get("requires_reflection") and analysis.get("complexity") == "high":
        return "需要高质量内容创作，选择 Reflection Agent 进行深度优化"
    if analysis.get("requires_planning") and analysis.get("complexity") == "high":
        return "需要结构化规划，选择 Plan and Solve Agent"
    return "使用 ReAct Agent 作为通用方案"


def _suggestion_reason_v2(analysis: Any, agent_name: str) -> str:
    """根据分析与所选 Agent 生成建议原因（新架构）"""
    # analysis is TaskAnalysis domain object
    if agent_name == "simple":
        return "识别为简单问答或闲聊，选择 Simple Agent 进行快速简洁回答"
    if agent_name == "reflection":
        return f"高复杂度任务（{analysis.task_type}），选择 Reflection Agent 进行深度优化"
    if analysis.requires_real_time_data:
        return "需要实时数据，选择 ReAct Agent 进行信息检索"
    if analysis.requires_knowledge:
        return "任务需要知识库支持，选择 ReAct Agent（集成 KnowledgeSearchTool）"
    return "使用 ReAct Agent 作为通用方案"
