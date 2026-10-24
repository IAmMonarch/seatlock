import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from seatlock.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from seatlock.auth.models import User
from seatlock.auth.schemas import UserCreate
from seatlock.auth.security import DUMMY_HASH, hash_password, verify_password


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower()))


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    if await get_user_by_email(db, email=data.email):
        raise EmailAlreadyRegisteredError

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )

    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        # Two sign-ups with the same email at the same moment:
        # the unique constraint catches what the check above missed.
        await db.rollback()
        raise EmailAlreadyRegisteredError from None

    await db.refresh(user)  # load server defaults like created_at
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None:
        verify_password(password, DUMMY_HASH)
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash) or not user.is_active:
        raise InvalidCredentialsError
    return user
