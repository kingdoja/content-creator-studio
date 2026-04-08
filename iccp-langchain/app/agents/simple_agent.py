"""
Simple Agent实现
用于简单问答和日常聊天场景：快速、简洁地给出回答，不走复杂工具链。

Refactored to accept domain objects (ContentTask + ExecutionContext).
Memory recall is no longer performed here; it is handled upstream by ContextBuilder.
Requirements: 1.3, 3.1
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.domain.interfaces import BaseAgent, ExecutionContext
from app.domain.models import ContentResult, ContentTask
from app.llm.client import get_llm_client


class SimpleAgent(BaseAgent):
    """Simple Agent - 面向简单问答和日常聊天的轻量执行器"""

    name = "simple"
    description = "Simple Agent：用于简单问答和日常聊天，快速给出简洁准确的回答。"

    CASUAL_INDICATORS = {
        "嗨", "你好", "hi", "hello", "hey", "谢谢", "thanks", "再见", "bye",
        "哈哈", "ok", "好的", "嗯", "对", "是的", "哦", "嘛", "呀",
    }
    TIME_QUERY_INDICATORS = {
        "今天几号", "今天几月几号", "今天星期几", "今天周几", "今天礼拜几",
        "现在几点", "现在时间", "当前时间", "几号", "星期几", "周几", "礼拜几",
        "what time", "current time", "today date", "today is",
    }

    def __init__(self) -> None:
        self.llm_client = get_llm_client()

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    async def execute(
        self,
        task: ContentTask,
        context: ExecutionContext,
    ) -> ContentResult:
        """Execute using domain objects (new interface)."""
        try:
            model_override = self._resolve_model_override(context)
            prefs = context.user_context.preferences if context and context.user_context else {}
            is_chat = bool(prefs.get("_is_chat", False))
            topic = task.topic
            requirements = task.requirements or ""
            category = task.category

            if self._is_time_query(topic):
                return ContentResult(
                    success=True,
                    content=self._build_time_reply(),
                    agent=self.name,
                    tools_used=(),
                    iterations=1,
                    metadata={"mode": "simple_time"},
                )

            if self._is_casual_chat(topic):
                prompt = self._build_chat_prompt(topic, category, requirements, is_chat)
            else:
                prompt = self._build_qa_prompt(topic, category, requirements, is_chat)

            content = await self.llm_client.achat(
                [{"role": "user", "content": prompt}],
                temperature=0.7 if is_chat else 0.6,
                model=model_override,
            )

            return ContentResult(
                success=True,
                content=content,
                agent=self.name,
                tools_used=(),
                iterations=1,
                metadata={"mode": "simple_chat" if self._is_casual_chat(topic) else "simple_qa"},
            )
        except Exception as exc:
            return ContentResult(
                success=False,
                content="",
                agent=self.name,
                tools_used=(),
                iterations=1,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Legacy dict-based interface (kept for backward compatibility)
    # ------------------------------------------------------------------

    async def execute_dict(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Legacy interface that accepts raw dicts. Delegates to execute()."""
        from app.domain.models import UserContext

        ctx = context or {}
        is_chat = task.get("module") == "chat"
        # Carry is_chat flag via preferences so execute() can read it
        prefs = dict(ctx.get("user_preferences") or {})
        prefs["_is_chat"] = is_chat
        if ctx.get("llm_model_override"):
            prefs["llm_model_override"] = ctx["llm_model_override"]

        content_task = ContentTask(
            category=task.get("category", "lifestyle"),
            topic=task.get("topic", ""),
            requirements=task.get("requirements") or "",
            length=task.get("length", "medium"),
            style=task.get("style", "professional"),
            force_simple=task.get("force_simple", False),
        )
        user_ctx = UserContext(
            user_id=ctx.get("user_id", "anonymous"),
            session_id=ctx.get("session_id"),
            recalled_memories=tuple(ctx.get("recalled_memories") or []),
            preferences=prefs,
        )
        exec_ctx = ExecutionContext(
            user_context=user_ctx,
            session_id=ctx.get("session_id"),
        )

        result = await self.execute(content_task, exec_ctx)
        return {
            "success": result.success,
            "content": result.content,
            "agent": result.agent,
            "tools_used": list(result.tools_used),
            "iterations": result.iterations,
            "error": result.error,
            "metadata": result.metadata,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_model_override(context: ExecutionContext) -> str | None:
        """Extract optional LLM model override from execution context."""
        if context is None:
            return None
        # ExecutionContext may carry extra metadata via user_context.preferences
        prefs = context.user_context.preferences if context.user_context else {}
        override = (prefs.get("llm_model_override") or "").strip()
        return override or None

    def _is_casual_chat(self, topic: str) -> bool:
        t = topic.strip().lower()
        if len(t) <= 15:
            return True
        return any(k in t for k in self.CASUAL_INDICATORS)

    def _is_time_query(self, topic: str) -> bool:
        t = topic.strip().lower()
        return any(k in t for k in self.TIME_QUERY_INDICATORS)

    @staticmethod
    def _build_time_reply() -> str:
        now = datetime.now()
        weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_map[now.weekday()]
        return (
            f"现在是{now.year}年{now.month}月{now.day}日，"
            f"星期{weekday}，{now.strftime('%H:%M')}。"
        )

    def _build_chat_prompt(
        self, topic: str, category: str, requirements: str = "", is_chat: bool = False
    ) -> str:
        ctx = f"\n\n同会话上下文（如有）：\n{requirements}" if requirements.strip() else ""
        if is_chat:
            return (
                f"你是一个温暖、有亲和力的AI助手。用户在跟你闲聊，请像关心朋友一样回复。\n\n"
                f"要求：\n"
                f"- 回复简短自然，1-3句话，像面对面聊天\n"
                f"- 语气温柔亲切，口语化表达\n"
                f"- 适当表达共情和关心\n"
                f"- 不要用Markdown格式、标题、列表\n"
                f"- 如果用户只是打招呼，就温暖地回应\n\n"
                f"用户说：{topic}{ctx}"
            )
        return (
            f"你是一个友好的AI助手。用户在跟你闲聊，请像朋友一样自然地回复。\n\n"
            f"要求：\n"
            f"- 回复简短自然，1-3句话\n"
            f"- 语气轻松友好\n"
            f"- 不要用Markdown格式\n\n"
            f"用户说：{topic}{ctx}"
        )

    def _build_qa_prompt(
        self, topic: str, category: str, requirements: str, is_chat: bool = False
    ) -> str:
        req_line = (
            f"\n补充信息：{requirements}"
            if requirements.strip() and requirements.strip() != "无"
            else ""
        )
        if is_chat:
            return (
                f"你是一个温和但靠谱的问答助手，用聊天的口吻回答，但内容必须有用。\n\n"
                f"问题：{topic}{req_line}\n\n"
                f"回答要求：\n"
                f"1) 直接回答问题，给出具体有用的内容；\n"
                f"2) 用通俗易懂的话解释，可以举例子；\n"
                f"3) 语气温和自然，但不要为了温和而回避问题；\n"
                f"4) 不要反问用户、不要说「你想怎样」，直接给答案；\n"
                f"5) 需要条理时可以用简单序号；\n"
                f"6) 不确定就直说。"
            )
        return (
            f"你是一个直接高效的问答助手，说话不绕弯子。\n\n"
            f"问题：{topic}{req_line}\n\n"
            f"输出要求：\n"
            f"1) 第一句话直接回答问题，不要铺垫；\n"
            f"2) 给出关键要点，每个要点要有具体信息；\n"
            f"3) 如果问题可操作，给简单步骤（最多3步）；\n"
            f"4) 整体控制在200字以内，不要写长文；\n"
            f"5) 不确定时明确说明。"
        )
