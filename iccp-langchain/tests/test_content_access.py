from uuid import uuid4


class _FakeGraph:
    async def ainvoke(self, _state):
        return {
            "success": True,
            "content": "mock content",
            "agent": "simple",
            "tools_used": [],
            "iterations": 1,
            "agent_selected": "simple",
            "task_analysis": {},
            "quality_gate_passed": True,
            "quality_gate_reason": "ok",
            "execution_trace": ["mock"],
            "error": None,
        }


def _register_and_get_auth(client, *, email: str | None = None):
    suffix = uuid4().hex[:8]
    payload = {
        "username": f"user_{suffix}",
        "email": email or f"user_{suffix}@example.com",
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
    return {"Authorization": f"Bearer {token}"}, me_resp.json()["user"]


def test_content_history_is_user_scoped(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.content.get_content_creation_graph", lambda: _FakeGraph())

    headers_a, user_a = _register_and_get_auth(client)
    headers_b, _ = _register_and_get_auth(client)

    create_resp = client.post(
        "/api/v1/content/create",
        json={
            "category": "ai",
            "topic": "A用户主题",
            "length": "medium",
            "style": "professional",
            "use_memory": False,
            "user_id": user_a["id"],
        },
        headers=headers_a,
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["success"] is True

    history_b = client.get("/api/v1/content/history?limit=20", headers=headers_b)
    assert history_b.status_code == 200
    items_b = history_b.json()["items"]
    assert all(item["topic"] != "A用户主题" for item in items_b)


def test_admin_can_query_other_user_content_history(client, monkeypatch):
    monkeypatch.setattr("app.api.v1.content.get_content_creation_graph", lambda: _FakeGraph())

    user_headers, user = _register_and_get_auth(client)
    admin_headers, _ = _register_and_get_auth(client, email="admin@example.com")

    create_resp = client.post(
        "/api/v1/content/create",
        json={
            "category": "ai",
            "topic": "用户历史内容",
            "length": "medium",
            "style": "professional",
            "use_memory": False,
            "user_id": user["id"],
        },
        headers=user_headers,
    )
    assert create_resp.status_code == 200

    history_resp = client.get(
        f"/api/v1/content/history?limit=20&user_id={user['id']}",
        headers=admin_headers,
    )
    assert history_resp.status_code == 200
    items = history_resp.json()["items"]
    assert any(item["topic"] == "用户历史内容" for item in items)
