from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import ExpiredSignatureError, InvalidSignatureError, InvalidTokenError

from app.core.config import get_settings

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def _now() -> datetime:
    return datetime.now(UTC)


def _create_jwt(user_id: str, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    issued_at = _now()
    expires_at = issued_at + expires_delta
    payload: dict[str, Any] = {
        "user_id": user_id,
        "token_type": token_type,
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    return _create_jwt(
        user_id=user_id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    settings = get_settings()
    payload_token = token_urlsafe(32)
    issued_at = _now()
    expires_at = issued_at + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "user_id": user_id,
        "token_type": REFRESH_TOKEN_TYPE,
        "token": payload_token,
        "iat": issued_at,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from exc
    except InvalidSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    if payload.get("token_type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expires_at() -> datetime:
    settings = get_settings()
    return _now() + timedelta(days=settings.refresh_token_expire_days)
