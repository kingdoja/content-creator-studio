"""
Reflection Agent实现
通过生成-反思-改进循环优化内容质量
"""
from typing import Dict, Any
from app.llm.client import get_llm_client
from app.prompting import prompt_optimizer
import logging

logger = logging.getLogger(__name__)

class ReflectionAgent:
    """Reflection Agent - 通过反思优化内容质量"""
    
    def __init__(self):
        self.name = "reflection"
        self.description = "Reflection Agent：通过生成初稿、反思评估、改进优化的循环来创作高质量内容。"
        self.llm_client = get_llm_client()
    
    async def execute(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行Reflection Agent任务"""
        try:
            model_override = ((context or {}).get("llm_model_override") or "").strip() or None
            max_reflections = context.get("max_reflections", 3) if context else 3
            prompt_package = prompt_optimizer.build_package(task, mode="draft")
            system_prompt = prompt_package.system_prompt

            # 支持在图内对已有草稿进行反思优化
            draft = (context or {}).get("draft_content")
            if not draft:
                draft = await self._generate_draft(
                    task, system_prompt, prompt_package.user_prompt, model_override
                )
            
            # 反思-改进循环
            current_content = draft
            reflections = []
            
            for i in range(max_reflections):
                # 反思阶段
                reflection = await self._reflect(current_content, task, system_prompt, model_override)
                reflections.append(reflection)
                
                # 判断是否需要改进
                should_improve = self._should_improve(reflection)
                if not should_improve:
                    break
                
                # 改进阶段
                current_content = await self._improve(
                    current_content,
                    reflection,
                    task,
                    system_prompt,
                    model_override,
                )
            
            return {
                "success": True,
                "content": current_content,
                "agent": self.name,
                "tools_used": [],
                "iterations": len(reflections) + 1,
                "metadata": {
                    "reflections": reflections,
                    "draft": draft
                }
            }
            
        except Exception as e:
            logger.error(f"ReflectionAgent执行失败: {e}")
            return {
                "success": False,
                "content": "",
                "agent": self.name,
                "error": str(e)
            }
    
    async def _generate_draft(
        self,
        task: Dict[str, Any],
        system_prompt: str,
        base_user_prompt: str,
        model_override: str | None = None,
    ) -> str:
        """生成初稿"""
        user_prompt = f"{base_user_prompt}\n这是初稿阶段，请先给结构化完整草稿。"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.llm_client.achat(messages, temperature=0.8, model=model_override)
    
    async def _reflect(
        self,
        content: str,
        task: Dict[str, Any],
        system_prompt: str,
        model_override: str | None = None,
    ) -> str:
        """反思内容质量"""
        reflection_pkg = prompt_optimizer.build_package(task, mode="reflection")

        reflection_prompt = f"""{reflection_pkg.user_prompt}

待评估内容：
{content}

请逐项给出评估结论和可执行的改进建议，不要泛泛而谈。"""

        messages = [
            {"role": "system", "content": reflection_pkg.system_prompt},
            {"role": "user", "content": reflection_prompt}
        ]

        return await self.llm_client.achat(messages, temperature=0.6, model=model_override)
    
    def _should_improve(self, reflection: str) -> bool:
        """判断是否需要改进"""
        improvement_keywords = [
            "需要改进", "可以改进", "存在问题", "不足", "不够",
            "需要", "improve", "better", "issue"
        ]
        
        reflection_lower = reflection.lower()
        return any(keyword in reflection_lower for keyword in improvement_keywords)
    
    async def _improve(
        self,
        current_content: str,
        reflection: str,
        task: Dict[str, Any],
        system_prompt: str,
        model_override: str | None = None,
    ) -> str:
        """改进内容"""
        improvement_prompt = f"""请基于以下反思意见改进内容：

当前内容：
{current_content}

反思意见：
{reflection}

任务要求：
- 主题：{task.get('topic', '')}
- 长度：{task.get('length', 'medium')}
- 风格：{task.get('style', 'professional')}
{f"- 额外要求：{task.get('requirements', '')}" if task.get('requirements') else ''}

请根据反思意见改进内容，确保：
1. 修正所有指出的问题
2. 保持内容的真实性和准确性
3. 提升内容的深度和价值
4. 优化语言表达，更直白犀利，直接点出要点与痛点
5. 改进结构和逻辑

请输出改进后的完整内容。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": improvement_prompt}
        ]
        
        return await self.llm_client.achat(messages, temperature=0.7, model=model_override)
    
