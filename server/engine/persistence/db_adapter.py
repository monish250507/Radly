import os
import uuid
from datetime import datetime

from ...domain.auth_models import (
    AuditEvent,
    Conversation,
    Invitation,
    ProjectMembership,
    Role,
    User,
)


class DatabaseProvider:
    """Abstract interface for Database Persistence."""
    async def get_user_by_email(self, email: str) -> User | None: raise NotImplementedError
    async def create_user(self, email: str) -> User: raise NotImplementedError
    async def create_project(self) -> str: raise NotImplementedError
    async def get_project_membership(self, user_id: str, project_id: str) -> ProjectMembership | None: raise NotImplementedError
    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership: raise NotImplementedError
    async def create_invitation(self, inv: Invitation) -> Invitation: raise NotImplementedError
    async def get_invitation(self, token: str) -> Invitation | None: raise NotImplementedError
    async def update_invitation(self, inv: Invitation): raise NotImplementedError
    async def create_conversation(self, conv: Conversation) -> Conversation: raise NotImplementedError
    async def get_conversation(self, conv_id: str) -> Conversation | None: raise NotImplementedError
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

    async def get_user_by_email(self, email: str) -> User | None:
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

    async def get_project_membership(self, user_id: str, project_id: str) -> ProjectMembership | None:
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

    async def get_invitation(self, token: str) -> Invitation | None:
        return self.invitations.get(token)

    async def update_invitation(self, inv: Invitation):
        self.invitations[inv.token] = inv

    async def create_conversation(self, conv: Conversation) -> Conversation:
        self.conversations[conv.id] = conv
        return conv

    async def get_conversation(self, conv_id: str) -> Conversation | None:
        return self.conversations.get(conv_id)
        
    async def log_audit(self, event: AuditEvent):
        self.audits.append(event)


# ---------------------------------------------------------------------------
# PostgresAdapter — production persistence
# ---------------------------------------------------------------------------
class PostgresAdapter(DatabaseProvider):
    """
    Production database adapter backed by asyncpg / Supabase.

    P0 FIX: This replaces the unconditional InMemoryAdapter. Set DATABASE_URL
    in your environment to activate this path.

    To implement:
      1. pip install asyncpg
      2. Implement each method using asyncpg connection pools.
      3. Run the schema migration in infra/migrations/ against your Postgres DB.

    Until the methods below are implemented, this adapter will raise
    NotImplementedError rather than silently falling back to in-memory state.
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        # TODO: initialise asyncpg pool here:
        # import asyncpg
        # self._pool = await asyncpg.create_pool(database_url)
        raise NotImplementedError(
            "PostgresAdapter is not yet fully implemented. "
            "Either implement the adapter methods or unset DATABASE_URL to use "
            "InMemoryAdapter for local development."
        )

    async def get_user_by_email(self, email: str) -> User | None:
        raise NotImplementedError("Implement with asyncpg: SELECT * FROM users WHERE email=$1")

    async def create_user(self, email: str) -> User:
        raise NotImplementedError("Implement with asyncpg: INSERT INTO users ...")

    async def create_project(self) -> str:
        raise NotImplementedError("Implement with asyncpg: INSERT INTO projects ...")

    async def get_project_membership(self, user_id: str, project_id: str) -> ProjectMembership | None:
        raise NotImplementedError("Implement with asyncpg")

    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership:
        raise NotImplementedError("Implement with asyncpg")

    async def create_invitation(self, inv: Invitation) -> Invitation:
        raise NotImplementedError("Implement with asyncpg")

    async def get_invitation(self, token: str) -> Invitation | None:
        raise NotImplementedError("Implement with asyncpg")

    async def update_invitation(self, inv: Invitation):
        raise NotImplementedError("Implement with asyncpg")

    async def create_conversation(self, conv: Conversation) -> Conversation:
        raise NotImplementedError("Implement with asyncpg")

    async def get_conversation(self, conv_id: str) -> Conversation | None:
        raise NotImplementedError("Implement with asyncpg")

    async def log_audit(self, event: AuditEvent):
        raise NotImplementedError("Implement with asyncpg")


# ---------------------------------------------------------------------------
# Factory — P0 FIX: no longer unconditionally uses InMemoryAdapter
# ---------------------------------------------------------------------------
def get_db_provider() -> DatabaseProvider:
    """
    Return the appropriate database provider.

    - If DATABASE_URL is set → PostgresAdapter (production).
    - Otherwise            → InMemoryAdapter (development only).

    InMemoryAdapter is intentionally NOT used as a silent fallback when
    DATABASE_URL is set but broken. Fail loudly instead.
    """
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # Production path: use persistent Postgres adapter
        if not hasattr(get_db_provider, '_instance') or not isinstance(get_db_provider._instance, PostgresAdapter):
            get_db_provider._instance = PostgresAdapter(database_url)
        return get_db_provider._instance
    else:
        # Development path: in-memory only — data is lost on restart
        if not hasattr(get_db_provider, '_instance') or not isinstance(get_db_provider._instance, InMemoryAdapter):
            import warnings
            warnings.warn(
                "DATABASE_URL is not set. Using InMemoryAdapter — data will not persist across restarts. "
                "Set DATABASE_URL to a Postgres connection string for production.",
                RuntimeWarning,
                stacklevel=2
            )
            get_db_provider._instance = InMemoryAdapter()
        return get_db_provider._instance

