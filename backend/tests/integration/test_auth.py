from tests.conftest import get_cookie

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"

USER = {
    "email": "alice@example.com",
    "username": "alice",
    "password": "StrongPass123!",
}


async def register(client, **overrides):
    body = {**USER, **overrides}
    return await client.post(REGISTER_URL, json=body)


async def login(client, **overrides):
    body = {"email": USER["email"], "password": USER["password"], **overrides}
    return await client.post(LOGIN_URL, json=body)


async def test_register_creates_user(client):
    resp = await register(client)
    assert resp.status_code == 201

    data = resp.json()
    assert data["email"] == USER["email"]
    assert data["username"] == USER["username"]
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "hashed_password" not in data


async def test_register_duplicate_email_conflict(client):
    await register(client)
    resp = await register(client, username="another")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Email or username already taken"


async def test_register_duplicate_username_conflict(client):
    await register(client)
    resp = await register(client, email="bob@example.com")
    assert resp.status_code == 409


async def test_register_weak_password_validation(client):
    resp = await register(client, password="short")
    assert resp.status_code == 422


async def test_login_returns_access_token_and_httponly_cookie(client):
    await register(client)
    resp = await login(client)
    assert resp.status_code == 200

    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    set_cookie = resp.headers.get_list("set-cookie")
    cookie_header = next(c for c in set_cookie if c.startswith("refresh_token="))
    assert "HttpOnly" in cookie_header
    assert "Path=/api/v1/auth/refresh" in cookie_header
    assert "Secure" not in cookie_header


async def test_login_wrong_password_unauthorized(client):
    await register(client)
    resp = await login(client, password="WrongPass123!")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


async def test_login_unknown_email_unauthorized(client):
    resp = await login(client)
    assert resp.status_code == 401


async def test_me_without_token_unauthorized(client):
    resp = await client.get(ME_URL)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


async def test_me_with_invalid_token_unauthorized(client):
    resp = await client.get(ME_URL, headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


async def test_me_returns_current_user(client):
    await register(client)
    login_resp = await login(client)
    access_token = login_resp.json()["access_token"]

    resp = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == USER["username"]


async def test_me_returns_404_user_gone(client):
    """Token is structurally valid but user no longer exists in DB."""
    from app.core.security.jwt import create_access_token

    await register(client)
    ghost_token = create_access_token("00000000-0000-0000-0000-000000000000")
    resp = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {ghost_token}"}
    )
    assert resp.status_code == 401


async def test_refresh_rotates_both_tokens(client):
    await register(client)
    login_resp = await login(client)
    old_access = login_resp.json()["access_token"]
    old_refresh = get_cookie(login_resp.headers, "refresh_token")

    resp = await client.post(REFRESH_URL)
    assert resp.status_code == 200

    new_access = resp.json()["access_token"]
    new_refresh = get_cookie(resp.headers, "refresh_token")

    assert new_access != old_access
    assert new_refresh != old_refresh


async def test_refresh_without_cookie_unauthorized(client):
    resp = await client.post(REFRESH_URL)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing refresh token"


async def test_refresh_with_invalid_cookie_unauthorized(client):
    client.cookies.set("refresh_token", "not-a-token", path="/api/v1/auth/refresh")
    resp = await client.post(REFRESH_URL)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or expired refresh token"


async def test_logout_clears_cookie(client):
    await register(client)
    login_resp = await login(client)
    assert get_cookie(login_resp.headers, "refresh_token")

    resp = await client.post(LOGOUT_URL)
    assert resp.status_code == 200

    set_cookie = resp.headers.get_list("set-cookie")
    assert any(c.startswith("refresh_token=") and "Max-Age=0" in c for c in set_cookie)

    resp = await client.post(REFRESH_URL)
    assert resp.status_code == 401