import os
from collections.abc import AsyncGenerator

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-thirty-two-bytes")

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.refresh_token import RefreshToken
from app.security.password import hash_password, verify_password


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await engine.dispose()


def test_argon2id_hash_and_verify_flow() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert "$argon2id$" in password_hash
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


async def test_signup_login_and_me(client: httpx.AsyncClient) -> None:
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "Vishal",
            "email": "vishal@example.com",
            "password": "super-secret-password",
            "name": "Vishal",
        },
    )

    assert signup.status_code == 201
    signup_tokens = signup.json()
    assert signup_tokens["token_type"] == "bearer"
    assert signup_tokens["access_token"]
    assert signup_tokens["refresh_token"]

    duplicate = await client.post(
        "/auth/signup",
        json={
            "username": "vishal",
            "email": "other@example.com",
            "password": "super-secret-password",
        },
    )
    assert duplicate.status_code == 409

    login = await client.post(
        "/auth/login",
        json={"username": "vishal@example.com", "password": "super-secret-password"},
    )
    assert login.status_code == 200

    bad_login = await client.post(
        "/auth/login",
        json={"username": "vishal", "password": "bad-password"},
    )
    assert bad_login.status_code == 401

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "vishal@example.com"

    missing_token = await client.get("/auth/me")
    assert missing_token.status_code == 401


async def test_refresh_rotates_token_and_logout_revokes(client: httpx.AsyncClient) -> None:
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "raghvi",
            "email": "raghvi@example.com",
            "password": "super-secret-password",
        },
    )
    original_refresh_token = signup.json()["refresh_token"]

    rotated = await client.post("/auth/refresh", json={"refresh_token": original_refresh_token})
    assert rotated.status_code == 200
    new_refresh_token = rotated.json()["refresh_token"]
    assert new_refresh_token != original_refresh_token

    reused = await client.post("/auth/refresh", json={"refresh_token": original_refresh_token})
    assert reused.status_code == 401
    assert reused.json()["detail"] == "Token revoked"

    logout = await client.post("/auth/logout", json={"refresh_token": new_refresh_token})
    assert logout.status_code == 204

    after_logout = await client.post("/auth/refresh", json={"refresh_token": new_refresh_token})
    assert after_logout.status_code == 401
    assert after_logout.json()["detail"] == "Token revoked"


async def test_revoke_all_revokes_all_active_refresh_tokens(client: httpx.AsyncClient) -> None:
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "session-owner",
            "email": "session-owner@example.com",
            "password": "super-secret-password",
        },
    )
    login = await client.post(
        "/auth/login",
        json={"username": "session-owner", "password": "super-secret-password"},
    )

    revoke_all = await client.post(
        "/auth/revoke-all",
        headers={"Authorization": f"Bearer {signup.json()['access_token']}"},
    )
    assert revoke_all.status_code == 204

    for token in (signup.json()["refresh_token"], login.json()["refresh_token"]):
        refresh = await client.post("/auth/refresh", json={"refresh_token": token})
        assert refresh.status_code == 401
        assert refresh.json()["detail"] == "Token revoked"


async def test_refresh_tokens_are_stored_hashed(client: httpx.AsyncClient) -> None:
    signup = await client.post(
        "/auth/signup",
        json={
            "username": "hashed-token",
            "email": "hashed-token@example.com",
            "password": "super-secret-password",
        },
    )
    plaintext_refresh_token = signup.json()["refresh_token"]

    override = app.dependency_overrides[get_db_session]
    async for session in override():
        token_record = await session.scalar(select(RefreshToken))
        assert token_record is not None
        assert token_record.token_hash != plaintext_refresh_token
        assert len(token_record.token_hash) == 64
        break
