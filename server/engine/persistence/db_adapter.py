from typing import Optional, List
from datetime import datetime
import uuid
import os
from ...domain.auth_models import (
    User, ProjectMembership, Invitation, Conversation, 
    ResearchPR, Comment, Review, AuditEvent, Role, InvitationStatus
)

class DatabaseProvider:
    """Abstract interface for Database Persistence."""
    async def get_user_by_email(self, email: str) -> Optional[User]: raise NotImplementedError
    async def create_user(self, email: str) -> User: raise NotImplementedError
    async def create_project(self) -> str: raise NotImplementedError
    async def get_project_membership(self, user_id: str, project_id: str) -> Optional[ProjectMembership]: raise NotImplementedError
    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership: raise NotImplementedError
    async def create_invitation(self, inv: Invitation) -> Invitation: raise NotImplementedError
    async def get_invitation(self, token: str) -> Optional[Invitation]: raise NotImplementedError
    async def update_invitation(self, inv: Invitation): raise NotImplementedError
    async def create_conversation(self, conv: Conversation) -> Conversation: raise NotImplementedError
    async def get_conversation(self, conv_id: str) -> Optional[Conversation]: raise NotImplementedError
    async def log_audit(self, event: AuditEvent): raise NotImplementedError

class InMemoryAdapter(DatabaseProvider):
    """
    Development fallback for Vercel Dev. 
    In production, this must be swapped for Postgres (e.g. Vercel Postgres / Supabase).
    """
    def __init__(self):
        self.users = {}
        self.memberships = []
        self.invitations = {}
        self.conversations = {}
        self.projects = set()
        self.audits = []

    async def get_user_by_email(self, email: str) -> Optional[User]:
        for u in self.users.values():
            if u.email == email:
                return u
        return None

    async def create_user(self, email: str) -> User:
        uid = f"usr_{uuid.uuid4().hex[:8]}"
        u = User(id=uid, email=email, created_at=datetime.utcnow().isoformat())
        self.users[uid] = u
        return u

    async def create_project(self) -> str:
        pid = f"proj_{uuid.uuid4().hex[:8]}"
        self.projects.add(pid)
        return pid

    async def get_project_membership(self, user_id: str, project_id: str) -> Optional[ProjectMembership]:
        for m in self.memberships:
            if m.user_id == user_id and m.project_id == project_id:
                return m
        return None

    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership:
        m = ProjectMembership(
            user_id=user_id, project_id=project_id, 
            role=role, created_at=datetime.utcnow().isoformat()
        )
        self.memberships.append(m)
        return m

    async def create_invitation(self, inv: Invitation) -> Invitation:
        self.invitations[inv.token] = inv
        return inv

    async def get_invitation(self, token: str) -> Optional[Invitation]:
        return self.invitations.get(token)

    async def update_invitation(self, inv: Invitation):
        self.invitations[inv.token] = inv

    async def create_conversation(self, conv: Conversation) -> Conversation:
        self.conversations[conv.id] = conv
        return conv

    async def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        return self.conversations.get(conv_id)
        
    async def log_audit(self, event: AuditEvent):
        self.audits.append(event)

# Factory logic
def get_db_provider() -> DatabaseProvider:
    # If DATABASE_URL is set, we could return a PostgresAdapter
    # if os.getenv('DATABASE_URL'):
    #     return PostgresAdapter(os.getenv('DATABASE_URL'))
    if not hasattr(get_db_provider, '_instance'):
        get_db_provider._instance = InMemoryAdapter()
    return get_db_provider._instance
