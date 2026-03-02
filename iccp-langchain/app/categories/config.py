"""
板块配置
定义各个内容板块的元数据和要求
"""
from typing import Dict, Any, List

CategoryConfig = Dict[str, Any]

CATEGORIES: Dict[str, CategoryConfig] = {
    "finance": {
        "name": "财经",
        "description": "财经分析、投资理财、市场趋势等内容",
        "keywords": ["股票", "投资", "理财", "经济", "市场", "金融", "财报", "分析"],
        "requires_real_time_data": True,
        "typical_complexity": "high",
        "prompt_template": "finance_prompt.txt",
        "default_length": "medium",
    },
    "ai": {
        "name": "人工智能",
        "description": "AI技术、机器学习、深度学习、大模型等内容",
        "keywords": ["AI", "人工智能", "机器学习", "深度学习", "大模型", "GPT", "LLM"],
        "requires_real_time_data": True,
        "typical_complexity": "high",
        "prompt_template": "ai_prompt.txt",
        "default_length": "medium",
    },
    "lifestyle": {
        "name": "生活",
        "description": "生活方式、健康、美食、旅行、情感等内容",
        "keywords": ["生活", "健康", "美食", "旅行", "情感", "日常", "分享"],
        "requires_real_time_data": False,
        "typical_complexity": "low",
        "prompt_template": "lifestyle_prompt.txt",
        "default_length": "short",
    },
    "tech": {
        "name": "科技",
        "description": "科技产品、技术趋势、数码评测、创新技术等内容",
        "keywords": ["科技", "产品", "评测", "技术", "创新", "数码", "硬件", "软件"],
        "requires_real_time_data": True,
        "typical_complexity": "medium",
        "prompt_template": "tech_prompt.txt",
        "default_length": "medium",
    },
    "books": {
        "name": "书籍",
        "description": "书评、读书笔记、阅读推荐、文学评论等内容",
        "keywords": ["书籍", "阅读", "书评", "读书", "文学", "推荐", "笔记"],
        "requires_real_time_data": False,
        "typical_complexity": "medium",
        "prompt_template": "books_prompt.txt",
        "default_length": "medium",
    },
    "investment": {
        "name": "投资",
        "description": "投资策略、市场分析、资产配置、投资理念等内容",
        "keywords": ["投资", "策略", "资产", "配置", "市场", "分析", "理念"],
        "requires_real_time_data": True,
        "typical_complexity": "high",
        "prompt_template": "investment_prompt.txt",
        "default_length": "medium",
    },
    "growth": {
        "name": "成长",
        "description": "个人成长、职业发展、技能提升、思维方法等内容",
        "keywords": ["成长", "职业", "技能", "发展", "提升", "思维", "方法"],
        "requires_real_time_data": False,
        "typical_complexity": "medium",
        "prompt_template": "growth_prompt.txt",
        "default_length": "medium",
    },
}

def get_category(category_id: str) -> CategoryConfig:
    """获取板块配置"""
    if category_id not in CATEGORIES:
        raise ValueError(f"未知的板块: {category_id}")
    return CATEGORIES[category_id]

def get_all_categories() -> List[CategoryConfig]:
    """获取所有板块列表"""
    return [
        {"id": k, **v} for k, v in CATEGORIES.items()
    ]

def match_category_by_keywords(text: str) -> str:
    """根据关键词匹配板块"""
    text_lower = text.lower()
    best_match = None
    max_matches = 0
    
    for category_id, config in CATEGORIES.items():
        matches = sum(1 for keyword in config["keywords"] 
                     if keyword.lower() in text_lower)
        if matches > max_matches:
            max_matches = matches
            best_match = category_id
    
    return best_match or "lifestyle"  # 默认返回生活板块
