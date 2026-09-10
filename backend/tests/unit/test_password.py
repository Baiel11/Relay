from app.core.security.password import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    hashed = hash_password("super-secret-pass")
    assert hashed != "super-secret-pass"
    assert verify_password("super-secret-pass", hashed)


def test_wrong_password_rejected():
    hashed = hash_password("correct-pass")
    assert not verify_password("wrong-pass", hashed)


def test_hashes_are_salted():
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b