import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from ..domain.auth_models import (
    User, ProjectMembership, Role, Invitation, InvitationStatus, AuditEvent, ConversationVisibility
)
from .persistence.db_adapter import get_db_provider

async def migrate_guest_to_auth(email: str, guest_session_id: str) -> User:
    """
    Migrates ephemeral guest data to a persistent User account.
    """
    db = get_db_provider()
    
    # 1. Ensure user exists
    user = await db.get_user_by_email(email)
    if not user:
        user = await db.create_user(email)
        
    # 2. Create Persistent Project from guest session
    project_id = await db.create_project()
    
    # 3. Grant OWNER role to user
    await db.add_project_member(user.id, project_id, Role.OWNER)
    
    # 4. Migrate conversations matching guest_session_id
    # Since we are not doing a full SQL query, we manually iterate the mock db
    if hasattr(db, 'conversations'):
        for conv in db.conversations.values():
            if conv.owner_id == guest_session_id:
                conv.owner_id = user.id
                conv.project_id = project_id
                
    await log_audit_event(project_id, user.id, "guest_migrated", {"guest_session_id": guest_session_id})
    return user

async def send_invitation(project_id: str, inviter_id: str, email: str, role: Role) -> Invitation:
    db = get_db_provider()
    
    # Prevent duplicate pending invites
    if hasattr(db, 'invitations'):
        for inv in db.invitations.values():
            if inv.project_id == project_id and inv.email == email and inv.status == InvitationStatus.PENDING:
                # Revoke old invite
                inv.status = InvitationStatus.REVOKED
                await db.update_invitation(inv)

    token = f"inv_{uuid.uuid4().hex}"
    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
    
    inv = Invitation(
        token=token,
        project_id=project_id,
        role=role,
        email=email,
        status=InvitationStatus.PENDING,
        expires_at=expires_at,
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    
    await db.create_invitation(inv)
    await log_audit_event(project_id, inviter_id, "invitation_sent", {"email": email, "role": role.value})
    return inv

async def accept_invitation(token: str, current_user: User):
    db = get_db_provider()
    inv = await db.get_invitation(token)
    
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
        
    if inv.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Invitation is {inv.status.value}")
        
    if inv.email != current_user.email:
        raise HTTPException(status_code=403, detail="Invitation was sent to a different email address")
        
    if datetime.utcnow().isoformat() > inv.expires_at:
        inv.status = InvitationStatus.EXPIRED
        await db.update_invitation(inv)
        raise HTTPException(status_code=400, detail="Invitation has expired")
        
    # Check if already a member
    existing = await db.get_project_membership(current_user.id, inv.project_id)
    if existing:
        inv.status = InvitationStatus.REVOKED
        await db.update_invitation(inv)
        raise HTTPException(status_code=400, detail="Already a member of this project")
        
    # Grant access
    await db.add_project_member(current_user.id, inv.project_id, inv.role)
    inv.status = InvitationStatus.ACCEPTED
    await db.update_invitation(inv)
    
    await log_audit_event(inv.project_id, current_user.id, "invitation_accepted", {"role": inv.role.value})
    return {"status": "success", "project_id": inv.project_id}

async def log_audit_event(project_id: str, actor_id: str, action: str, details: dict = None):
    db = get_db_provider()
    event = AuditEvent(
        id=f"evt_{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        actor_id=actor_id,
        action=action,
        details=details or {},
        created_at=datetime.utcnow().isoformat() + "Z"
    )
    await db.log_audit(event)
