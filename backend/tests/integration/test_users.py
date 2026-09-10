SEARCH_URL = "/api/v1/users/search"


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
    return resp.json()["access_token"]


async def test_search_requires_auth(client):
    resp = await client.get(SEARCH_URL, params={"q": "alice"})
    assert resp.status_code == 401


async def test_search_returns_matching_users(client):
    await register(client, "alice@example.com", "alice")
    await register(client, "bob@example.com", "bob")
    token = await login(client, "alice@example.com")

    resp = await client.get(
        SEARCH_URL,
        params={"q": "alice"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["username"] == "alice"
    assert "email" not in body["results"][0]


async def test_search_is_case_insensitive(client):
    await register(client, "alice@example.com", "Alice")
    token = await login(client, "alice@example.com")

    resp = await client.get(
        SEARCH_URL,
        params={"q": "ALICE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_search_searches_email_too(client):
    await register(client, "zstyle@example.com", "zstyle")
    token = await login(client, "zstyle@example.com")

    resp = await client.get(
        SEARCH_URL,
        params={"q": "example"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_search_empty_result(client):
    await register(client, "alice@example.com", "alice")
    token = await login(client, "alice@example.com")

    resp = await client.get(
        SEARCH_URL,
        params={"q": "nonexistent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["results"] == []


async def test_search_missing_query_validation(client):
    await register(client, "alice@example.com", "alice")
    token = await login(client, "alice@example.com")

    resp = await client.get(SEARCH_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


async def test_search_pagination(client):
    for i in range(5):
        await register(client, f"user{i}@example.com", f"user{i}")
    token = await login(client, "user0@example.com")

    resp = await client.get(
        SEARCH_URL,
        params={"q": "user", "limit": 2, "offset": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 2
    assert len(body["results"]) == 2
    assert body["total"] == 5


async def test_search_pagination_second_page(client):
    for i in range(5):
        await register(client, f"user{i}@example.com", f"user{i}")
    token = await login(client, "user0@example.com")

    resp = await client.get(
        SEARCH_URL,
        params={"q": "user", "limit": 2, "offset": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["total"] == 5