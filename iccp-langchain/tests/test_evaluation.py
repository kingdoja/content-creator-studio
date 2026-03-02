from app.evaluation import score_content


def test_score_content_returns_dimensions():
    result = score_content("这是一段用于测试的内容。结论：建议持续优化。资料引用：内部文档。", topic="测试")
    assert "total_score" in result
    assert "dimensions" in result
    assert "accuracy" in result["dimensions"]
    assert isinstance(result["advice"], list)
