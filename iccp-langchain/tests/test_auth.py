from uuid import uuid4


def _register_and_get_auth(client, *, is_admin: bool = False):
    suffix = uuid4().hex[:8]
    email = "admin@example.com" if is_admin else f"user_{suffix}@example.com"
    payload = {
        "username": f"user_{suffix}",
        "email": email,
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


def test_register_login_and_me(client):
    register_payload = {
        "username": "tester1",
        "email": "tester1@example.com",
        "password": "secret123",
    }
    reg_resp = client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert reg_data["success"] is True
    assert reg_data["access_token"]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["success"] is True
    assert me_data["user"]["email"] == register_payload["email"]


def test_anonymous_cannot_access_named_user_scope(client):
    admin_headers, admin_user = _register_and_get_auth(client, is_admin=True)
    user_id = admin_user["id"]

    create_resp = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": user_id, "module": "chat", "title": "admin会话"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 200

    # 未登录请求传 user_id，应被解析为 anonymous 域，因此看不到登录用户会话
    anonymous_list_resp = client.get(
        "/api/v1/chat/sessions",
        params={"user_id": user_id, "module": "chat", "limit": 20},
    )
    assert anonymous_list_resp.status_code == 200
    sessions = anonymous_list_resp.json()["sessions"]
    assert isinstance(sessions, list)
    assert all(item.get("user_id") == "anonymous" for item in sessions)


def test_regular_user_cannot_access_other_user_chat_session(client):
    headers_a, user_a = _register_and_get_auth(client)
    headers_b, _ = _register_and_get_auth(client)

    create_resp = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": user_a["id"], "module": "chat", "title": "A的会话"},
        headers=headers_a,
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session"]["id"]

    forbidden_resp = client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers=headers_b,
    )
    assert forbidden_resp.status_code == 403


def test_admin_can_query_other_user_memory_scope(client):
    admin_headers, _ = _register_and_get_auth(client, is_admin=True)
    user_headers, user = _register_and_get_auth(client)

    create_resp = client.post(
        "/api/v1/chat/sessions",
        json={"user_id": user["id"], "module": "chat", "title": "普通用户会话"},
        headers=user_headers,
    )
    assert create_resp.status_code == 200

    # 管理员通过 user_id 访问用户域数据应成功
    stats_resp = client.get(
        "/api/v1/memory/stats",
        params={"user_id": user["id"]},
        headers=admin_headers,
    )
    assert stats_resp.status_code == 200
    assert stats_resp.json()["success"] is True
