import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pwdlib import PasswordHash

from seatlock.config import settings

TokenType = Literal["access", "refresh"]

password_hasher = PasswordHash.recommended()

DUMMY_HASH = password_hasher.hash("some-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hasher.verify(password, hashed)


def create_token(user_id: uuid.UUID, token_type: TokenType) -> str:
    now = datetime.now(UTC)
    if token_type == "access":
        expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expires = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {"sub": str(user_id), "type": token_type, "iat": now, "exp": expires}

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    """Returns the user id in the token. Raise jwt.InvalidTokenError if invalid."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub", "type"]},
    )

    if payload["type"] != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    try:
        return uuid.UUID(payload["sub"])
    except ValueError:
        raise jwt.InvalidTokenError("Invalid subject") from None
