from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 10


def validate_password_strength(password: str) -> str | None:
    """Return an error message if the password is too weak, else None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.lower() == password or password.upper() == password:
        return "Password must mix upper- and lower-case letters."
    if not any(c.isdigit() for c in password):
        return "Password must include a number."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Verified against when the email is unknown, so login timing doesn't reveal which emails exist.
DUMMY_HASH = _hasher.hash("not-a-real-password-0")
