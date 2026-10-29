from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from seatlock.auth.models import User, UserRole
from seatlock.auth.security import decode_token
from seatlock.auth.service import get_user_by_id
from seatlock.dependencies import DbSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    try:
        user_id = decode_token(token, "access")
    except jwt.InvalidTokenError:
        raise credentials_error() from None

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    async def check_role(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return user

    return check_role


Organizer = Annotated[User, Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))]
