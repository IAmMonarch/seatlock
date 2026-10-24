from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from seatlock.auth.dependencies import CurrentUser, credentials_error
from seatlock.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)
from seatlock.auth.models import User
from seatlock.auth.schemas import RefreshRequest, TokenPair, UserCreate, UserOut
from seatlock.auth.security import create_token, decode_token
from seatlock.auth.service import authenticate, get_user_by_id, register_user
from seatlock.dependencies import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])


def issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(user_id=user.id, token_type="access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DbSession) -> User:
    try:
        return await register_user(db, data)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from None


@router.post("/login")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession
) -> TokenPair:
    try:
        user = await authenticate(db, email=form.username, password=form.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return issue_tokens(user)


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        user_id = decode_token(token=body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise credentials_error() from None

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_error()
    return issue_tokens(user)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
