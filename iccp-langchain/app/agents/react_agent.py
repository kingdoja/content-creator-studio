"""
ReAct Agent实现（使用LangChain）

Refactored to:
- Accept ContentTask + ExecutionContext domain objects (new interface).
- Register KnowledgeSearchTool alongside existing tools.
- Read recalled memories from ExecutionContext instead of performing its own recall.
Requirements: 1.1, 1.3, 3.1
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.domain.interfaces import BaseAgent, ExecutionContext
from app.domain.models import ContentResult, ContentTask
from app.llm.client import get_llm_client
from app.prompting import prompt_optimizer
from app.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)


class ReActAgent(BaseAgent):
    """ReAct Agent - 使用LangChain实现，集成 KnowledgeSearchTool"""

    name = "react"
    description = (
        "ReAct Agent：通过思考-行动-观察循环完成任务，"
        "适合需要实时信息检索和工具调用的任务。"
    )

    def __init__(self) -> None:
        self.llm_client = get_llm_client()
        self.tool_registry = get_tool_registry()

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
            task_dict = self._task_to_dict(task)
            prefs = context.user_context.preferences if context and context.user_context else {}
            is_chat = bool(prefs.get("_is_chat", False))
            prompt_mode = "chat_react" if is_chat else "react"
            prompt_package = prompt_optimizer.build_package(task_dict, mode=prompt_mode)
            system_prompt = prompt_package.system_prompt
            user_prompt = self._build_user_prompt(task_dict, prompt_package.user_prompt, is_chat=is_chat)

            # Build tool list: registry tools + KnowledgeSearchTool
            tools = self._build_tools()

            max_iterations = int(prefs.get("_max_iterations", 3))
            agent_executor = await self._create_agent_executor(
                system_prompt,
                tools,
                llm_model_override=model_override,
                max_iterations=max_iterations,
            )

            result = await agent_executor.ainvoke({"input": user_prompt})
            content = result.get("output", "")

            tools_used: list[str] = []
            for step in result.get("intermediate_steps", []):
                if step:
                    tool_name = step[0].tool if hasattr(step[0], "tool") else str(step[0])
                    tools_used.append(tool_name)

            if "Agent stopped due to iteration limit or time limit" in content:
                content = await self._finalize_from_intermediate_steps(
                    task=task_dict,
                    intermediate_steps=result.get("intermediate_steps", []),
                    fallback_text=content,
                    llm_model_override=model_override,
                )

            return ContentResult(
                success=True,
                content=content,
                agent=self.name,
                tools_used=tuple(set(tools_used)),
                iterations=len(result.get("intermediate_steps", [])),
                metadata={"steps": result.get("intermediate_steps", [])},
            )

        except Exception as exc:
            logger.error(f"ReActAgent执行失败: {exc}")
            return ContentResult(
                success=False,
                content="",
                agent=self.name,
                tools_used=(),
                iterations=0,
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
        """Legacy interface that accepts raw dicts."""
        from app.domain.models import UserContext

        ctx = context or {}
        prefs = dict(ctx.get("user_preferences") or {})
        if ctx.get("llm_model_override"):
            prefs["llm_model_override"] = ctx["llm_model_override"]
        prefs["_is_chat"] = task.get("module") == "chat"
        prefs["_max_iterations"] = ctx.get("max_iterations", 3)

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

    def _build_tools(self) -> List:
        """Return registry tools plus KnowledgeSearchTool."""
        from app.tools.knowledge_search import KnowledgeSearchTool

        tools = list(self.tool_registry.get_langchain_tools())
        # Add KnowledgeSearchTool if not already registered
        registered_names = {t.name for t in tools}
        ks_tool = KnowledgeSearchTool()
        if ks_tool.name not in registered_names:
            tools.append(ks_tool.to_langchain_tool())
        return tools

    @staticmethod
    def _resolve_model_override(context: ExecutionContext) -> str | None:
        if context is None:
            return None
        # Check for model override stored in preferences or via legacy attribute
        prefs = context.user_context.preferences if context.user_context else {}
        override = (prefs.get("llm_model_override") or "").strip()
        return override or None

    @staticmethod
    def _task_to_dict(task: ContentTask) -> Dict[str, Any]:
        return {
            "category": task.category,
            "topic": task.topic,
            "requirements": task.requirements,
            "length": task.length,
            "style": task.style,
        }

    async def _create_agent_executor(
        self,
        system_prompt: str,
        tools: List,
        llm_model_override: str | None = None,
        max_iterations: int = 3,
    ) -> AgentExecutor:
        react_prompt = PromptTemplate.from_template("""
{system_prompt}

你有以下工具可以使用：
{tools}

使用以下格式：
Question: 输入的问题
Thought: 你应该思考要做什么
Action: 要采取的行动，应该是[{tool_names}]中的一个
Action Input: 行动的输入
Observation: 行动的结果
... (这个思考/行动/行动输入/观察可以重复N次)
Thought: 我现在知道最终答案了
Final Answer: 原始问题的最终答案

重要约束：
1) 在 Final Answer 之前，必须严格输出 Thought/Action/Action Input/Observation 字段，不能省略 Action。
2) 不要在 Thought/Action 行使用 Markdown 标题或列表包裹字段名；字段名必须原样输出。
3) 禁止对同一工具+同一输入重复调用超过一次；若新信息不足，请直接输出 Final Answer。
4) 拿到工具返回的 Observation 后，若已足够回答问题，应在本轮直接输出 Thought + Final Answer，不要无意义地再开新轮。

Question: {input}
Thought: {agent_scratchpad}
""")

        llm = ChatOpenAI(
            model=llm_model_override or self.llm_client.model,
            temperature=0.7,
            api_key=self.llm_client.api_key,
            base_url=(
                self.llm_client.base_url
                if self.llm_client.base_url != "https://api.openai.com/v1"
                else None
            ),
        )

        agent = create_react_agent(
            llm=llm,
            tools=tools,
            prompt=react_prompt.partial(system_prompt=system_prompt),
        )

        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            max_iterations=max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )

    def _build_user_prompt(
        self, task: Dict[str, Any], prompt_base: str, *, is_chat: bool = False
    ) -> str:
        requirements = task.get("requirements", "")
        now = datetime.now()
        topic = (task.get("topic") or "").lower()
        freshness_needed = any(
            kw in topic
            for kw in ["最新", "最近", "今日", "今天", "本周", "本月", "今年", "current", "latest", "today", "recent"]
        )

        if is_chat:
            final_hint = (
                "请按 ReAct 流程查找信息，最后在 Final Answer 里用温和自然的聊天口吻回答用户，"
                "不要写文章体，不要用 Markdown 标题。"
            )
        else:
            final_hint = "请按 ReAct 流程完成：需要信息就使用工具，最后在 Final Answer 输出最终成稿。"

        prompt = (
            f"{prompt_base}\n\n"
            f"当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}。\n"
            f"{final_hint}"
        )

        if requirements:
            prompt += "\n如果额外要求与基础要求冲突，以真实性和可验证性优先。"
        if freshness_needed:
            prompt += (
                "\n该任务有明显时效性：请优先检索近30天内信息，"
                "在检索词中加入年份/月等时间限定；若只能拿到旧信息，必须明确标注信息日期与时效风险。"
            )
        return prompt

    async def _finalize_from_intermediate_steps(
        self,
        task: Dict[str, Any],
        intermediate_steps: List[Any],
        fallback_text: str,
        llm_model_override: str | None = None,
    ) -> str:
        observations: list[str] = []
        for i, step in enumerate(intermediate_steps):
            if not step or len(step) < 2:
                continue
            action = step[0]
            observation = step[1]
            tool_name = getattr(action, "tool", "unknown_tool")
            tool_input = getattr(action, "tool_input", "")
            observation_text = str(observation)
            if len(observation_text) > 1200:
                observation_text = observation_text[:1200] + " ...(截断)"
            observations.append(
                f"[步骤{i + 1}] 工具={tool_name} 输入={tool_input}\n观察={observation_text}"
            )

        is_chat = task.get("module") == "chat"
        style_hint = (
            "用温和自然的聊天口吻回答，不要用 Markdown 标题，不要写文章体。"
            if is_chat
            else "请直接输出最终成稿，不要再输出 Thought/Action。"
        )

        prompt = (
            f"你需要基于已有工具结果回答用户。\n"
            f"主题：{task.get('topic', '')}\n"
            f"板块：{task.get('category', '')}\n"
            f"长度：{task.get('length', 'medium')}\n"
            f"风格：{task.get('style', 'professional')}\n"
            f"额外要求：{task.get('requirements') or '无'}\n\n"
            f"已有观察结果：\n"
            + ("\n\n".join(observations) if observations else fallback_text)
            + f"\n\n{style_hint}"
        )
        return await self.llm_client.achat(
            [{"role": "user", "content": prompt}],
            temperature=0.6,
            model=llm_model_override,
        )
