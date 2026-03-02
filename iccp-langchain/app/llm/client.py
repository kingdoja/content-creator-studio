"""
LangChain LLM客户端封装
"""
from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, SystemMessage, AIMessage
from typing import List, Dict, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    """LangChain LLM客户端"""
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.model = model or settings.OPENAI_MODEL
        self.temperature = temperature or settings.LLM_TEMPERATURE
        self.base_url = base_url or settings.LLM_BASE_URL
        self.api_key = api_key or settings.OPENAI_API_KEY
        
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url if self.base_url != "https://api.openai.com/v1" else None,
            api_key=self.api_key,
            timeout=settings.LLM_TIMEOUT
        )
        self._llm_cache: Dict[str, ChatOpenAI] = {}
    
    def chat(
        self,
        messages: List[Dict[str, str]] | List[BaseMessage],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """调用LLM生成内容"""
        try:
            # 转换消息格式
            if messages and isinstance(messages[0], dict):
                langchain_messages = self._convert_messages(messages)
            else:
                langchain_messages = messages
            
            llm = self._get_llm(model, temperature)
            response = llm.invoke(langchain_messages)
            
            return response.content
            
        except Exception as e:
            fallback_model = self._fallback_model_name(model)
            if fallback_model and self._should_fallback(e):
                logger.warning("LLM模型不可用，回退到默认模型: from=%s to=%s", model, fallback_model)
                return self.chat(messages, temperature=temperature, model=fallback_model)
            logger.error(f"LLM调用失败: {e}")
            raise Exception(f"LLM调用失败: {e}")

    async def achat(
        self,
        messages: List[Dict[str, str]] | List[BaseMessage],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> str:
        """异步调用LLM生成内容。"""
        try:
            if messages and isinstance(messages[0], dict):
                langchain_messages = self._convert_messages(messages)
            else:
                langchain_messages = messages

            llm = self._get_llm(model, temperature)
            response = await llm.ainvoke(langchain_messages)

            return response.content
        except Exception as e:
            fallback_model = self._fallback_model_name(model)
            if fallback_model and self._should_fallback(e):
                logger.warning("LLM模型不可用，回退到默认模型: from=%s to=%s", model, fallback_model)
                return await self.achat(messages, temperature=temperature, model=fallback_model)
            logger.error(f"LLM异步调用失败: {e}")
            raise Exception(f"LLM异步调用失败: {e}")
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[BaseMessage]:
        """转换消息格式"""
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))
        
        return langchain_messages
    
    def stream(self, messages: List[Dict[str, str]]):
        """流式生成内容"""
        langchain_messages = self._convert_messages(messages)
        return self.llm.stream(langchain_messages)

    def _get_llm(self, model: Optional[str] = None, temperature: Optional[float] = None) -> ChatOpenAI:
        model_name = (model or "").strip()
        use_model = model_name or self.model
        use_temperature = self.temperature if temperature is None else float(temperature)

        # 默认模型 + 默认温度直接复用主实例
        if use_model == self.model and use_temperature == self.temperature:
            return self.llm

        cache_key = f"{use_model}::{use_temperature}"
        cached = self._llm_cache.get(cache_key)
        if cached:
            return cached
        cached = ChatOpenAI(
            model=use_model,
            temperature=use_temperature,
            base_url=self.base_url if self.base_url != "https://api.openai.com/v1" else None,
            api_key=self.api_key,
            timeout=settings.LLM_TIMEOUT,
        )
        self._llm_cache[cache_key] = cached
        return cached

    def _fallback_model_name(self, model: Optional[str]) -> Optional[str]:
        requested = (model or "").strip()
        default_model = (settings.OPENAI_MODEL or "").strip()
        if not requested or not default_model:
            return None
        if requested == default_model:
            return None
        return default_model

    @staticmethod
    def _should_fallback(error: Exception) -> bool:
        text = str(error).lower()
        return any(
            token in text
            for token in [
                "model_not_found",
                "does not exist",
                "you do not have access to it",
                "invalid model",
            ]
        )

# 全局实例
_llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """获取LLM客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
