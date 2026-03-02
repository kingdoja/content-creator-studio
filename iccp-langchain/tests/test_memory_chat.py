import asyncio


class _FakeRouter:
    async def route(self, task, context=None):
        return {
            "success": True,
            "content": f"mock reply: {task.get('topic', '')}",
            "agent": "simple",
            "tools_used": [],
            "iterations": 1,
            "error": None,
        }


def _auth_headers_and_user(client):
    payload = {
        "username": "tester_chat",
        "email": "tester_chat@example.com",
        "password": "secret123",
    }
    reg_resp = client.post("/api/v1/auth/register", json=payload)
    if reg_resp.status_code == 200:
        token = reg_resp.json()["access_token"]
    else:
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    user_id = me_resp.json()["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


def test_chat_session_create_and_send_message(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.chat.get_agent_router", lambda: _FakeRouter())
    headers, user_id = _auth_headers_and_user(client)

    create_resp = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": "u_test", "module": "chat", "title": "测试会话"},
        headers=headers,
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session"]["id"]
    assert session_id

    send_resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/message",
        json={
            "user_id": user_id,
            "content": "帮我写一个AI冷启动方案",
            "category": "ai",
            "style": "professional",
            "length": "medium",
            "use_memory": True,
            "memory_top_k": 4,
        },
        headers=headers,
    )
    assert send_resp.status_code == 200
    body = send_resp.json()
    assert body["success"] is True
    assert body["assistant"]["content"].startswith("mock reply:")
    assert "recalled_count" in body["memory"]


def test_chat_memory_recall(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.chat.get_agent_router", lambda: _FakeRouter())
    headers, user_id = _auth_headers_and_user(client)

    create_resp = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": user_id, "module": "chat", "title": "回忆会话"},
        headers=headers,
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session"]["id"]

    from app.db.session import AsyncSessionLocal
    from app.memory import get_memory_manager

    async def _seed_memory():
        async with AsyncSessionLocal() as db:
            manager = get_memory_manager()
            await manager.store.create_memory_entry(
                db,
                user_id=user_id,
                memory_type="episodic",
                source_module="chat",
                source_id=session_id,
                content="用户之前讨论过 AI 冷启动策略：先做垂直场景 MVP，再做渠道分发。",
                importance=0.9,
                tags=["ai", "冷启动"],
            )

    asyncio.run(_seed_memory())

    send_resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/message",
        json={
            "user_id": user_id,
            "content": "继续聊AI冷启动策略，给我一个可执行计划",
            "category": "ai",
            "style": "professional",
            "length": "medium",
            "use_memory": True,
            "memory_top_k": 4,
        },
        headers=headers,
    )
    assert send_resp.status_code == 200
    body = send_resp.json()
    assert body["success"] is True
    assert body["memory"]["used"] is True
    assert body["memory"]["recalled_count"] >= 1
