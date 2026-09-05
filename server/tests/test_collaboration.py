from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from server.domain.auth_models import (
    Conversation,
    InvitationStatus,
    Role,
)
from server.engine.auth import require_role
from server.engine.collaboration import (
    accept_invitation,
    migrate_guest_to_auth,
    send_invitation,
)
from server.engine.persistence.db_adapter import InMemoryAdapter, get_db_provider


@pytest.fixture(autouse=True)
def mock_db():
    # Reset in-memory DB for each test
    db = InMemoryAdapter()
    get_db_provider._instance = db
    return db

@pytest.mark.anyio
async def test_guest_migration(mock_db):
    # Setup Guest Data
    guest_session_id = "guest_123"
    conv = Conversation(
        id="conv_1",
        project_id="temp_proj",
        owner_id=guest_session_id,
        created_at=datetime.utcnow().isoformat()
    )
    await mock_db.create_conversation(conv)
    
    # Migrate
    user = await migrate_guest_to_auth("test@example.com", guest_session_id)
    
    assert user.email == "test@example.com"
    
    # Verify Project Membership
    memberships = mock_db.memberships
    assert len(memberships) == 1
    assert memberships[0].user_id == user.id
    assert memberships[0].role == Role.OWNER
    
    # Verify Conversation Ownership Migration
    migrated_conv = await mock_db.get_conversation("conv_1")
    assert migrated_conv.owner_id == user.id
    assert migrated_conv.project_id == memberships[0].project_id
    
    # Verify Audit
    assert len(mock_db.audits) == 1
    assert mock_db.audits[0].action == "guest_migrated"

@pytest.mark.anyio
async def test_invitation_flow(mock_db):
    owner = await mock_db.create_user("owner@test.com")
    project_id = await mock_db.create_project()
    await mock_db.add_project_member(owner.id, project_id, Role.OWNER)
    
    # Send invite
    inv = await send_invitation(project_id, owner.id, "collab@test.com", Role.RESEARCHER)
    assert inv.status == InvitationStatus.PENDING
    
    # Accept invite (happy path)
    collab = await mock_db.create_user("collab@test.com")
    res = await accept_invitation(inv.token, collab)
    assert res["status"] == "success"
    
    # Verify membership
    m = await mock_db.get_project_membership(collab.id, project_id)
    assert m is not None
    assert m.role == Role.RESEARCHER

@pytest.mark.anyio
async def test_invitation_wrong_user(mock_db):
    owner = await mock_db.create_user("owner@test.com")
    project_id = await mock_db.create_project()
    inv = await send_invitation(project_id, owner.id, "collab@test.com", Role.REVIEWER)
    
    hacker = await mock_db.create_user("hacker@test.com")
    
    with pytest.raises(HTTPException) as exc:
        await accept_invitation(inv.token, hacker)
    assert exc.value.status_code == 403
    assert "different email address" in exc.value.detail

@pytest.mark.anyio
async def test_invitation_expired(mock_db):
    owner = await mock_db.create_user("owner@test.com")
    project_id = await mock_db.create_project()
    inv = await send_invitation(project_id, owner.id, "collab@test.com", Role.REVIEWER)
    
    # Manually expire
    inv.expires_at = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    await mock_db.update_invitation(inv)
    
    collab = await mock_db.create_user("collab@test.com")
    
    with pytest.raises(HTTPException) as exc:
        await accept_invitation(inv.token, collab)
    assert exc.value.status_code == 400
    assert "expired" in exc.value.detail

@pytest.mark.anyio
async def test_rbac_idor_protection(mock_db):
    # Setup
    owner = await mock_db.create_user("owner@test.com")
    viewer = await mock_db.create_user("viewer@test.com")
    hacker = await mock_db.create_user("hacker@test.com")
    
    project_id = await mock_db.create_project()
    await mock_db.add_project_member(owner.id, project_id, Role.OWNER)
    await mock_db.add_project_member(viewer.id, project_id, Role.VIEWER)
    
    # Create Role Checker Dependencies
    require_researcher = require_role(Role.RESEARCHER)
    require_viewer = require_role(Role.VIEWER)
    
    # Viewer cannot access Researcher endpoints
    with pytest.raises(HTTPException) as exc:
        await require_researcher(project_id=project_id, user=viewer)
    assert exc.value.status_code == 403
    assert "Requires RESEARCHER" in exc.value.detail
    
    # Owner CAN access Researcher endpoints
    m = await require_researcher(project_id=project_id, user=owner)
    assert m.role == Role.OWNER
    
    # Hacker cannot access Viewer endpoints
    with pytest.raises(HTTPException) as exc:
        await require_viewer(project_id=project_id, user=hacker)
    assert exc.value.status_code == 403
    assert "Not a member" in exc.value.detail
