"""
LangGraph 编排验证脚本
用于确认图构建与 ainvoke 流程正常（需先 pip install -r requirements.txt）
"""
import asyncio
import sys


async def test_graph():
    from langgraph.graph import StateGraph, START, END
    from app.agents.graph import build_content_creation_graph, get_content_creation_graph

    print("=" * 50)
    print("LangGraph 编排验证")
    print("=" * 50)

    # 1. 构建与编译
    builder = build_content_creation_graph()
    graph = get_content_creation_graph()
    print("[OK] 图构建与编译成功")

    # 2. 仅验证路由与状态结构（不真实调 LLM，需有 OPENAI_API_KEY 才会真正执行）
    task = {
        "category": "lifestyle",
        "topic": "测试主题",
        "length": "short",
        "style": "casual",
    }
    print("\n执行 graph.ainvoke({ task }) ...")
    try:
        final_state = await graph.ainvoke({"task": task})
        print("[OK] ainvoke 返回状态键:", list(final_state.keys()))
        assert "content" in final_state and "agent" in final_state
        print("[OK] 状态含 content / agent")
        print("     agent:", final_state.get("agent"))
        print("     success:", final_state.get("success"))
        print("     content 长度:", len(final_state.get("content", "")))
    except Exception as e:
        print("[FAIL] ainvoke 异常:", e)
        raise

    print("\n" + "=" * 50)
    print("验证完成")
    print("=" * 50)


if __name__ == "__main__":
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    if not os.getenv("OPENAI_API_KEY"):
        print("提示: 未设置 OPENAI_API_KEY，ainvoke 可能因调用 LLM 失败而报错")
        print("设置后即可完整验证。继续尝试...\n")
    asyncio.run(test_graph())
