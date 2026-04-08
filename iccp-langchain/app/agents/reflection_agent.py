"""
Reflection Agent实现
通过生成-反思-改进循环优化内容质量。

Refactored to:
- Accept ContentTask + ExecutionContext domain objects (new interface).
- Register KnowledgeSearchTool for knowledge-augmented generation.
- Merge PlanSolveAgent planning capability into a high-complexity branch.
- Read recalled memories from ExecutionContext instead of performing its own recall.
Requirements: 1.1, 1.3
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from app.domain.interfaces import BaseAgent, ExecutionContext
from app.domain.models import ContentResult, ContentTask
from app.llm.client import get_llm_client
from app.prompting import prompt_optimizer

logger = logging.getLogger(__name__)


class ReflectionAgent(BaseAgent):
    """Reflection Agent - 通过反思优化内容质量，高复杂度任务支持规划分步执行"""

    name = "reflection"
    description = (
        "Reflection Agent：通过生成初稿、反思评估、改进优化的循环来创作高质量内容。"
        "高复杂度任务额外支持规划-分步执行模式（原 PlanSolveAgent 能力）。"
    )

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
            task_dict = self._task_to_dict(task)
            prefs = context.user_context.preferences if context and context.user_context else {}
            max_reflections = int(prefs.get("_max_reflections", 3))

            # High-complexity branch: plan -> execute steps -> reflect
            if prefs.get("_use_planning", False):
                return await self._execute_with_planning(task_dict, context, model_override)

            prompt_package = prompt_optimizer.build_package(task_dict, mode="draft")
            system_prompt = prompt_package.system_prompt

            # Allow graph to pass an existing draft for refinement
            draft = prefs.get("_draft_content") or None
            if not draft:
                draft = await self._generate_draft(
                    task_dict, system_prompt, prompt_package.user_prompt, model_override
                )

            current_content = draft
            reflections: list[str] = []

            for _ in range(max_reflections):
                reflection = await self._reflect(
                    current_content, task_dict, system_prompt, model_override
                )
                reflections.append(reflection)
                if not self._should_improve(reflection):
                    break
                current_content = await self._improve(
                    current_content, reflection, task_dict, system_prompt, model_override
                )

            # Optionally augment with knowledge search
            knowledge_context = await self._fetch_knowledge(task_dict)
            if knowledge_context:
                current_content = await self._augment_with_knowledge(
                    current_content, knowledge_context, task_dict, system_prompt, model_override
                )

            return ContentResult(
                success=True,
                content=current_content,
                agent=self.name,
                tools_used=("knowledge_search",) if knowledge_context else (),
                iterations=len(reflections) + 1,
                metadata={"reflections": reflections, "draft": draft},
            )

        except Exception as exc:
            logger.error(f"ReflectionAgent执行失败: {exc}")
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
        prefs["_max_reflections"] = ctx.get("max_reflections", 3)
        prefs["_draft_content"] = ctx.get("draft_content")

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
    # Planning branch (merged from PlanSolveAgent)
    # ------------------------------------------------------------------

    async def _execute_with_planning(
        self,
        task: Dict[str, Any],
        context: ExecutionContext,
        model_override: str | None,
    ) -> ContentResult:
        """High-complexity path: plan -> execute steps -> integrate -> reflect once."""
        plan_pkg = prompt_optimizer.build_package(task, mode="plan")
        write_pkg = prompt_optimizer.build_package(task, mode="default")

        plan = await self._create_plan(task, plan_pkg.system_prompt, model_override)
        steps = self._parse_plan_steps(plan)

        step_results: list[dict] = []

        for step in steps:
            step_content = await self._execute_step(
                step, task, step_results, write_pkg.system_prompt, model_override
            )
            step_results.append({"step": step, "content": step_content})

        draft = await self._integrate_results(task, step_results, write_pkg.system_prompt, model_override)

        # One reflection pass on the integrated draft
        reflection = await self._reflect(draft, task, write_pkg.system_prompt, model_override)
        final_content = draft
        if self._should_improve(reflection):
            final_content = await self._improve(
                draft, reflection, task, write_pkg.system_prompt, model_override
            )

        return ContentResult(
            success=True,
            content=final_content,
            agent=self.name,
            tools_used=(),
            iterations=len(steps) + 1,
            metadata={"plan": plan, "steps": step_results, "reflection": reflection},
        )

    async def _create_plan(
        self, task: Dict[str, Any], system_prompt: str, model_override: str | None
    ) -> str:
        plan_pkg = prompt_optimizer.build_package(task, mode="plan")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": plan_pkg.user_prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.5, model=model_override)

    @staticmethod
    def _parse_plan_steps(plan: str) -> List[str]:
        steps: list[str] = []
        for line in plan.split("\n"):
            line = line.strip()
            match = re.match(r"^\s*[\d\.\-\*、]\s*(.+)$", line)
            if match:
                steps.append(match.group(1))
        return steps or [plan]

    async def _execute_step(
        self,
        step: str,
        task: Dict[str, Any],
        previous_results: List[Dict[str, Any]],
        system_prompt: str,
        model_override: str | None,
    ) -> str:
        prompt = (
            f"执行以下步骤：{step}\n\n"
            f"任务主题：{task.get('topic', '')}\n"
            f"板块：{task.get('category', 'lifestyle')}\n\n"
        )
        if previous_results:
            prompt += "之前的步骤结果：\n"
            for i, r in enumerate(previous_results):
                prompt += f"步骤 {i + 1} ({r.get('step', '')}):\n{r.get('content', '')}\n\n"
        prompt += "请完成这一步，输出这一步的具体结果或内容。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.7, model=model_override)

    async def _integrate_results(
        self,
        task: Dict[str, Any],
        step_results: List[Dict[str, Any]],
        system_prompt: str,
        model_override: str | None,
    ) -> str:
        req_line = f"额外要求：{task.get('requirements', '')}\n" if task.get("requirements") else ""
        prompt = (
            f"请创作一篇关于「{task.get('topic', '')}」的内容。\n\n"
            f"板块：{task.get('category', 'lifestyle')}\n"
            f"长度：{task.get('length', 'medium')}\n"
            f"风格：{task.get('style', 'professional')}\n"
            f"{req_line}"
            "\n以下是执行各个步骤得到的结果，请整合这些结果创作最终内容：\n\n"
        )
        for i, r in enumerate(step_results):
            prompt += f"步骤 {i + 1}: {r.get('step', '')}\n结果：\n{r.get('content', '')}\n\n"
        prompt += "请基于以上所有步骤的结果，创作一篇完整、连贯、有价值的内容。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.7, model=model_override)

    # ------------------------------------------------------------------
    # Knowledge augmentation
    # ------------------------------------------------------------------

    async def _fetch_knowledge(self, task: Dict[str, Any]) -> str:
        """Optionally fetch knowledge snippets via KnowledgeSearchTool."""
        try:
            from app.tools.knowledge_search import KnowledgeSearchTool

            tool = KnowledgeSearchTool()
            query = f"{task.get('topic', '')}\n{task.get('requirements') or ''}".strip()
            result = await tool.execute({"query": query, "top_k": 3})
            if result.success and result.data and result.data != "未找到相关知识片段":
                return str(result.data)
        except Exception:
            pass
        return ""

    async def _augment_with_knowledge(
        self,
        content: str,
        knowledge_context: str,
        task: Dict[str, Any],
        system_prompt: str,
        model_override: str | None,
    ) -> str:
        """Enrich the final content with retrieved knowledge snippets."""
        prompt = (
            f"请基于以下知识片段，对内容进行补充和完善（如已包含相关信息则保持不变）：\n\n"
            f"当前内容：\n{content}\n\n"
            f"知识片段：\n{knowledge_context}\n\n"
            f"任务主题：{task.get('topic', '')}\n"
            f"请输出完善后的完整内容，确保知识引用准确，并在结尾列出引用来源。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.6, model=model_override)

    # ------------------------------------------------------------------
    # Core reflection helpers
    # ------------------------------------------------------------------

    async def _generate_draft(
        self,
        task: Dict[str, Any],
        system_prompt: str,
        base_user_prompt: str,
        model_override: str | None,
    ) -> str:
        user_prompt = f"{base_user_prompt}\n这是初稿阶段，请先给结构化完整草稿。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.8, model=model_override)

    async def _reflect(
        self,
        content: str,
        task: Dict[str, Any],
        system_prompt: str,
        model_override: str | None,
    ) -> str:
        reflection_pkg = prompt_optimizer.build_package(task, mode="reflection")
        reflection_prompt = (
            f"{reflection_pkg.user_prompt}\n\n"
            f"待评估内容：\n{content}\n\n"
            f"请逐项给出评估结论和可执行的改进建议，不要泛泛而谈。"
        )
        messages = [
            {"role": "system", "content": reflection_pkg.system_prompt},
            {"role": "user", "content": reflection_prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.6, model=model_override)

    @staticmethod
    def _should_improve(reflection: str) -> bool:
        keywords = [
            "需要改进", "可以改进", "存在问题", "不足", "不够",
            "需要", "improve", "better", "issue",
        ]
        return any(kw in reflection.lower() for kw in keywords)

    async def _improve(
        self,
        current_content: str,
        reflection: str,
        task: Dict[str, Any],
        system_prompt: str,
        model_override: str | None,
    ) -> str:
        req_line = f"- 额外要求：{task.get('requirements', '')}\n" if task.get("requirements") else ""
        improvement_prompt = (
            f"请基于以下反思意见改进内容：\n\n"
            f"当前内容：\n{current_content}\n\n"
            f"反思意见：\n{reflection}\n\n"
            f"任务要求：\n"
            f"- 主题：{task.get('topic', '')}\n"
            f"- 长度：{task.get('length', 'medium')}\n"
            f"- 风格：{task.get('style', 'professional')}\n"
            f"{req_line}"
            "\n请根据反思意见改进内容，确保：\n"
            "1. 修正所有指出的问题\n"
            "2. 保持内容的真实性和准确性\n"
            "3. 提升内容的深度和价值\n"
            "4. 优化语言表达，更直白犀利，直接点出要点与痛点\n"
            "5. 改进结构和逻辑\n\n"
            "请输出改进后的完整内容。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": improvement_prompt},
        ]
        return await self.llm_client.achat(messages, temperature=0.7, model=model_override)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_model_override(context: ExecutionContext) -> str | None:
        if context is None:
            return None
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
