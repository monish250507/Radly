"""
test_auth.py — Production authentication tests (P1-4).
Covers JWT claim verification (issuer, audience, expiry, signature)
and RBAC role boundary enforcement.
"""
import time
import jwt
import pytest
from fastapi import HTTPException

from server.domain.auth_models import Role, User
from server.engine.auth import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_SECRET,
    create_access_token,
    decode_token,
    get_current_user,
    get_current_user_or_guest,
    require_role,
)
from server.engine.persistence.db_adapter import InMemoryAdapter, get_db_provider


def test_valid_token_decoding():
    token = create_access_token({"email": "researcher@example.com", "sub": "usr_1"})
    decoded = decode_token(token)
    assert decoded["email"] == "researcher@example.com"
    assert decoded["iss"] == JWT_ISSUER
    assert decoded["aud"] == JWT_AUDIENCE


def test_expired_token_raises_error():
    expired_payload = {
        "email": "user@example.com",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "exp": int(time.time()) - 3600  # expired 1 hour ago
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)


def test_invalid_issuer_raises_error():
    bad_issuer_payload = {
        "email": "user@example.com",
        "iss": "untrusted_auth_server",
        "aud": JWT_AUDIENCE
    }
    token = jwt.encode(bad_issuer_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidIssuerError):
        decode_token(token)


def test_invalid_audience_raises_error():
    bad_aud_payload = {
        "email": "user@example.com",
        "iss": JWT_ISSUER,
        "aud": "different_app"
    }
    token = jwt.encode(bad_aud_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidAudienceError):
        decode_token(token)


def test_invalid_signature_raises_error():
    token = create_access_token({"email": "user@example.com"})
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(token, secret="completely_wrong_secret_key_32bytes!")


@pytest.mark.asyncio
async def test_get_current_user_or_guest():
    db = InMemoryAdapter()
    user = await db.create_user("alice@lab.org")
    
    # Monkeypatch db provider to test adapter
    original_get_db = get_db_provider
    try:
        import server.engine.auth as auth_mod
        auth_mod.get_db_provider = lambda: db

        # 1. Valid token
        token = create_access_token({"email": "alice@lab.org"})
        found_user = await get_current_user_or_guest(f"Bearer {token}")
        assert found_user is not None
        assert found_user.email == "alice@lab.org"

        # 2. Malformed header
        guest = await get_current_user_or_guest("InvalidHeader")
        assert guest is None

        # 3. Invalid token returns guest None
        guest2 = await get_current_user_or_guest("Bearer bad.token.here")
        assert guest2 is None
    finally:
        import server.engine.auth as auth_mod
        auth_mod.get_db_provider = original_get_db


@pytest.mark.asyncio
async def test_rbac_role_boundaries():
    db = InMemoryAdapter()
    owner = await db.create_user("owner@lab.org")
    viewer = await db.create_user("viewer@lab.org")
    outsider = await db.create_user("outsider@lab.org")

    project_id = await db.create_project()
    await db.add_project_member(owner.id, project_id, Role.OWNER)
    await db.add_project_member(viewer.id, project_id, Role.VIEWER)

    original_get_db = get_db_provider
    try:
        import server.engine.auth as auth_mod
        auth_mod.get_db_provider = lambda: db

        # Viewer trying to perform MAINTAINER action -> 403
        maintainer_check = require_role(Role.MAINTAINER)
        with pytest.raises(HTTPException) as exc:
            await maintainer_check(project_id, user=viewer)
        assert exc.value.status_code == 403
        assert "Requires MAINTAINER privileges" in exc.value.detail

        # Owner has level 5 >= MAINTAINER (4) -> succeeds
        membership = await maintainer_check(project_id, user=owner)
        assert membership.role == Role.OWNER

        # Outsider has no membership -> 403
        viewer_check = require_role(Role.VIEWER)
        with pytest.raises(HTTPException) as exc:
            await viewer_check(project_id, user=outsider)
        assert exc.value.status_code == 403
        assert "Not a member of this project" in exc.value.detail
    finally:
        import server.engine.auth as auth_mod
        auth_mod.get_db_provider = original_get_db
