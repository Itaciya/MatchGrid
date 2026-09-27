from app.core.security import hash_password, verify_password


def test_hash_password_returns_different_string_than_input():
    hashed = hash_password("mypassword123")
    assert hashed != "mypassword123"


def test_hash_password_produces_bcrypt_format():
    hashed = hash_password("mypassword123")
    assert hashed.startswith("$2b$")


def test_verify_password_succeeds_with_correct_password():
    hashed = hash_password("mypassword123")
    assert verify_password("mypassword123", hashed) is True


def test_verify_password_fails_with_incorrect_password():
    hashed = hash_password("mypassword123")
    assert verify_password("wrongpassword", hashed) is False


def test_same_password_produces_different_hashes():
    hashed1 = hash_password("mypassword123")
    hashed2 = hash_password("mypassword123")
    assert hashed1 != hashed2
    assert verify_password("mypassword123", hashed1) is True
    assert verify_password("mypassword123", hashed2) is True


def test_verify_password_at_72_byte_boundary():
    password = "a" * 72
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True
