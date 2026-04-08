"""
TaskAnalyzer：将原始任务字典分析为 TaskAnalysis 领域对象。
重构自 routing.py 的 analyze_task，返回类型安全的领域对象。
Requirements: 1.1, 1.4
"""
from __future__ import annotations

from typing import Any

from app.categories.config import get_category
from app.domain.models import TaskAnalysis


def analyze_task(
    task: dict[str, Any],
    memory_signals: dict[str, Any] | None = None,
) -> TaskAnalysis:
    """
    分析任务特征，返回 TaskAnalysis 领域对象。

    Args:
        task: 原始任务字典，包含 category、topic、requirements、length、style、force_simple 等字段。
        memory_signals: 可选的记忆信号，包含 recalled_count、has_preferences 等字段。

    Returns:
        TaskAnalysis 领域对象，供路由策略使用。
    """
    category_id = task.get("category", "lifestyle")
    try:
        category = get_category(category_id)
    except ValueError:
        category = {"requires_real_time_data": False, "typical_complexity": "medium"}

    topic = (task.get("topic") or "").lower()
    requirements = (task.get("requirements") or "").lower()
    length = task.get("length", "medium")
    style = (task.get("style") or "").lower()
    force_simple = bool(task.get("force_simple", False))

    # --- 复杂度推断 ---
    complexity = category.get("typical_complexity", "medium")
    if length == "long":
        complexity = "high" if complexity != "low" else "medium"
    if requirements and len(requirements) > 50:
        complexity = "high" if complexity != "low" else "medium"

    # --- 实时数据需求 ---
    realtime_keywords = [
        "最新", "最近", "今日", "今天", "本周", "本月", "本季度", "今年", "刚刚",
        "实时", "新发布", "新版本", "近况", "动态", "current", "latest", "today", "recent",
    ]
    requires_real_time_data = category.get("requires_real_time_data", False) or any(
        k in topic for k in realtime_keywords
    )

    # --- 规划需求 ---
    requires_planning = (
        length == "long"
        or complexity == "high"
        or ("结构" in requirements or "规划" in requirements)
    )

    # --- 反思需求 ---
    requires_reflection = (
        style == "professional"
        or complexity == "high"
        or ("深度" in requirements or "质量" in requirements)
    )

    # --- 知识库需求 ---
    knowledge_keywords = ["知识库", "根据资料", "基于资料", "RAG", "文档", "内部资料", "手册", "规范"]
    requires_knowledge = any(k in f"{topic} {requirements}" for k in knowledge_keywords)

    # --- 简单问答识别 ---
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
    has_simple_qa_pattern = (
        any(k in topic for k in simple_qa_keywords) or "?" in topic or "？" in topic
    )
    has_casual_chat_pattern = any(k in topic for k in casual_chat_keywords) or topic_is_very_short

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

    if requires_simple_qa:
        requires_real_time_data = False

    # --- 记忆信号调整 ---
    memory_signals = memory_signals or {}
    recalled_count = int(memory_signals.get("recalled_count") or 0)
    has_preferences = bool(memory_signals.get("has_preferences"))
    memory_modules = set(memory_signals.get("memory_modules") or [])
    preference_keys = set(memory_signals.get("preference_keys") or [])

    if "knowledge" in memory_modules:
        requires_knowledge = True
    if recalled_count > 0:
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

    # --- task_type 推断 ---
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

    # --- 预估迭代次数 ---
    estimated_iterations = 3
    if complexity == "high":
        estimated_iterations = 5
    elif complexity == "low":
        estimated_iterations = 2
    if requires_real_time_data:
        estimated_iterations += 2

    return TaskAnalysis(
        complexity=complexity,
        task_type=task_type,
        requires_knowledge=requires_knowledge,
        requires_real_time_data=requires_real_time_data,
        requires_reflection=requires_reflection,
        estimated_iterations=estimated_iterations,
    )
