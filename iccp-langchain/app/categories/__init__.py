"""
板块系统
"""
from .config import CATEGORIES, get_category, get_all_categories
from .loader import PromptLoader

__all__ = ["CATEGORIES", "get_category", "get_all_categories", "PromptLoader"]
