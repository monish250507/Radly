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
        self._pool = None

    async def _get_pool(self):
        if not self._pool:
            import asyncpg
            self._pool = await asyncpg.create_pool(self.database_url)
            # Ensure schema exists
            async with self._pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY);
                    CREATE TABLE IF NOT EXISTS project_memberships (user_id TEXT, project_id TEXT, role TEXT, created_at TEXT, PRIMARY KEY(user_id, project_id));
                    CREATE TABLE IF NOT EXISTS invitations (token TEXT PRIMARY KEY, project_id TEXT, role TEXT, email TEXT, status TEXT, expires_at TEXT, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, project_id TEXT, owner_id TEXT, visibility TEXT, title TEXT, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, project_id TEXT, actor_id TEXT, action TEXT, details TEXT, created_at TEXT);
                ''')
        return self._pool

    async def get_user_by_email(self, email: str) -> User | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT id, email, created_at FROM users WHERE email=$1", email)
        if row: return User(id=row['id'], email=row['email'], created_at=row['created_at'])
        return None

    async def create_user(self, email: str) -> User:
        pool = await self._get_pool()
        uid = f"usr_{uuid.uuid4().hex[:8]}"
        created_at = datetime.utcnow().isoformat()
        await pool.execute("INSERT INTO users (id, email, created_at) VALUES ($1, $2, $3)", uid, email, created_at)
        return User(id=uid, email=email, created_at=created_at)

    async def create_project(self) -> str:
        pool = await self._get_pool()
        pid = f"proj_{uuid.uuid4().hex[:8]}"
        await pool.execute("INSERT INTO projects (id) VALUES ($1)", pid)
        return pid

    async def get_project_membership(self, user_id: str, project_id: str) -> ProjectMembership | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT user_id, project_id, role, created_at FROM project_memberships WHERE user_id=$1 AND project_id=$2", user_id, project_id)
        if row: return ProjectMembership(user_id=row['user_id'], project_id=row['project_id'], role=Role(row['role']), created_at=row['created_at'])
        return None

    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership:
        pool = await self._get_pool()
        created_at = datetime.utcnow().isoformat()
        await pool.execute("INSERT INTO project_memberships (user_id, project_id, role, created_at) VALUES ($1, $2, $3, $4)", user_id, project_id, role.value, created_at)
        return ProjectMembership(user_id=user_id, project_id=project_id, role=role, created_at=created_at)

    async def create_invitation(self, inv: Invitation) -> Invitation:
        pool = await self._get_pool()
        await pool.execute("INSERT INTO invitations (token, project_id, role, email, status, expires_at, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            inv.token, inv.project_id, inv.role.value, inv.email, inv.status.value, inv.expires_at, inv.created_at)
        return inv

    async def get_invitation(self, token: str) -> Invitation | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT * FROM invitations WHERE token=$1", token)
        if row:
            from ...domain.auth_models import InvitationStatus
            return Invitation(token=row['token'], project_id=row['project_id'], role=Role(row['role']), email=row['email'], status=InvitationStatus(row['status']), expires_at=row['expires_at'], created_at=row['created_at'])
        return None

    async def update_invitation(self, inv: Invitation):
        pool = await self._get_pool()
        await pool.execute("UPDATE invitations SET status=$1 WHERE token=$2", inv.status.value, inv.token)

    async def create_conversation(self, conv: Conversation) -> Conversation:
        pool = await self._get_pool()
        await pool.execute("INSERT INTO conversations (id, project_id, owner_id, visibility, title, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            conv.id, conv.project_id, conv.owner_id, conv.visibility.value, conv.title, conv.created_at)
        return conv

    async def get_conversation(self, conv_id: str) -> Conversation | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT * FROM conversations WHERE id=$1", conv_id)
        if row:
            from ...domain.auth_models import ConversationVisibility
            return Conversation(id=row['id'], project_id=row['project_id'], owner_id=row['owner_id'], visibility=ConversationVisibility(row['visibility']), title=row['title'], created_at=row['created_at'])
        return None

    async def log_audit(self, event: AuditEvent):
        pool = await self._get_pool()
        import json
        await pool.execute("INSERT INTO audit_events (id, project_id, actor_id, action, details, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            event.id, event.project_id, event.actor_id, event.action, json.dumps(event.details), event.created_at)


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

