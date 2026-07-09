from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.middleware.auth import get_current_user
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.security.jwt import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    refresh_token_expires_at,
)
from app.security.password import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)
    name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    preferences: dict = Field(default_factory=dict)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("email must be valid")
        return value.strip().lower()

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    name: str | None
    phone: str | None
    preferences: dict


async def _issue_tokens(session: AsyncSession, user_id: str) -> AuthTokens:
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(refresh_token),
            expires_at=refresh_token_expires_at(),
        )
    )
    await session.commit()
    return AuthTokens(access_token=access_token, refresh_token=refresh_token)


async def _get_valid_refresh_token(session: AsyncSession, token: str) -> RefreshToken:
    payload = decode_token(token, REFRESH_TOKEN_TYPE)
    token_record = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
    )
    if token_record is None or token_record.user_id != payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if token_record.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return token_record


@router.post("/signup", response_model=AuthTokens, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, session: DbSession) -> AuthTokens:
    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
        phone=request.phone,
        preferences=request.preferences,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists"
        ) from exc
    return await _issue_tokens(session, user.id)


@router.post("/login", response_model=AuthTokens)
async def login(request: LoginRequest, session: DbSession) -> AuthTokens:
    username_or_email = request.username.strip().lower()
    user = await session.scalar(
        select(User).where(or_(User.username == username_or_email, User.email == username_or_email))
    )
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return await _issue_tokens(session, user.id)


@router.post("/refresh", response_model=AuthTokens)
async def refresh(request: RefreshRequest, session: DbSession) -> AuthTokens:
    token_record = await _get_valid_refresh_token(session, request.refresh_token)
    token_record.revoked_at = datetime.now(UTC)
    return await _issue_tokens(session, token_record.user_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: LogoutRequest, session: DbSession) -> None:
    token_record = await _get_valid_refresh_token(session, request.refresh_token)
    token_record.revoked_at = datetime.now(UTC)
    await session.commit()


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all(
    current_user: CurrentUser,
    session: DbSession,
) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()


@router.get("/me", response_model=UserProfile)
async def me(current_user: CurrentUser) -> UserProfile:
    return UserProfile(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        name=current_user.name,
        phone=current_user.phone,
        preferences=current_user.preferences,
    )
