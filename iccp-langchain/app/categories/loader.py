"""
Prompt模板加载器
"""
from pathlib import Path
from typing import Optional
from app.config import settings
from app.categories.config import get_category
import logging

logger = logging.getLogger(__name__)

class PromptLoader:
    """加载和管理板块特定的prompt模板"""
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or settings.PROMPTS_DIR
        self._cache: dict[str, str] = {}
    
    def load_prompt(self, category_id: str) -> str:
        """加载板块的prompt模板"""
        if category_id in self._cache:
            return self._cache[category_id]
        
        try:
            category = get_category(category_id)
            template_file = category.get("prompt_template")
            
            if not template_file:
                # 如果没有模板文件，使用默认prompt
                return self._get_default_prompt(category_id)
            
            prompt_path = self.prompts_dir / template_file
            
            if not prompt_path.exists():
                logger.warning(f"Prompt模板不存在: {prompt_path}，使用默认prompt")
                return self._get_default_prompt(category_id)
            
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt = f.read()
            
            self._cache[category_id] = prompt
            return prompt
            
        except Exception as e:
            logger.error(f"加载prompt失败: {e}")
            return self._get_default_prompt(category_id)

    def get_prompt_file_path(self, category_id: str) -> Path:
        """获取板块 prompt 文件路径。"""
        category = get_category(category_id)
        template_file = category.get("prompt_template")
        if not template_file:
            raise ValueError(f"板块 {category_id} 未配置 prompt_template")
        return self.prompts_dir / template_file

    def save_prompt(self, category_id: str, content: str) -> str:
        """保存板块 prompt，并立即刷新缓存。"""
        prompt_path = self.get_prompt_file_path(category_id)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = (content or "").strip()
        if not normalized:
            raise ValueError("prompt 内容不能为空")
        prompt_path.write_text(normalized + "\n", encoding="utf-8")
        self._cache[category_id] = normalized
        return normalized
    
    def _get_default_prompt(self, category_id: str) -> str:
        """获取默认prompt（板块模板缺失时的兜底）"""
        category = get_category(category_id)
        category_name = category["name"]

        return f"""你是一位专业的{category_name}内容创作者，擅长将专业知识转化为读者可理解、可行动的内容。

板块核心约束：
- 所有关键信息必须来自可靠来源，并在文中注明或提供引用
- 提供具体的数据、案例或证据支持观点
- 内容要有实际价值，能帮助读者解决问题或增长知识
- 区分事实陈述和个人观点，后者明确标注

目标读者：对{category_name}领域感兴趣的一般读者

禁止行为：
- 不要编造引用来源、数据、专家观点
- 不要使用夸张营销语和标题党用语
- 不要为了凑字数而重复同一论点"""

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()

# 全局实例
prompt_loader = PromptLoader()
