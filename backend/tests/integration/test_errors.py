async def test_validation_error_returns_structured_body(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "username": "u", "password": "short"},
    )
    assert resp.status_code == 422

    body = resp.json()
    assert body["detail"] == "Validation error"
    assert isinstance(body["errors"], list)
    assert all("field" in e and "message" in e for e in body["errors"])