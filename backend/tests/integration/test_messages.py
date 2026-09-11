import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.message import Message

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CONVERSATIONS_URL = "/api/v1/conversations"


async def register(client, email, username, password="StrongPass123!"):
    resp = await client.post(
        REGISTER_URL,
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


async def login(client, email, password="StrongPass123!"):
    resp = await client.post(
        LOGIN_URL,
        json={"email": email, "password": password},
    )
    return resp.json()["access_token"]


async def auth_header(client, email):
    return {"Authorization": f"Bearer {await login(client, email)}"}


async def create_conversation(client, token, other_user_id):
    resp = await client.post(
        CONVERSATIONS_URL,
        json={"other_user_id": str(other_user_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def messages_url(conversation_id):
    return f"/api/v1/conversations/{conversation_id}/messages"


async def insert_message(session, conversation_id, sender_id, content, created_at):
    msg = Message(
        conversation_id=uuid.UUID(str(conversation_id)),
        sender_id=uuid.UUID(str(sender_id)),
        content=content,
        client_message_id=uuid.uuid4(),
        created_at=created_at,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def test_send_message(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    token = await login(client, "alice@example.com")
    conversation_id = await create_conversation(client, token, bob["id"])

    client_msg_id = uuid.uuid4()
    resp = await client.post(
        messages_url(conversation_id),
        json={"content": "Hello Bob!", "client_message_id": str(client_msg_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    data = resp.json()
    assert data["id"]
    assert data["conversation_id"] == conversation_id
    assert data["sender_id"] is not None
    assert data["content"] == "Hello Bob!"
    assert data["client_message_id"] == str(client_msg_id)
    assert data["read_at"] is None


async def test_message_idempotency(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    token = await login(client, "alice@example.com")
    conversation_id = await create_conversation(client, token, bob["id"])

    client_msg_id = uuid.uuid4()
    url = messages_url(conversation_id)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"content": "Hello Bob!", "client_message_id": str(client_msg_id)}

    first = await client.post(url, json=payload, headers=headers)
    second = await client.post(url, json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_send_message_non_member_forbidden(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    carol = await register(client, "carol@example.com", "carol")

    alice_token = await login(client, "alice@example.com")
    conversation_id = await create_conversation(client, alice_token, bob["id"])

    carol_token = await login(client, "carol@example.com")
    resp = await client.post(
        messages_url(conversation_id),
        json={"content": "intruder"},
        headers={"Authorization": f"Bearer {carol_token}"},
    )
    assert resp.status_code == 403


async def test_send_message_conversation_not_found(client):
    await register(client, "alice@example.com", "alice")
    token = await login(client, "alice@example.com")

    resp = await client.post(
        messages_url(str(uuid.uuid4())),
        json={"content": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_send_empty_content_validation(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    token = await login(client, "alice@example.com")
    conversation_id = await create_conversation(client, token, bob["id"])

    resp = await client.post(
        messages_url(conversation_id),
        json={"content": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_list_messages_newest_first(client, session):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    alice_token = await login(client, "alice@example.com")
    bob_token = await login(client, "bob@example.com")
    conversation_id = await create_conversation(client, alice_token, bob["id"])

    base = datetime.now(timezone.utc)
    for i in range(3):
        await insert_message(
            session, conversation_id, bob["id"], f"msg-{i}", base + timedelta(minutes=i)
        )

    resp = await client.get(
        messages_url(conversation_id),
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [m["content"] for m in body["items"]] == ["msg-2", "msg-1", "msg-0"]
    assert body["has_more"] is False


async def test_list_messages_pagination_and_has_more(client, session):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    alice_token = await login(client, "alice@example.com")
    bob_token = await login(client, "bob@example.com")
    conversation_id = await create_conversation(client, alice_token, bob["id"])

    base = datetime.now(timezone.utc)
    ids = []
    for i in range(5):
        msg = await insert_message(
            session, conversation_id, bob["id"], f"msg-{i}", base + timedelta(minutes=i)
        )
        ids.append(str(msg.id))

    url = messages_url(conversation_id)
    headers = {"Authorization": f"Bearer {alice_token}"}

    page1 = await client.get(url, params={"limit": 2}, headers=headers)
    assert page1.status_code == 200
    body1 = page1.json()
    assert [m["content"] for m in body1["items"]] == ["msg-4", "msg-3"]
    assert body1["has_more"] is True

    oldest_on_page1 = body1["items"][-1]["id"]
    page2 = await client.get(
        url, params={"limit": 2, "before": oldest_on_page1}, headers=headers
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert [m["content"] for m in body2["items"]] == ["msg-2", "msg-1"]
    assert body2["has_more"] is True

    oldest_on_page2 = body2["items"][-1]["id"]
    page3 = await client.get(
        url, params={"limit": 2, "before": oldest_on_page2}, headers=headers
    )
    body3 = page3.json()
    assert [m["content"] for m in body3["items"]] == ["msg-0"]
    assert body3["has_more"] is False


async def test_list_messages_invalid_cursor(client):
    await register(client, "alice@example.com", "alice")
    bob = await register(client, "bob@example.com", "bob")
    token = await login(client, "alice@example.com")
    conversation_id = await create_conversation(client, token, bob["id"])

    resp = await client.get(
        messages_url(conversation_id),
        params={"before": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "cursor" in resp.json()["detail"].lower()


async def test_list_messages_requires_auth(client):
    resp = await client.get(messages_url(str(uuid.uuid4())))
    assert resp.status_code == 401