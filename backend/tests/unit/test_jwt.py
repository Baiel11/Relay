from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_roundtrip():
    token = create_access_token("user-123")
    payload = decode_token(token, token_type="access")
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token("user-123")
    payload = decode_token(token, token_type="refresh")
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_refresh_token_cannot_be_used_as_access():
    refresh = create_refresh_token("user-123")
    assert decode_token(refresh, token_type="access") is None


def test_access_token_cannot_be_used_as_refresh():
    access = create_access_token("user-123")
    assert decode_token(access, token_type="refresh") is None


def test_tampered_token_is_rejected():
    token = create_access_token("user-123")
    assert decode_token(token[:-2] + "xx", token_type="access") is None


def test_garbage_token_is_rejected():
    assert decode_token("not-a-jwt", token_type="access") is None