from app.services.users.passwords import hash_password, verify_password


def test_password_round_trip() -> None:
    stored = hash_password("correct-horse")
    assert verify_password("correct-horse", stored)
    assert not verify_password("wrong-horse", stored)
