"""
ReAct Agent实现（使用LangChain）
"""
from typing import Dict, Any, List
from datetime import datetime
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from app.llm.client import get_llm_client
from app.tools.registry import get_tool_registry
from app.prompting import prompt_optimizer
import logging

logger = logging.getLogger(__name__)

class ReActAgent:
    """ReAct Agent - 使用LangChain实现"""
    
    def __init__(self):
        self.name = "react"
        self.description = "ReAct Agent：通过思考-行动-观察循环完成任务，适合需要实时信息检索和工具调用的任务。"
        self.llm_client = get_llm_client()
        self.tool_registry = get_tool_registry()
    
    async def execute(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行ReAct Agent任务"""
        try:
            model_override = ((context or {}).get("llm_model_override") or "").strip() or None
            is_chat = task.get("module") == "chat"
            prompt_mode = "chat_react" if is_chat else "react"
            prompt_package = prompt_optimizer.build_package(task, mode=prompt_mode)
            system_prompt = prompt_package.system_prompt
            user_prompt = self._build_user_prompt(task, prompt_package.user_prompt, is_chat=is_chat)
            
            # 获取工具
            tools = self.tool_registry.get_langchain_tools()
            
            # 创建ReAct Agent
            agent_executor = await self._create_agent_executor(
                system_prompt,
                tools,
                llm_model_override=model_override,
                max_iterations=context.get("max_iterations", 3) if context else 3
            )
            
            # 执行Agent
            result = await agent_executor.ainvoke({
                "input": user_prompt
            })
            
            content = result.get("output", "")
            
            # 提取使用的工具
            tools_used = []
            if "intermediate_steps" in result:
                for step in result["intermediate_steps"]:
                    if len(step) > 0:
                        tool_name = step[0].tool if hasattr(step[0], "tool") else str(step[0])
                        tools_used.append(tool_name)

            # 兜底：当达到迭代上限时，基于已有中间步骤强制整合最终成稿，避免前端显示停止提示。
            if "Agent stopped due to iteration limit or time limit" in content:
                content = await self._finalize_from_intermediate_steps(
                    task=task,
                    intermediate_steps=result.get("intermediate_steps", []),
                    fallback_text=content,
                    llm_model_override=model_override,
                )
            
            return {
                "success": True,
                "content": content,
                "agent": self.name,
                "tools_used": list(set(tools_used)),
                "iterations": len(result.get("intermediate_steps", [])),
                "metadata": {
                    "steps": result.get("intermediate_steps", [])
                }
            }
            
        except Exception as e:
            logger.error(f"ReActAgent执行失败: {e}")
            return {
                "success": False,
                "content": "",
                "agent": self.name,
                "error": str(e)
            }
    
    async def _create_agent_executor(
        self,
        system_prompt: str,
        tools: List,
        llm_model_override: str | None = None,
        max_iterations: int = 3
    ) -> AgentExecutor:
        """创建Agent Executor"""
        # 构建ReAct Prompt模板
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
        
        # 创建LLM
        llm = ChatOpenAI(
            model=llm_model_override or self.llm_client.model,
            temperature=0.7,
            api_key=self.llm_client.api_key,
            base_url=self.llm_client.base_url if self.llm_client.base_url != "https://api.openai.com/v1" else None
        )
        
        # 创建Agent
        agent = create_react_agent(
            llm=llm,
            tools=tools,
            prompt=react_prompt.partial(system_prompt=system_prompt)
        )
        
        # 创建Executor
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,  # 关闭可避免 Observation 在控制台重复刷屏、与「5 次 Finished chain」混淆
            max_iterations=max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            early_stopping_method="force",
        )
        
        return executor
    
    def _build_user_prompt(self, task: Dict[str, Any], prompt_base: str, *, is_chat: bool = False) -> str:
        """构建用户prompt"""
        requirements = task.get("requirements", "")
        now = datetime.now()
        topic = (task.get("topic") or "").lower()
        freshness_needed = any(
            kw in topic for kw in ["最新", "最近", "今日", "今天", "本周", "本月", "今年", "current", "latest", "today", "recent"]
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
        """当 ReAct 达到迭代上限时，用已有观察结果二次整合成稿。"""
        observations = []
        for i, step in enumerate(intermediate_steps):
            if not step or len(step) < 2:
                continue
            action = step[0]
            observation = step[1]
            tool_name = getattr(action, "tool", "unknown_tool")
            tool_input = getattr(action, "tool_input", "")
            observation_text = str(observation)
            # 限制长度，避免再次把模型上下文淹没
            if len(observation_text) > 1200:
                observation_text = observation_text[:1200] + " ...(截断)"
            observations.append(
                f"[步骤{i + 1}] 工具={tool_name} 输入={tool_input}\n观察={observation_text}"
            )

        is_chat = task.get("module") == "chat"
        if is_chat:
            style_hint = "用温和自然的聊天口吻回答，不要用 Markdown 标题，不要写文章体。"
        else:
            style_hint = "请直接输出最终成稿，不要再输出 Thought/Action。"

        prompt = (
            f"你需要基于已有工具结果回答用户。\n"
            f"主题：{task.get('topic', '')}\n"
            f"板块：{task.get('category', '')}\n"
            f"长度：{task.get('length', 'medium')}\n"
            f"风格：{task.get('style', 'professional')}\n"
            f"额外要求：{task.get('requirements') or '无'}\n\n"
            f"已有观察结果：\n" + ("\n\n".join(observations) if observations else fallback_text) + "\n\n"
            f"{style_hint}"
        )
        messages = [{"role": "user", "content": prompt}]
        return await self.llm_client.achat(messages, temperature=0.6, model=llm_model_override)
