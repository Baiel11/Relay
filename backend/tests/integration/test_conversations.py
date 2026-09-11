CONVERSATIONS_URL = "/api/v1/conversations"


async def register(client, email, username, password="StrongPass123!"):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


async def login(client, email, password="StrongPass123!"):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def auth_header(client, email):
    return {"Authorization": f"Bearer {await login(client, email)}"}


async def test_create_conversation(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")

    resp = await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": str(bob["id"])},
        headers=await auth_header(client, "alice@example.com"),
    )
    assert resp.status_code == 201

    data = resp.json()
    assert data["id"]
    assert data["other_user"]["id"] == bob["id"]
    assert data["other_user"]["username"] == "bob"


async def test_create_conversation_is_unique_reversed(client):
    alice = await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")

    first = await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": str(bob["id"])},
        headers=await auth_header(client, "alice@example.com"),
    )
    assert first.status_code == 201

    second = await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": str(alice["id"])},
        headers=await auth_header(client, "bob@example.com"),
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


async def test_create_conversation_with_self_rejected(client):
    alice = await register(client, "alice@example.com", "alice")

    resp = await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": str(alice["id"])},
        headers=await auth_header(client, "alice@example.com"),
    )
    assert resp.status_code == 400
    assert "yourself" in resp.json()["detail"].lower()


async def test_create_conversation_other_user_not_found(client):
    await register(client, "alice@example.com", "alice")

    resp = await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": "00000000-0000-0000-0000-000000000000"},
        headers=await auth_header(client, "alice@example.com"),
    )
    assert resp.status_code == 404


async def test_list_conversations_only_members(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    await register(client, "carol@example.com", "carol")

    await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": str(bob["id"])},
        headers=await auth_header(client, "alice@example.com"),
    )

    alice_list = await client.get(
        CONVERSATIONS_URL, headers=await auth_header(client, "alice@example.com")
    )
    assert alice_list.status_code == 200
    assert alice_list.json()["total"] == 1
    assert alice_list.json()["items"][0]["other_user"]["username"] == "bob"

    carol_list = await client.get(
        CONVERSATIONS_URL, headers=await auth_header(client, "carol@example.com")
    )
    assert carol_list.json()["total"] == 0
    assert carol_list.json()["items"] == []


async def test_list_conversations_multiple(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    carol = await register(client, "carol@example.com", "carol")

    headers = await auth_header(client, "alice@example.com")
    await client.post(CONVERSATIONS_URL, json={"other_user_id": str(bob["id"])}, headers=headers)
    await client.post(CONVERSATIONS_URL, json={"other_user_id": str(carol["id"])}, headers=headers)

    resp = await client.get(CONVERSATIONS_URL, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["other_user"]["username"] for item in body["items"]} == {"bob", "carol"}


async def test_list_conversations_requires_auth(client):
    resp = await client.get(CONVERSATIONS_URL)
    assert resp.status_code == 401