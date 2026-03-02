"""
Agent 路由器：持有三个 Agent 实例，提供 get_suggestion；执行入口统一走 LangGraph。
"""
from typing import Dict, Any

from app.agents.react_agent import ReActAgent
from app.agents.reflection_agent import ReflectionAgent
from app.agents.plan_solve_agent import PlanSolveAgent
from app.agents.rag_agent import RAGAgent
from app.agents.simple_agent import SimpleAgent
from . import routing
import logging

logger = logging.getLogger(__name__)


class AgentRouter:
    """持有 ReAct / Reflection / PlanSolve 三个 Agent，路由逻辑委托给 routing 模块"""

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
        """获取 Agent 选择建议（与 LangGraph 路由逻辑一致）"""
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
    """将图最终状态转为 route() 的返回格式"""
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
    """根据分析与所选 Agent 生成建议原因"""
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
