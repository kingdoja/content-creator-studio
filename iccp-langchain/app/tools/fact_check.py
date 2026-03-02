"""
事实核查工具
"""
from typing import Dict, Any, List
from app.tools.base import BaseTool, ToolResult
from app.tools.web_search import WebSearchTool
import logging

logger = logging.getLogger(__name__)

class FactCheckTool(BaseTool):
    """事实核查工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "fact_check"
        self.description = "验证特定声明或事实的准确性。通过交叉验证多个来源来确保信息的可靠性。"
        self.web_search = WebSearchTool()
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行事实核查"""
        claim = params.get("claim", "")
        sources = params.get("sources", [])
        
        if not claim:
            return ToolResult(
                success=False,
                error="缺少声明参数 claim"
            )
        
        try:
            # 搜索相关信息
            search_result = await self.web_search.execute({
                "query": claim,
                "max_results": 5
            })
            
            if not search_result.success:
                return ToolResult(
                    success=False,
                    error="搜索失败，无法进行事实核查"
                )
            
            # 分析搜索结果
            verification = await self._verify_claim(claim, search_result.data.get("results", []))
            
            return ToolResult(
                success=True,
                data={
                    "claim": claim,
                    "verified": verification["verified"],
                    "confidence": verification["confidence"],
                    "evidence": verification["evidence"],
                    "sources": verification["sources"]
                },
                sources=verification["sources"],
                metadata={
                    "verification_time": verification.get("verification_time")
                }
            )
            
        except Exception as e:
            logger.error(f"事实核查失败: {e}")
            return ToolResult(
                success=False,
                error=f"事实核查失败: {str(e)}"
            )
    
    async def _verify_claim(self, claim: str, search_results: List[Dict]) -> Dict[str, Any]:
        """验证声明"""
        # 简单的验证逻辑：检查多个来源是否支持该声明
        supporting_sources = []
        conflicting_sources = []
        
        for result in search_results:
            snippet = result.get("snippet", "").lower()
            url = result.get("url", "")
            
            # 简单的关键词匹配（实际应该使用更复杂的NLP方法）
            claim_keywords = claim.lower().split()
            match_count = sum(1 for keyword in claim_keywords if keyword in snippet)
            
            if match_count >= len(claim_keywords) * 0.5:  # 50%匹配
                supporting_sources.append(url)
            else:
                conflicting_sources.append(url)
        
        # 判断可信度
        total_sources = len(search_results)
        support_ratio = len(supporting_sources) / total_sources if total_sources > 0 else 0
        
        if support_ratio >= 0.7:
            confidence = "high"
            verified = True
        elif support_ratio >= 0.5:
            confidence = "medium"
            verified = True
        else:
            confidence = "low"
            verified = False
        
        return {
            "verified": verified,
            "confidence": confidence,
            "evidence": [
                f"{len(supporting_sources)}个来源支持此声明",
                f"{len(conflicting_sources)}个来源有不同观点"
            ],
            "sources": supporting_sources[:3],  # 返回前3个支持来源
            "verification_time": "now"
        }
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """返回参数schema"""
        return {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "需要验证的声明或事实"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "已有的信息来源（URL数组）"
                }
            },
            "required": ["claim"]
        }
