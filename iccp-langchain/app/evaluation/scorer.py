from typing import Any, Dict


def score_content(content: str, topic: str = "") -> Dict[str, Any]:
    text = (content or "").strip()
    length = len(text)
    topic_hit = 1 if topic and topic.lower() in text.lower() else 0

    # 轻量规则评分，后续可替换为 LLM-as-Judge
    accuracy = 60 + min(25, topic_hit * 15 + (5 if "资料引用" in text else 0))
    relevance = 50 + min(35, topic_hit * 20 + (10 if length > 400 else 0))
    completeness = min(95, 40 + length // 30)
    readability = 70 + (5 if "。" in text else 0) + (5 if "\n" in text else 0)
    originality = 60 + (10 if "观点" in text or "建议" in text else 0)
    professionalism = 65 + (10 if "结论" in text or "风险" in text else 0)

    dimensions = {
        "accuracy": int(max(0, min(100, accuracy))),
        "relevance": int(max(0, min(100, relevance))),
        "completeness": int(max(0, min(100, completeness))),
        "readability": int(max(0, min(100, readability))),
        "originality": int(max(0, min(100, originality))),
        "professionalism": int(max(0, min(100, professionalism))),
    }
    total = round(sum(dimensions.values()) / len(dimensions), 2)
    advice = []
    if dimensions["accuracy"] < 75:
        advice.append("补充可验证事实与来源引用")
    if dimensions["completeness"] < 75:
        advice.append("扩展背景、方法和结论三段结构")
    if dimensions["readability"] < 75:
        advice.append("增加分段与小标题，减少长句")
    if not advice:
        advice.append("整体质量较好，可继续优化案例和数据支撑")

    return {"total_score": total, "dimensions": dimensions, "advice": advice}
