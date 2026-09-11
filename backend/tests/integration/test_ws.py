import time
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.database import Base, get_db
from app.main import app
from app.services.connection_manager import connection_manager


@pytest.fixture
def ws_client():
    connection_manager.reset()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        connection_manager.reset()


def register(client, email, username, password="StrongPass123!"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


def login(client, email, password="StrongPass123!"):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def create_conversation(client, token, other_user_id):
    resp = client.post(
        "/api/v1/conversations",
        json={"other_user_id": str(other_user_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def messages_url(conversation_id):
    return f"/api/v1/conversations/{conversation_id}/messages"


def setup_pair(client):
    alice = register(client, "alice@example.com", "alice")
    bob = register(client, "bob@example.com", "bob")
    alice_token = login(client, "alice@example.com")
    bob_token = login(client, "bob@example.com")
    conversation_id = create_conversation(client, alice_token, bob["id"])
    return alice, bob, alice_token, bob_token, conversation_id


def ws_url(token):
    return f"/ws?token={token}"


def test_ws_rejects_missing_token(ws_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect("/ws"):
            pass
    assert exc_info.value.code == 4401


def test_ws_rejects_invalid_token(ws_client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect("/ws?token=not-a-token"):
            pass
    assert exc_info.value.code == 4401


def test_ws_send_message_ack_and_broadcast(ws_client):
    alice, bob, alice_token, bob_token, conversation_id = setup_pair(ws_client)

    with ws_client.websocket_connect(ws_url(alice_token)) as alice_ws:
        with ws_client.websocket_connect(ws_url(bob_token)) as bob_ws:
            alice_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert alice_ws.receive_json()["type"] == "messages"
            bob_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert bob_ws.receive_json()["type"] == "messages"

            alice_ws.send_json(
                {
                    "type": "send_message",
                    "conversation_id": conversation_id,
                    "content": "Hello Bob!",
                }
            )
            ack = alice_ws.receive_json()
            assert ack["type"] == "ack"
            assert ack["data"]["created"] is True
            assert ack["data"]["message"]["content"] == "Hello Bob!"

            delivered = bob_ws.receive_json()
            assert delivered["type"] == "message"
            assert delivered["data"]["content"] == "Hello Bob!"
            assert delivered["data"]["sender_id"] == alice["id"]
            assert delivered["data"]["conversation_id"] == conversation_id


def test_ws_send_message_idempotent_no_duplicate(ws_client):
    alice, bob, alice_token, bob_token, conversation_id = setup_pair(ws_client)
    client_msg_id = str(uuid.uuid4())

    with ws_client.websocket_connect(ws_url(alice_token)) as alice_ws:
        with ws_client.websocket_connect(ws_url(bob_token)) as bob_ws:
            alice_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert alice_ws.receive_json()["type"] == "messages"
            bob_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert bob_ws.receive_json()["type"] == "messages"

            payload = {
                "type": "send_message",
                "conversation_id": conversation_id,
                "content": "retry me",
                "client_message_id": client_msg_id,
            }
            alice_ws.send_json(payload)
            ack1 = alice_ws.receive_json()
            assert ack1["data"]["created"] is True
            message_id = ack1["data"]["message"]["id"]
            assert bob_ws.receive_json()["type"] == "message"

            alice_ws.send_json(payload)
            ack2 = alice_ws.receive_json()
            assert ack2["data"]["created"] is False
            assert ack2["data"]["message"]["id"] == message_id

            alice_ws.send_json(
                {
                    "type": "send_message",
                    "conversation_id": conversation_id,
                    "content": "second",
                }
            )
            assert bob_ws.receive_json()["data"]["content"] == "second"


def test_ws_non_member_cannot_send_or_subscribe(ws_client):
    register(ws_client, "alice@example.com", "alice")
    bob = register(ws_client, "bob@example.com", "bob")
    register(ws_client, "carol@example.com", "carol")
    alice_token = login(ws_client, "alice@example.com")
    carol_token = login(ws_client, "carol@example.com")
    conversation_id = create_conversation(ws_client, alice_token, bob["id"])

    with ws_client.websocket_connect(ws_url(carol_token)) as carol_ws:
        carol_ws.send_json(
            {
                "type": "send_message",
                "conversation_id": conversation_id,
                "content": "intruder",
            }
        )
        error = carol_ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "forbidden"

        carol_ws.send_json({"type": "subscribe", "conversation_id": conversation_id})
        error = carol_ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "forbidden"

        carol_ws.send_json({"type": "ping"})
        assert carol_ws.receive_json()["type"] == "pong"


def test_ws_non_subscribed_recipient_gets_unread_event(ws_client):
    alice, bob, alice_token, bob_token, conversation_id = setup_pair(ws_client)

    with ws_client.websocket_connect(ws_url(alice_token)) as alice_ws:
        with ws_client.websocket_connect(ws_url(bob_token)) as bob_ws:
            alice_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert alice_ws.receive_json()["type"] == "messages"

            alice_ws.send_json(
                {
                    "type": "send_message",
                    "conversation_id": conversation_id,
                    "content": "status update!",
                }
            )
            ack = alice_ws.receive_json()
            assert ack["type"] == "ack"
            assert ack["data"]["created"] is True

            event = bob_ws.receive_json()
            assert event["type"] == "new_message"
            assert event["data"]["conversation_id"] == conversation_id
            assert event["data"]["message_id"] == ack["data"]["message"]["id"]
            assert event["data"]["sender_id"] == alice["id"]
            assert event["data"]["preview"] == "status update!"


def test_ws_subscribed_recipient_gets_only_full_message(ws_client):
    alice, bob, alice_token, bob_token, conversation_id = setup_pair(ws_client)

    with ws_client.websocket_connect(ws_url(alice_token)) as alice_ws:
        with ws_client.websocket_connect(ws_url(bob_token)) as bob_ws:
            alice_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert alice_ws.receive_json()["type"] == "messages"
            bob_ws.send_json({"type": "sync", "conversation_id": conversation_id})
            assert bob_ws.receive_json()["type"] == "messages"

            alice_ws.send_json(
                {
                    "type": "send_message",
                    "conversation_id": conversation_id,
                    "content": "hello",
                }
            )
            assert alice_ws.receive_json()["type"] == "ack"

            frame = bob_ws.receive_json()
            assert frame["type"] == "message"
            assert frame["data"]["content"] == "hello"

            bob_ws.send_json({"type": "ping"})
            assert bob_ws.receive_json()["type"] == "pong"


def test_ws_sync_backfills_messages(ws_client):
    alice, bob, alice_token, bob_token, conversation_id = setup_pair(ws_client)
    headers = {"Authorization": f"Bearer {alice_token}"}

    message_ids = []
    for content in ("first", "second"):
        resp = ws_client.post(
            messages_url(conversation_id),
            json={"content": content},
            headers=headers,
        )
        assert resp.status_code == 201
        message_ids.append(resp.json()["id"])
        time.sleep(1.05)

    with ws_client.websocket_connect(ws_url(alice_token)) as alice_ws:
        alice_ws.send_json({"type": "sync", "conversation_id": conversation_id})
        body = alice_ws.receive_json()
        assert body["type"] == "messages"
        assert body["data"]["has_more"] is False
        assert [m["content"] for m in body["data"]["items"]] == [
            "first",
            "second",
        ]

        alice_ws.send_json(
            {
                "type": "sync",
                "conversation_id": conversation_id,
                "after_message_id": message_ids[0],
            }
        )
        body = alice_ws.receive_json()
        assert body["type"] == "messages"
        assert [m["content"] for m in body["data"]["items"]] == ["second"]
        assert body["data"]["has_more"] is False


def test_ws_bad_frames_keep_connection_open(ws_client):
    register(ws_client, "dave@example.com", "dave")
    alice_token = login(ws_client, "dave@example.com")

    with ws_client.websocket_connect(ws_url(alice_token)) as alice_ws:
        alice_ws.send_text("{not valid json")
        error = alice_ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_json"

        alice_ws.send_json({"type": "nope"})
        error = alice_ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "unknown_type"

        alice_ws.send_json({"type": "send_message", "conversation_id": "bad-uuid"})
        error = alice_ws.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid_frame"

        alice_ws.send_json({"type": "ping"})
        assert alice_ws.receive_json()["type"] == "pong"