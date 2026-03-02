import asyncio
from datetime import datetime, timedelta


def _auth_headers_and_user(client):
    payload = {
        "username": "tester_memory",
        "email": "tester_memory@example.com",
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


async def _seed_memory(user_id: str, source_module: str, content: str, memory_type: str = "episodic"):
    from app.db.session import AsyncSessionLocal
    from app.memory import get_memory_manager

    async with AsyncSessionLocal() as db:
        manager = get_memory_manager()
        await manager.store.create_memory_entry(
            db,
            user_id=user_id,
            memory_type=memory_type,
            source_module=source_module,
            source_id="seed_source",
            content=content,
            importance=0.8,
            tags=[source_module],
        )


def test_memory_entries_pagination_and_time_filter(client):
    headers, user_id = _auth_headers_and_user(client)
    asyncio.run(_seed_memory(user_id, "chat", "第一条：AI 冷启动策略"))
    asyncio.run(_seed_memory(user_id, "video", "第二条：角色风格延续"))
    asyncio.run(_seed_memory(user_id, "content", "第三条：文章结构偏好"))

    resp_page_1 = client.get(
        "/api/v1/memory/entries",
        params={"user_id": user_id, "limit": 2, "offset": 0},
        headers=headers,
    )
    assert resp_page_1.status_code == 200
    body_1 = resp_page_1.json()
    assert body_1["success"] is True
    assert len(body_1["entries"]) == 2
    assert body_1["pagination"]["total"] >= 3
    assert body_1["pagination"]["has_more"] is True

    resp_page_2 = client.get(
        "/api/v1/memory/entries",
        params={"user_id": user_id, "limit": 2, "offset": 2},
        headers=headers,
    )
    assert resp_page_2.status_code == 200
    body_2 = resp_page_2.json()
    assert body_2["success"] is True
    assert len(body_2["entries"]) >= 1

    future_from = (datetime.utcnow() + timedelta(days=1)).isoformat()
    resp_future = client.get(
        "/api/v1/memory/entries",
        params={"user_id": user_id, "created_from": future_from},
        headers=headers,
    )
    assert resp_future.status_code == 200
    future_body = resp_future.json()
    assert future_body["success"] is True
    assert future_body["entries"] == []


def test_memory_delete_and_stats(client):
    headers, user_id = _auth_headers_and_user(client)
    asyncio.run(_seed_memory(user_id, "chat", "待删除记忆", memory_type="episodic"))

    entries_resp = client.get(
        "/api/v1/memory/entries",
        params={"user_id": user_id, "limit": 10},
        headers=headers,
    )
    assert entries_resp.status_code == 200
    entries = entries_resp.json()["entries"]
    assert len(entries) >= 1
    entry_id = entries[0]["id"]

    delete_resp = client.delete(
        f"/api/v1/memory/entries/{entry_id}",
        params={"user_id": user_id},
        headers=headers,
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    stats_resp = client.get("/api/v1/memory/stats", params={"user_id": user_id}, headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()["stats"]
    assert stats["total"] >= 0


def test_video_start_includes_memory_context(client, monkeypatch):
    headers, user_id = _auth_headers_and_user(client)
    asyncio.run(_seed_memory(user_id, "video", "历史剧情：主角是失忆机器人，风格偏赛博朋克。"))
    captured = {}

    async def _fake_create_story_video_task(payload):
        captured["payload"] = payload
        return {
            "success": True,
            "storyline": "mock storyline",
            "video_prompt": "mock prompt",
            "task_id": "task_mock_1",
            "status": "queued",
            "provider": "mock",
            "model": "mock-model",
            "progress_percent": 10,
            "latency_ms": 1,
        }

    monkeypatch.setattr("app.api.v1.content.create_story_video_task", _fake_create_story_video_task)

    resp = client.post(
        "/api/v1/content/generate-story-video/start",
        json={
            "input_text": "继续这个机器人故事，做第二集",
            "provider": "mock",
            "user_id": user_id,
            "use_memory": True,
            "memory_top_k": 4,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["memory_recalled_count"] >= 1
    assert isinstance(body["memory_recalled"], list)
    assert captured["payload"].get("memory_context_text")
