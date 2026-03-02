"""
快速测试脚本（可选走 LangGraph 或直接 Router）
"""
import asyncio
import sys

async def test_agent():
    """测试 Agent 系统（默认使用 LangGraph 编排）"""
    print("=" * 60)
    print("测试 LangGraph + 多 Agent 内容创作平台")
    print("=" * 60)

    try:
        from app.agents.graph import get_content_creation_graph
        use_graph = True
        graph = get_content_creation_graph()
        print("使用 LangGraph 编排\n")
    except Exception as e:
        print(f"LangGraph 不可用 ({e})，改用 Router\n")
        use_graph = False
        graph = None

    router = __import__("app.agents.router", fromlist=["get_agent_router"]).get_agent_router()
    
    # 测试任务1：需要实时数据的财经内容
    print("\n【测试1】财经内容（需要实时数据）")
    print("-" * 60)
    task1 = {
        "category": "finance",
        "topic": "2024年A股市场投资策略",
        "length": "medium",
        "style": "professional"
    }
    
    # 获取Agent建议
    suggestion = router.get_suggestion(task1)
    print(f"推荐Agent: {suggestion['recommended']}")
    print(f"原因: {suggestion['reason']}")
    print(f"任务分析: {suggestion['analysis']}")
    
    # 执行任务
    print("\n执行中...")
    if use_graph:
        result1 = await graph.ainvoke({"task": task1})
    else:
        result1 = await router.route(task1)
    print(f"成功: {result1['success']}")
    print(f"使用的Agent: {result1['agent']}")
    print(f"使用的工具: {result1['tools_used']}")
    print(f"迭代次数: {result1['iterations']}")
    if result1['success']:
        print(f"\n生成的内容（前200字）:\n{result1['content'][:200]}...")
    else:
        print(f"错误: {result1.get('error')}")
    
    # 测试任务2：需要深度思考的AI内容
    print("\n\n【测试2】AI技术内容（需要深度思考）")
    print("-" * 60)
    task2 = {
        "category": "ai",
        "topic": "大语言模型的技术原理和应用",
        "requirements": "需要深度分析技术原理，提供实际应用案例",
        "length": "medium",
        "style": "professional"
    }
    
    suggestion2 = router.get_suggestion(task2)
    print(f"推荐Agent: {suggestion2['recommended']}")
    print(f"原因: {suggestion2['reason']}")
    
    print("\n执行中...")
    if use_graph:
        result2 = await graph.ainvoke({"task": task2})
    else:
        result2 = await router.route(task2)
    print(f"成功: {result2['success']}")
    print(f"使用的Agent: {result2['agent']}")
    print(f"迭代次数: {result2['iterations']}")
    if result2['success']:
        print(f"\n生成的内容（前200字）:\n{result2['content'][:200]}...")
    
    # 测试任务3：需要规划的长文
    print("\n\n【测试3】成长内容（需要规划）")
    print("-" * 60)
    task3 = {
        "category": "growth",
        "topic": "如何提升个人效率",
        "length": "long",
        "style": "professional"
    }
    
    suggestion3 = router.get_suggestion(task3)
    print(f"推荐Agent: {suggestion3['recommended']}")
    print(f"原因: {suggestion3['reason']}")
    
    print("\n执行中...")
    if use_graph:
        result3 = await graph.ainvoke({"task": task3})
    else:
        result3 = await router.route(task3)
    print(f"成功: {result3['success']}")
    print(f"使用的Agent: {result3['agent']}")
    print(f"迭代次数: {result3['iterations']}")
    if result3['success']:
        print(f"\n生成的内容（前200字）:\n{result3['content'][:200]}...")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    # 检查环境变量
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("错误: 请设置 OPENAI_API_KEY 环境变量")
        print("可以在 .env 文件中设置，或运行: export OPENAI_API_KEY=your-key")
        sys.exit(1)
    
    # 运行测试
    asyncio.run(test_agent())
