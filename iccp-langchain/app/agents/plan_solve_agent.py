"""
Plan-and-Solve Agent实现
通过制定计划、分步执行、整合结果的方式完成任务
"""
from typing import Dict, Any, List
from app.llm.client import get_llm_client
from app.tools.registry import get_tool_registry
from app.prompting import prompt_optimizer
import logging
import json
import re

logger = logging.getLogger(__name__)

class PlanSolveAgent:
    """Plan-and-Solve Agent - 通过规划分步执行"""
    
    def __init__(self):
        self.name = "plan_solve"
        self.description = "Plan-and-Solve Agent：通过制定计划、分步执行、整合结果的方式完成复杂任务。"
        self.llm_client = get_llm_client()
        self.tool_registry = get_tool_registry()
    
    async def execute(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行Plan-and-Solve Agent任务"""
        try:
            model_override = ((context or {}).get("llm_model_override") or "").strip() or None
            # 计划阶段与写作阶段的提示词目标不同：计划要“可解析可执行”，写作要“可成稿”
            plan_pkg = prompt_optimizer.build_package(task, mode="plan")
            write_pkg = prompt_optimizer.build_package(task, mode="default")
            
            # 第一步：制定计划
            plan = await self._create_plan(task, plan_pkg.system_prompt, model_override)
            
            # 解析计划步骤
            steps = self._parse_plan_steps(plan)
            
            # 第二步：分步执行
            step_results = []
            tools_used = []
            
            for i, step in enumerate(steps):
                # 判断步骤是否需要工具
                if self._step_needs_tool(step):
                    tool_result = await self._execute_step_with_tool(step, task)
                    step_results.append({
                        "step": step,
                        "content": tool_result.get("content", ""),
                        "tool": tool_result.get("tool")
                    })
                    if tool_result.get("tool"):
                        tools_used.append(tool_result["tool"])
                else:
                    step_content = await self._execute_step(
                        step,
                        task,
                        step_results,
                        write_pkg.system_prompt,
                        model_override,
                    )
                    step_results.append({
                        "step": step,
                        "content": step_content
                    })
            
            # 第三步：整合结果
            final_content = await self._integrate_results(
                task,
                step_results,
                write_pkg.system_prompt,
                model_override,
            )
            
            return {
                "success": True,
                "content": final_content,
                "agent": self.name,
                "tools_used": list(set(tools_used)),
                "iterations": len(steps),
                "metadata": {
                    "plan": plan,
                    "steps": step_results
                }
            }
            
        except Exception as e:
            logger.error(f"PlanSolveAgent执行失败: {e}")
            return {
                "success": False,
                "content": "",
                "agent": self.name,
                "error": str(e)
            }
    
    async def _create_plan(
        self,
        task: Dict[str, Any],
        system_prompt: str,
        model_override: str | None = None,
    ) -> str:
        """创建执行计划"""
        # system_prompt 由外部传入（已是 plan 模式组装后的 prompt）
        plan_pkg = prompt_optimizer.build_package(task, mode="plan")
        plan_prompt = f"""{plan_pkg.user_prompt}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": plan_prompt}
        ]

        return await self.llm_client.achat(messages, temperature=0.5, model=model_override)
    
    def _parse_plan_steps(self, plan: str) -> List[str]:
        """解析计划步骤"""
        lines = plan.split('\n')
        steps = []
        
        for line in lines:
            line = line.strip()
            # 匹配 "1. 步骤描述" 或 "- 步骤描述" 格式
            match = re.match(r'^\s*[\d\.\-\*、]\s*(.+)$', line)
            if match:
                steps.append(match.group(1))
        
        # 如果没有找到步骤，将整个计划作为一个步骤
        if not steps:
            steps = [plan]
        
        return steps
    
    def _step_needs_tool(self, step: str) -> bool:
        """判断步骤是否需要工具"""
        step_lower = step.lower()
        return any(keyword in step_lower for keyword in [
            "搜索", "查找", "验证", "核查", "search", "verify"
        ])
    
    async def _execute_step_with_tool(
        self,
        step: str,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用工具执行步骤"""
        step_lower = step.lower()
        
        if "搜索" in step_lower or "查找" in step_lower:
            # 提取搜索关键词
            search_match = re.search(r'搜索[：:]\s*([^\n]+)|查找[：:]\s*([^\n]+)', step)
            query = search_match.group(1) or search_match.group(2) if search_match else task.get("topic", "")
            
            tool = self.tool_registry.get_tool("web_search")
            if tool:
                result = await tool.execute({"query": query})
                return {
                    "content": json.dumps(result.data, ensure_ascii=False) if result.success else f"搜索失败: {result.error}",
                    "tool": "web_search"
                }
        
        if "验证" in step_lower or "核查" in step_lower:
            tool = self.tool_registry.get_tool("fact_check")
            if tool:
                result = await tool.execute({"claim": task.get("topic", "")})
                return {
                    "content": json.dumps(result.data, ensure_ascii=False) if result.success else f"验证失败: {result.error}",
                    "tool": "fact_check"
                }
        
        return {"content": f"工具执行完成: {step}"}
    
    async def _execute_step(
        self,
        step: str,
        task: Dict[str, Any],
        previous_results: List[Dict[str, Any]],
        system_prompt: str,
        model_override: str | None = None,
    ) -> str:
        """执行普通步骤"""
        prompt = f"""执行以下步骤：{step}

任务主题：{task.get('topic', '')}
板块：{task.get('category', 'lifestyle')}

"""
        
        if previous_results:
            prompt += "之前的步骤结果：\n"
            for i, result in enumerate(previous_results):
                prompt += f"步骤 {i+1} ({result.get('step', '')}):\n{result.get('content', '')}\n\n"
        
        prompt += "请完成这一步，输出这一步的具体结果或内容。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        return await self.llm_client.achat(messages, temperature=0.7, model=model_override)
    
    async def _integrate_results(
        self,
        task: Dict[str, Any],
        step_results: List[Dict[str, Any]],
        system_prompt: str,
        model_override: str | None = None,
    ) -> str:
        """整合所有步骤的结果"""
        prompt = f"""请创作一篇关于「{task.get('topic', '')}」的内容。

板块：{task.get('category', 'lifestyle')}
长度：{task.get('length', 'medium')}
风格：{task.get('style', 'professional')}
{f"额外要求：{task.get('requirements', '')}" if task.get('requirements') else ''}

以下是执行各个步骤得到的结果，请整合这些结果创作最终内容：

"""
        
        for i, result in enumerate(step_results):
            prompt += f"步骤 {i+1}: {result.get('step', '')}\n"
            prompt += f"结果：\n{result.get('content', '')}\n\n"
        
        prompt += """请基于以上所有步骤的结果，创作一篇完整、连贯、有价值的内容。确保：
1. 整合所有步骤的信息，不遗漏关键发现
2. 保持内容的连贯性和逻辑性
3. 按照 system prompt 中的板块约束和输出格式要求输出"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        return await self.llm_client.achat(messages, temperature=0.7, model=model_override)
