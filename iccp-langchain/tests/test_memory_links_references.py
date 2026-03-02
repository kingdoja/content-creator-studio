import asyncio
from uuid import uuid4


def _admin_headers(client):
    email = "admin@example.com"
    password = "secret123"
    register_payload = {
        "username": f"admin_{uuid4().hex[:8]}",
        "email": email,
        "password": password,
    }
    reg_resp = client.post("/api/v1/auth/register", json=register_payload)
    if reg_resp.status_code == 200:
        token = reg_resp.json()["access_token"]
    else:
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_memory_entry(
    user_id: str,
    source_module: str = "chat",
    content: str = "测试记忆内容",
    memory_type: str = "episodic",
):
    from app.db.session import AsyncSessionLocal
    from app.memory import get_memory_manager

    async with AsyncSessionLocal() as db:
        manager = get_memory_manager()
        entry = await manager.store.create_memory_entry(
            db,
            user_id=user_id,
            memory_type=memory_type,
            source_module=source_module,
            source_id=f"seed_{uuid4().hex[:12]}",
            content=content,
            importance=0.7,
            tags=[source_module, "test"],
        )
        return entry.id


def test_memory_link_create_and_related_query(client):
    admin_headers = _admin_headers(client)
    user_id = "u_link_related"
    target_memory_id = asyncio.run(
        _seed_memory_entry(
            user_id=user_id,
            source_module="content",
            content="这是一条将被关联的长期记忆",
        )
    )
    source_id = f"src_{uuid4().hex[:12]}"

    create_resp = client.post(
        "/api/v1/memory/links",
        json={
            "source_type": "content_record",
            "source_id": source_id,
            "target_type": "memory_entry",
            "target_id": target_memory_id,
            "relation": "contextual_support",
            "strength": 0.78,
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200
    create_body = create_resp.json()
    assert create_body["success"] is True
    assert create_body["link"]["source_type"] == "content_record"
    assert create_body["link"]["target_type"] == "memory_entry"
    assert create_body["link"]["target_id"] == target_memory_id

    related_resp = client.get(
        "/api/v1/memory/related",
        params={"source_type": "content_record", "source_id": source_id, "limit": 10},
        headers=admin_headers,
    )
    assert related_resp.status_code == 200
    related_body = related_resp.json()
    assert related_body["success"] is True
    assert len(related_body["items"]) >= 1

    hit = related_body["items"][0]
    assert hit["relation"] == "contextual_support"
    assert hit["memory"]["id"] == target_memory_id
    assert hit["memory"]["source_module"] == "content"


def test_memory_link_upsert_keep_single_and_max_strength(client):
    admin_headers = _admin_headers(client)
    user_id = "u_link_upsert"
    target_memory_id = asyncio.run(
        _seed_memory_entry(
            user_id=user_id,
            source_module="chat",
            content="用于测试 link 幂等更新",
        )
    )
    source_id = f"src_{uuid4().hex[:10]}"

    first_resp = client.post(
        "/api/v1/memory/links",
        json={
            "source_type": "content_record",
            "source_id": source_id,
            "target_type": "memory_entry",
            "target_id": target_memory_id,
            "relation": "related_to",
            "strength": 0.35,
        },
        headers=admin_headers,
    )
    assert first_resp.status_code == 200

    second_resp = client.post(
        "/api/v1/memory/links",
        json={
            "source_type": "content_record",
            "source_id": source_id,
            "target_type": "memory_entry",
            "target_id": target_memory_id,
            "relation": "related_to",
            "strength": 0.92,
        },
        headers=admin_headers,
    )
    assert second_resp.status_code == 200

    related_resp = client.get(
        "/api/v1/memory/related",
        params={"source_type": "content_record", "source_id": source_id, "limit": 10},
        headers=admin_headers,
    )
    assert related_resp.status_code == 200
    body = related_resp.json()
    assert body["success"] is True
    assert len(body["items"]) == 1
    assert body["items"][0]["memory"]["id"] == target_memory_id
    assert body["items"][0]["strength"] >= 0.92


def test_knowledge_references_aggregation_and_filter(client):
    admin_headers = _admin_headers(client)
    doc_1_title = f"引用统计文档A-{uuid4().hex[:8]}"
    doc_2_title = f"引用统计文档B-{uuid4().hex[:8]}"

    doc_1_resp = client.post(
        "/api/v1/knowledge/upload",
        json={
            "title": doc_1_title,
            "content": "这是文档A内容，用于引用聚合测试。",
            "source_type": "text",
        },
        headers=admin_headers,
    )
    assert doc_1_resp.status_code == 200
    doc_1_id = doc_1_resp.json()["document"]["id"]

    doc_2_resp = client.post(
        "/api/v1/knowledge/upload",
        json={
            "title": doc_2_title,
            "content": "这是文档B内容，用于引用过滤测试。",
            "source_type": "text",
        },
        headers=admin_headers,
    )
    assert doc_2_resp.status_code == 200
    doc_2_id = doc_2_resp.json()["document"]["id"]

    link_payloads = [
        {
            "source_type": "memory_entry",
            "source_id": f"mem_{uuid4().hex[:12]}",
            "target_type": "knowledge_document",
            "target_id": doc_1_id,
            "relation": "knowledge_citation",
            "strength": 0.7,
        },
        {
            "source_type": "memory_entry",
            "source_id": f"mem_{uuid4().hex[:12]}",
            "target_type": "knowledge_document",
            "target_id": doc_1_id,
            "relation": "knowledge_citation",
            "strength": 0.8,
        },
        {
            "source_type": "memory_entry",
            "source_id": f"mem_{uuid4().hex[:12]}",
            "target_type": "knowledge_document",
            "target_id": doc_2_id,
            "relation": "knowledge_citation",
            "strength": 0.6,
        },
    ]
    for payload in link_payloads:
        link_resp = client.post("/api/v1/memory/links", json=payload, headers=admin_headers)
        assert link_resp.status_code == 200
        assert link_resp.json()["success"] is True

    refs_resp = client.get("/api/v1/knowledge/references", params={"limit": 20}, headers=admin_headers)
    assert refs_resp.status_code == 200
    refs_body = refs_resp.json()
    assert refs_body["success"] is True

    refs_map = {item["document_id"]: item for item in refs_body["references"]}
    assert doc_1_id in refs_map
    assert doc_2_id in refs_map
    assert refs_map[doc_1_id]["reference_count"] >= 2
    assert refs_map[doc_2_id]["reference_count"] >= 1

    filtered_resp = client.get(
        "/api/v1/knowledge/references",
        params={"document_id": doc_2_id, "limit": 20},
        headers=admin_headers,
    )
    assert filtered_resp.status_code == 200
    filtered_body = filtered_resp.json()
    assert filtered_body["success"] is True
    assert len(filtered_body["references"]) == 1
    assert filtered_body["references"][0]["document_id"] == doc_2_id
