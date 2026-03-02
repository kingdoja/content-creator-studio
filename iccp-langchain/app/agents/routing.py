"""
路由逻辑：任务分析与 Agent 选择
供 LangGraph 路由节点与 AgentRouter 共用，单一事实来源。
"""
from typing import Dict, Any

from app.categories.config import get_category

# 图条件边使用的节点名，与各 Agent 的 .name 一致
AGENT_REACT = "react"
AGENT_REFLECTION = "reflection"
AGENT_PLAN_SOLVE = "plan_solve"
AGENT_RAG = "rag"
AGENT_SIMPLE = "simple"


def analyze_task(task: Dict[str, Any], memory_signals: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """分析任务特征（复杂度、是否需要实时数据/规划/反思等）"""
    category_id = task.get("category", "lifestyle")
    category = get_category(category_id)

    topic = (task.get("topic") or "").lower()
    requirements = (task.get("requirements") or "").lower()
    length = task.get("length", "medium")
    style = (task.get("style") or "").lower()
    force_simple = bool(task.get("force_simple", False))

    complexity = category.get("typical_complexity", "medium")
    if length == "long":
        complexity = "high" if complexity != "low" else "medium"
    if requirements and len(requirements) > 50:
        complexity = "high" if complexity != "low" else "medium"

    requires_real_time_data = (
        category.get("requires_real_time_data", False)
        or any(
            k in topic
            for k in [
                "最新", "最近", "今日", "今天", "本周", "本月", "本季度", "今年", "刚刚",
                "实时", "新发布", "新版本", "近况", "动态", "current", "latest", "today", "recent",
            ]
        )
    )
    requires_planning = (
        length == "long"
        or complexity == "high"
        or ("结构" in requirements or "规划" in requirements)
    )
    requires_reflection = (
        task.get("style") == "professional"
        or complexity == "high"
        or ("深度" in requirements or "质量" in requirements)
    )
    requires_knowledge = any(
        keyword in f"{topic} {requirements}"
        for keyword in ["知识库", "根据资料", "基于资料", "RAG", "文档", "内部资料", "手册", "规范"]
    )

    # 简单问答 / 闲聊识别
    simple_qa_keywords = [
        "什么是", "是什么", "怎么", "如何", "区别", "对比", "含义", "概念", "示例", "例子",
        "why", "what is", "how to", "difference", "example",
    ]
    casual_chat_keywords = [
        "嗨", "你好", "hi", "hello", "hey", "谢谢", "thanks", "再见", "bye",
        "哈哈", "ok", "好的", "嗯", "对", "是的", "哦",
    ]
    action_keywords = [
        "帮我", "帮忙", "具体", "详细", "方案", "设计", "规划", "分析",
        "写一", "做一", "想一", "列一", "给我", "生成", "创建", "总结",
        "怎么做", "怎么实现", "如何实现", "步骤", "流程", "计划",
    ]
    topic_stripped = topic.strip()
    topic_is_short = len(topic_stripped) <= 60
    topic_is_very_short = len(topic_stripped) <= 15
    requirement_is_light = len(requirements.strip()) <= 20
    has_action_request = any(k in topic for k in action_keywords)
    has_simple_qa_pattern = any(k in topic for k in simple_qa_keywords) or ("?" in topic) or ("？" in topic)
    has_casual_chat_pattern = (
        any(k in topic for k in casual_chat_keywords)
        or topic_is_very_short
    )
    requires_simple_qa = (
        (has_simple_qa_pattern or has_casual_chat_pattern)
        and topic_is_short
        and requirement_is_light
        and length != "long"
        and not requires_knowledge
        and not has_action_request
    )
    if force_simple:
        requires_simple_qa = True

    # 简单问答优先“快速回答”，不强制实时搜索
    if requires_simple_qa:
        requires_real_time_data = False

    memory_signals = memory_signals or {}
    recalled_count = int(memory_signals.get("recalled_count") or 0)
    has_preferences = bool(memory_signals.get("has_preferences"))
    memory_modules = set(memory_signals.get("memory_modules") or [])
    preference_keys = set(memory_signals.get("preference_keys") or [])
    preferred_agent_by_type = memory_signals.get("preferred_agent_by_type") or {}
    has_memory_context = recalled_count > 0

    if "knowledge" in memory_modules:
        requires_knowledge = True
    if has_memory_context:
        # 仅因为命中记忆不再强制升级到 reflection，避免中等任务普遍变慢。
        if complexity == "low":
            complexity = "medium"
        if not requires_real_time_data and (complexity == "high" or style == "professional"):
            requires_reflection = True
    if has_preferences and complexity == "low":
        complexity = "medium"
    if (
        {"preferred_style", "default_style"} & preference_keys
        and style in {"professional", "casual", "humorous"}
    ):
        requires_reflection = True

    if requires_simple_qa:
        task_type = "simple_qa"
    elif requires_knowledge:
        task_type = "knowledge"
    elif requires_real_time_data:
        task_type = "realtime"
    elif requires_planning and complexity == "high":
        task_type = "planning"
    elif requires_reflection:
        task_type = "reflection"
    else:
        task_type = "general"
    preferred_agent = str(preferred_agent_by_type.get(task_type) or "").strip().lower()

    estimated_iterations = 3
    if complexity == "high":
        estimated_iterations = 5
    elif complexity == "low":
        estimated_iterations = 2
    if requires_real_time_data:
        estimated_iterations += 2

    reason_flags = []
    if requires_simple_qa:
        reason_flags.append("simple_qa_detected")
    if requires_knowledge:
        reason_flags.append("knowledge_required")
    if requires_real_time_data:
        reason_flags.append("realtime_required")
    if has_memory_context:
        reason_flags.append("memory_context_present")
    if has_preferences:
        reason_flags.append("user_preferences_present")
    if preferred_agent:
        reason_flags.append(f"preferred_agent:{task_type}:{preferred_agent}")
    if requires_planning:
        reason_flags.append("planning_required")
    if requires_reflection:
        reason_flags.append("reflection_required")

    return {
        "complexity": complexity,
        "requires_real_time_data": requires_real_time_data,
        "requires_planning": requires_planning,
        "requires_reflection": requires_reflection,
        "requires_knowledge": requires_knowledge,
        "requires_simple_qa": requires_simple_qa,
        "force_simple": force_simple,
        "has_memory_context": has_memory_context,
        "recalled_count": recalled_count,
        "memory_modules": sorted(memory_modules),
        "task_type": task_type,
        "preferred_agent": preferred_agent,
        "estimated_iterations": estimated_iterations,
        "route_reason_flags": reason_flags,
    }


def select_agent_name(analysis: Dict[str, Any]) -> str:
    """
    根据分析结果返回应执行的 Agent 名称（与图条件边键一致）。
    返回 "simple" | "react" | "reflection" | "plan_solve" | "rag"。
    """
    agent, _ = select_agent_with_reason(analysis)
    return agent


def select_agent_with_reason(analysis: Dict[str, Any]) -> tuple[str, str]:
    preferred_agent = (analysis.get("preferred_agent") or "").strip().lower()
    if preferred_agent in {AGENT_SIMPLE, AGENT_REACT, AGENT_REFLECTION, AGENT_PLAN_SOLVE, AGENT_RAG}:
        if analysis.get("complexity") != "high" or preferred_agent in {AGENT_REFLECTION, AGENT_PLAN_SOLVE}:
            return preferred_agent, "preferred_agent_bias"
    if analysis.get("requires_simple_qa"):
        return AGENT_SIMPLE, "simple_qa_detected"
    if analysis.get("requires_knowledge"):
        return AGENT_RAG, "knowledge_required"
    if analysis.get("has_memory_context") and analysis.get("complexity") == "high":
        return AGENT_REFLECTION, "memory_context_present"
    if analysis.get("requires_real_time_data"):
        return AGENT_REACT, "realtime_required"
    if analysis.get("requires_reflection") and analysis.get("complexity") == "high":
        return AGENT_REFLECTION, "reflection_required_high_complexity"
    if analysis.get("requires_planning") and analysis.get("complexity") == "high":
        return AGENT_PLAN_SOLVE, "planning_required_high_complexity"
    if analysis.get("requires_reflection") and analysis.get("complexity") == "medium":
        return AGENT_REFLECTION, "reflection_required_medium_complexity"
    if analysis.get("requires_planning"):
        return AGENT_PLAN_SOLVE, "planning_required"
    return AGENT_REACT, "default_react"
