import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

from ...domain.auth_models import (
    AuditEvent,
    Comment,
    Conversation,
    DiffSummary,
    Invitation,
    InvitationStatus,
    PRStatus,
    ProjectMembership,
    ResearchPR,
    Review,
    Role,
    User,
)
from ...domain.models import (
    Evidence,
    ImpactFinding,
    JobRecord,
    JobStatus,
    ResearchAgentRun,
    ResearchProject,
)


class DatabaseProvider:
    """Abstract interface for Database Persistence."""
    # Auth & Users
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

    # Research PRs, Comments & Reviews (P1-1)
    async def create_pr(self, pr: ResearchPR) -> ResearchPR: raise NotImplementedError
    async def get_pr(self, pr_id: str) -> ResearchPR | None: raise NotImplementedError
    async def list_prs(self, project_id: str | None = None) -> list[ResearchPR]: raise NotImplementedError
    async def update_pr(self, pr: ResearchPR): raise NotImplementedError
    async def add_comment(self, comment: Comment) -> Comment: raise NotImplementedError
    async def get_comments(self, pr_id: str) -> list[Comment]: raise NotImplementedError
    async def add_review(self, review: Review) -> Review: raise NotImplementedError
    async def get_reviews(self, pr_id: str) -> list[Review]: raise NotImplementedError

    # Jobs (P1-2)
    async def create_job_record(self, job: JobRecord) -> JobRecord: raise NotImplementedError
    async def get_job_record(self, job_id: str) -> JobRecord | None: raise NotImplementedError
    async def update_job_record(self, job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None): raise NotImplementedError

    # Research / Evidence Domain (P1-3)
    async def save_research_project(self, project: ResearchProject): raise NotImplementedError
    async def get_research_project(self, project_id: str) -> ResearchProject | None: raise NotImplementedError
    async def save_findings(self, version_id: str, findings: list[ImpactFinding]): raise NotImplementedError
    async def get_findings_by_version(self, version_id: str) -> list[ImpactFinding]: raise NotImplementedError
    async def save_evidence(self, version_id: str, evidence: list[Evidence]): raise NotImplementedError
    async def get_evidence_by_version(self, version_id: str) -> list[Evidence]: raise NotImplementedError
    async def save_agent_run(self, run: ResearchAgentRun): raise NotImplementedError
    async def get_agent_run(self, run_id: str) -> ResearchAgentRun | None: raise NotImplementedError


# ---------------------------------------------------------------------------
# InMemoryAdapter — for fast isolated unit testing
# ---------------------------------------------------------------------------
class InMemoryAdapter(DatabaseProvider):
    def __init__(self):
        self.users: dict[str, User] = {}
        self.memberships: list[ProjectMembership] = []
        self.invitations: dict[str, Invitation] = {}
        self.conversations: dict[str, Conversation] = {}
        self.projects: set[str] = set()
        self.audits: list[AuditEvent] = []
        self.prs: dict[str, ResearchPR] = {}
        self.comments: list[Comment] = []
        self.reviews: list[Review] = []
        self.jobs: dict[str, JobRecord] = {}
        self.research_projects: dict[str, ResearchProject] = {}
        self.findings_by_version: dict[str, list[ImpactFinding]] = {}
        self.evidence_by_version: dict[str, list[Evidence]] = {}
        self.agent_runs: dict[str, ResearchAgentRun] = {}

    async def get_user_by_email(self, email: str) -> User | None:
        for u in self.users.values():
            if u.email == email:
                return u
        return None

    async def create_user(self, email: str) -> User:
        uid = f"usr_{uuid.uuid4().hex[:8]}"
        u = User(id=uid, email=email, created_at=_utc_now_iso())
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
            role=role, created_at=_utc_now_iso()
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

    # PRs, comments, reviews
    async def create_pr(self, pr: ResearchPR) -> ResearchPR:
        self.prs[pr.id] = pr
        return pr

    async def get_pr(self, pr_id: str) -> ResearchPR | None:
        return self.prs.get(pr_id)

    async def list_prs(self, project_id: str | None = None) -> list[ResearchPR]:
        if project_id:
            return [p for p in self.prs.values() if p.project_id == project_id]
        return list(self.prs.values())

    async def update_pr(self, pr: ResearchPR):
        self.prs[pr.id] = pr

    async def add_comment(self, comment: Comment) -> Comment:
        self.comments.append(comment)
        return comment

    async def get_comments(self, pr_id: str) -> list[Comment]:
        return [c for c in self.comments if c.pr_id == pr_id]

    async def add_review(self, review: Review) -> Review:
        self.reviews.append(review)
        return review

    async def get_reviews(self, pr_id: str) -> list[Review]:
        return [r for r in self.reviews if r.pr_id == pr_id]

    # Jobs
    async def create_job_record(self, job: JobRecord) -> JobRecord:
        self.jobs[job.jobId] = job
        return job

    async def get_job_record(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)

    async def update_job_record(self, job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None):
        job = self.jobs.get(job_id)
        if job:
            job.status = status
            job.updatedAt = _utc_now_iso()
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            if progress is not None:
                if job.result is None:
                    job.result = {}
                if isinstance(job.result, dict):
                    job.result['_progress'] = progress

    # Evidence Domain
    async def save_research_project(self, project: ResearchProject):
        self.research_projects[project.projectId] = project

    async def get_research_project(self, project_id: str) -> ResearchProject | None:
        return self.research_projects.get(project_id)

    async def save_findings(self, version_id: str, findings: list[ImpactFinding]):
        self.findings_by_version[version_id] = findings

    async def get_findings_by_version(self, version_id: str) -> list[ImpactFinding]:
        return self.findings_by_version.get(version_id, [])

    async def save_evidence(self, version_id: str, evidence: list[Evidence]):
        self.evidence_by_version[version_id] = evidence

    async def get_evidence_by_version(self, version_id: str) -> list[Evidence]:
        return self.evidence_by_version.get(version_id, [])

    async def save_agent_run(self, run: ResearchAgentRun):
        self.agent_runs[run.run_id] = run

    async def get_agent_run(self, run_id: str) -> ResearchAgentRun | None:
        return self.agent_runs.get(run_id)


# ---------------------------------------------------------------------------
# SqliteAdapter — Durable local SQLite persistence (P1-1, P1-2, P1-3)
# ---------------------------------------------------------------------------
class SqliteAdapter(DatabaseProvider):
    """
    Durable SQLite database adapter for local development and standalone execution.
    Persists data across server restarts without external daemon dependencies.
    """
    def __init__(self, db_path: str = "./rbr_local.db"):
        # Strip sqlite URI prefix if given e.g. sqlite+pysqlite:///./rbr_local.db
        if ":///" in db_path:
            db_path = db_path.split(":///")[-1]
        elif "://" in db_path:
            db_path = db_path.split("://")[-1]
        self.db_path = os.path.abspath(db_path)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE, created_at TEXT);
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS project_memberships (user_id TEXT, project_id TEXT, role TEXT, created_at TEXT, PRIMARY KEY(user_id, project_id));
                CREATE TABLE IF NOT EXISTS invitations (token TEXT PRIMARY KEY, project_id TEXT, role TEXT, email TEXT, status TEXT, expires_at TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, project_id TEXT, owner_id TEXT, visibility TEXT, title TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, project_id TEXT, actor_id TEXT, action TEXT, details TEXT, created_at TEXT);
                
                CREATE TABLE IF NOT EXISTS research_prs (
                    id TEXT PRIMARY KEY, project_id TEXT, author_id TEXT, base_version_id TEXT,
                    proposed_version_id TEXT, status TEXT, analysis_status TEXT, analysis_result TEXT,
                    analysis_error TEXT, diff_summary TEXT, base_file_count INTEGER, proposed_file_count INTEGER,
                    created_at TEXT, updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS pr_comments (
                    id TEXT PRIMARY KEY, pr_id TEXT, author_id TEXT, content TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS pr_reviews (
                    id TEXT PRIMARY KEY, pr_id TEXT, reviewer_id TEXT, verdict TEXT, content TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, status TEXT, created_at TEXT, updated_at TEXT, result TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS research_projects (
                    project_id TEXT PRIMARY KEY, payload TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS impact_findings (
                    finding_id TEXT PRIMARY KEY, version_id TEXT, payload TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS evidence_records (
                    evidence_id TEXT PRIMARY KEY, version_id TEXT, payload TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY, project_id TEXT, payload TEXT, updated_at TEXT
                );
            ''')

    async def get_user_by_email(self, email: str) -> User | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, email, created_at FROM users WHERE email=?", (email,)).fetchone()
            if row:
                return User(id=row['id'], email=row['email'], created_at=row['created_at'])
            return None

    async def create_user(self, email: str) -> User:
        uid = f"usr_{uuid.uuid4().hex[:8]}"
        created_at = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO users (id, email, created_at) VALUES (?, ?, ?)", (uid, email, created_at))
        return User(id=uid, email=email, created_at=created_at)

    async def create_project(self) -> str:
        pid = f"proj_{uuid.uuid4().hex[:8]}"
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO projects (id) VALUES (?)", (pid,))
        return pid

    async def get_project_membership(self, user_id: str, project_id: str) -> ProjectMembership | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT user_id, project_id, role, created_at FROM project_memberships WHERE user_id=? AND project_id=?", (user_id, project_id)).fetchone()
            if row:
                return ProjectMembership(user_id=row['user_id'], project_id=row['project_id'], role=Role(row['role']), created_at=row['created_at'])
            return None

    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership:
        created_at = _utc_now_iso()
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO project_memberships (user_id, project_id, role, created_at) VALUES (?, ?, ?, ?)",
                         (user_id, project_id, role.value, created_at))
        return ProjectMembership(user_id=user_id, project_id=project_id, role=role, created_at=created_at)

    async def create_invitation(self, inv: Invitation) -> Invitation:
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO invitations (token, project_id, role, email, status, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (inv.token, inv.project_id, inv.role.value, inv.email, inv.status.value, inv.expires_at, inv.created_at))
        return inv

    async def get_invitation(self, token: str) -> Invitation | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM invitations WHERE token=?", (token,)).fetchone()
            if row:
                return Invitation(
                    token=row['token'], project_id=row['project_id'], role=Role(row['role']),
                    email=row['email'], status=InvitationStatus(row['status']),
                    expires_at=row['expires_at'], created_at=row['created_at']
                )
            return None

    async def update_invitation(self, inv: Invitation):
        with self._get_conn() as conn:
            conn.execute("UPDATE invitations SET status=? WHERE token=?", (inv.status.value, inv.token))

    async def create_conversation(self, conv: Conversation) -> Conversation:
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO conversations (id, project_id, owner_id, visibility, title, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (conv.id, conv.project_id, conv.owner_id, conv.visibility.value, conv.title, conv.created_at))
        return conv

    async def get_conversation(self, conv_id: str) -> Conversation | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
            if row:
                from ...domain.auth_models import ConversationVisibility
                return Conversation(
                    id=row['id'], project_id=row['project_id'], owner_id=row['owner_id'],
                    visibility=ConversationVisibility(row['visibility']), title=row['title'],
                    created_at=row['created_at']
                )
            return None

    async def log_audit(self, event: AuditEvent):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO audit_events (id, project_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (event.id, event.project_id, event.actor_id, event.action, json.dumps(event.details), event.created_at))

    # PR Management
    async def create_pr(self, pr: ResearchPR) -> ResearchPR:
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO research_prs (
                    id, project_id, author_id, base_version_id, proposed_version_id,
                    status, analysis_status, analysis_result, analysis_error, diff_summary,
                    base_file_count, proposed_file_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pr.id, pr.project_id, pr.author_id, pr.base_version_id, pr.proposed_version_id,
                pr.status.value, pr.analysis_status,
                json.dumps(pr.analysis_result) if pr.analysis_result is not None else None,
                pr.analysis_error,
                json.dumps(pr.diff_summary.model_dump() if hasattr(pr.diff_summary, "model_dump") else pr.diff_summary) if pr.diff_summary is not None else None,
                pr.base_file_count, pr.proposed_file_count, pr.created_at, pr.updated_at
            ))
        return pr

    async def get_pr(self, pr_id: str) -> ResearchPR | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM research_prs WHERE id=?", (pr_id,)).fetchone()
            if row:
                diff_summary = json.loads(row['diff_summary']) if row['diff_summary'] else None
                analysis_result = json.loads(row['analysis_result']) if row['analysis_result'] else None
                return ResearchPR(
                    id=row['id'], project_id=row['project_id'], author_id=row['author_id'],
                    base_version_id=row['base_version_id'], proposed_version_id=row['proposed_version_id'],
                    status=PRStatus(row['status']), analysis_status=row['analysis_status'],
                    analysis_result=analysis_result, analysis_error=row['analysis_error'],
                    diff_summary=diff_summary, base_file_count=row['base_file_count'],
                    proposed_file_count=row['proposed_file_count'], created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None

    async def list_prs(self, project_id: str | None = None) -> list[ResearchPR]:
        with self._get_conn() as conn:
            if project_id:
                rows = conn.execute("SELECT * FROM research_prs WHERE project_id=? ORDER BY created_at DESC", (project_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM research_prs ORDER BY created_at DESC").fetchall()
            prs = []
            for row in rows:
                diff_summary = json.loads(row['diff_summary']) if row['diff_summary'] else None
                analysis_result = json.loads(row['analysis_result']) if row['analysis_result'] else None
                prs.append(ResearchPR(
                    id=row['id'], project_id=row['project_id'], author_id=row['author_id'],
                    base_version_id=row['base_version_id'], proposed_version_id=row['proposed_version_id'],
                    status=PRStatus(row['status']), analysis_status=row['analysis_status'],
                    analysis_result=analysis_result, analysis_error=row['analysis_error'],
                    diff_summary=diff_summary, base_file_count=row['base_file_count'],
                    proposed_file_count=row['proposed_file_count'], created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            return prs

    async def update_pr(self, pr: ResearchPR):
        await self.create_pr(pr)

    async def add_comment(self, comment: Comment) -> Comment:
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO pr_comments (id, pr_id, author_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
                         (comment.id, comment.pr_id, comment.author_id, comment.content, comment.created_at))
        return comment

    async def get_comments(self, pr_id: str) -> list[Comment]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM pr_comments WHERE pr_id=? ORDER BY created_at ASC", (pr_id,)).fetchall()
            return [Comment(id=r['id'], pr_id=r['pr_id'], author_id=r['author_id'], content=r['content'], created_at=r['created_at']) for r in rows]

    async def add_review(self, review: Review) -> Review:
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO pr_reviews (id, pr_id, reviewer_id, verdict, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (review.id, review.pr_id, review.reviewer_id, review.verdict.value, review.content, review.created_at))
        return review

    async def get_reviews(self, pr_id: str) -> list[Review]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM pr_reviews WHERE pr_id=? ORDER BY created_at ASC", (pr_id,)).fetchall()
            return [Review(id=r['id'], pr_id=r['pr_id'], reviewer_id=r['reviewer_id'], verdict=PRStatus(r['verdict']), content=r['content'], created_at=r['created_at']) for r in rows]

    # Jobs
    async def create_job_record(self, job: JobRecord) -> JobRecord:
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO jobs (job_id, status, created_at, updated_at, result, error) VALUES (?, ?, ?, ?, ?, ?)",
                         (job.jobId, job.status.value, job.createdAt, job.updatedAt, json.dumps(job.result) if job.result else None, job.error))
        return job

    async def get_job_record(self, job_id: str) -> JobRecord | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row:
                result = json.loads(row['result']) if row['result'] else None
                return JobRecord(
                    jobId=row['job_id'], status=JobStatus(row['status']),
                    createdAt=row['created_at'], updatedAt=row['updated_at'],
                    result=result, error=row['error']
                )
            return None

    async def update_job_record(self, job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None):
        with self._get_conn() as conn:
            row = conn.execute("SELECT result FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            current_result = json.loads(row['result']) if row and row['result'] else {}
            if result is not None:
                current_result = result
            if progress is not None:
                if not isinstance(current_result, dict):
                    current_result = {}
                current_result['_progress'] = progress

            updated_at = _utc_now_iso()
            conn.execute("UPDATE jobs SET status=?, updated_at=?, result=?, error=? WHERE job_id=?",
                         (status.value, updated_at, json.dumps(current_result) if current_result else None, error, job_id))

    # Evidence & Domain
    async def save_research_project(self, project: ResearchProject):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO research_projects (project_id, payload, created_at) VALUES (?, ?, ?)",
                         (project.projectId, json.dumps(project.model_dump()), project.createdAt))

    async def get_research_project(self, project_id: str) -> ResearchProject | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT payload FROM research_projects WHERE project_id=?", (project_id,)).fetchone()
            if row and row['payload']:
                data = json.loads(row['payload'])
                return ResearchProject.model_validate(data)
            return None

    async def save_findings(self, version_id: str, findings: list[ImpactFinding]):
        with self._get_conn() as conn:
            for f in findings:
                conn.execute("INSERT OR REPLACE INTO impact_findings (finding_id, version_id, payload, created_at) VALUES (?, ?, ?, ?)",
                             (f.findingId, version_id, json.dumps(f.model_dump()), f.createdAt))

    async def get_findings_by_version(self, version_id: str) -> list[ImpactFinding]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT payload FROM impact_findings WHERE version_id=?", (version_id,)).fetchall()
            return [ImpactFinding.model_validate(json.loads(r['payload'])) for r in rows if r['payload']]

    async def save_evidence(self, version_id: str, evidence: list[Evidence]):
        with self._get_conn() as conn:
            for e in evidence:
                conn.execute("INSERT OR REPLACE INTO evidence_records (evidence_id, version_id, payload, created_at) VALUES (?, ?, ?, ?)",
                             (e.evidenceId, version_id, json.dumps(e.model_dump()), e.createdAt))

    async def get_evidence_by_version(self, version_id: str) -> list[Evidence]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT payload FROM evidence_records WHERE version_id=?", (version_id,)).fetchall()
            return [Evidence.model_validate(json.loads(r['payload'])) for r in rows if r['payload']]

    async def save_agent_run(self, run: ResearchAgentRun):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO agent_runs (run_id, project_id, payload, updated_at) VALUES (?, ?, ?, ?)",
                         (run.run_id, run.project_id, json.dumps(run.model_dump()), run.updated_at))

    async def get_agent_run(self, run_id: str) -> ResearchAgentRun | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT payload FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
            if row and row['payload']:
                return ResearchAgentRun.model_validate(json.loads(row['payload']))
            return None


# ---------------------------------------------------------------------------
# PostgresAdapter — production persistence
# ---------------------------------------------------------------------------
class PostgresAdapter(DatabaseProvider):
    """
    Production database adapter backed by asyncpg / Supabase / Vercel Postgres.
    """
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None

    async def _get_pool(self):
        if not self._pool:
            import asyncpg
            self._pool = await asyncpg.create_pool(self.database_url)
            async with self._pool.acquire() as conn:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY);
                    CREATE TABLE IF NOT EXISTS project_memberships (user_id TEXT, project_id TEXT, role TEXT, created_at TEXT, PRIMARY KEY(user_id, project_id));
                    CREATE TABLE IF NOT EXISTS invitations (token TEXT PRIMARY KEY, project_id TEXT, role TEXT, email TEXT, status TEXT, expires_at TEXT, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, project_id TEXT, owner_id TEXT, visibility TEXT, title TEXT, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, project_id TEXT, actor_id TEXT, action TEXT, details TEXT, created_at TEXT);
                    CREATE TABLE IF NOT EXISTS research_prs (
                        id TEXT PRIMARY KEY, project_id TEXT, author_id TEXT, base_version_id TEXT,
                        proposed_version_id TEXT, status TEXT, analysis_status TEXT, analysis_result TEXT,
                        analysis_error TEXT, diff_summary TEXT, base_file_count INTEGER, proposed_file_count INTEGER,
                        created_at TEXT, updated_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS pr_comments (
                        id TEXT PRIMARY KEY, pr_id TEXT, author_id TEXT, content TEXT, created_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS pr_reviews (
                        id TEXT PRIMARY KEY, pr_id TEXT, reviewer_id TEXT, verdict TEXT, content TEXT, created_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY, status TEXT, created_at TEXT, updated_at TEXT, result TEXT, error TEXT
                    );
                    CREATE TABLE IF NOT EXISTS research_projects (
                        project_id TEXT PRIMARY KEY, payload TEXT, created_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS impact_findings (
                        finding_id TEXT PRIMARY KEY, version_id TEXT, payload TEXT, created_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS evidence_records (
                        evidence_id TEXT PRIMARY KEY, version_id TEXT, payload TEXT, created_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS agent_runs (
                        run_id TEXT PRIMARY KEY, project_id TEXT, payload TEXT, updated_at TEXT
                    );
                ''')
        return self._pool

    async def get_user_by_email(self, email: str) -> User | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT id, email, created_at FROM users WHERE email=$1", email)
        if row:
            return User(id=row['id'], email=row['email'], created_at=row['created_at'])
        return None

    async def create_user(self, email: str) -> User:
        pool = await self._get_pool()
        uid = f"usr_{uuid.uuid4().hex[:8]}"
        created_at = _utc_now_iso()
        await pool.execute("INSERT INTO users (id, email, created_at) VALUES ($1, $2, $3) ON CONFLICT (email) DO NOTHING", uid, email, created_at)
        return User(id=uid, email=email, created_at=created_at)

    async def create_project(self) -> str:
        pool = await self._get_pool()
        pid = f"proj_{uuid.uuid4().hex[:8]}"
        await pool.execute("INSERT INTO projects (id) VALUES ($1)", pid)
        return pid

    async def get_project_membership(self, user_id: str, project_id: str) -> ProjectMembership | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT user_id, project_id, role, created_at FROM project_memberships WHERE user_id=$1 AND project_id=$2", user_id, project_id)
        if row:
            return ProjectMembership(user_id=row['user_id'], project_id=row['project_id'], role=Role(row['role']), created_at=row['created_at'])
        return None

    async def add_project_member(self, user_id: str, project_id: str, role: Role) -> ProjectMembership:
        pool = await self._get_pool()
        created_at = _utc_now_iso()
        await pool.execute("INSERT INTO project_memberships (user_id, project_id, role, created_at) VALUES ($1, $2, $3, $4) ON CONFLICT (user_id, project_id) DO UPDATE SET role=$3", user_id, project_id, role.value, created_at)
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
        await pool.execute("INSERT INTO audit_events (id, project_id, actor_id, action, details, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            event.id, event.project_id, event.actor_id, event.action, json.dumps(event.details), event.created_at)

    async def create_pr(self, pr: ResearchPR) -> ResearchPR:
        pool = await self._get_pool()
        diff_str = json.dumps(pr.diff_summary.model_dump() if hasattr(pr.diff_summary, "model_dump") else pr.diff_summary) if pr.diff_summary is not None else None
        res_str = json.dumps(pr.analysis_result) if pr.analysis_result is not None else None
        await pool.execute('''
            INSERT INTO research_prs (
                id, project_id, author_id, base_version_id, proposed_version_id,
                status, analysis_status, analysis_result, analysis_error, diff_summary,
                base_file_count, proposed_file_count, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (id) DO UPDATE SET
                status=$6, analysis_status=$7, analysis_result=$8, analysis_error=$9,
                diff_summary=$10, updated_at=$14
        ''', pr.id, pr.project_id, pr.author_id, pr.base_version_id, pr.proposed_version_id,
             pr.status.value, pr.analysis_status, res_str, pr.analysis_error, diff_str,
             pr.base_file_count, pr.proposed_file_count, pr.created_at, pr.updated_at)
        return pr

    async def get_pr(self, pr_id: str) -> ResearchPR | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT * FROM research_prs WHERE id=$1", pr_id)
        if row:
            diff_summary = json.loads(row['diff_summary']) if row['diff_summary'] else None
            analysis_result = json.loads(row['analysis_result']) if row['analysis_result'] else None
            return ResearchPR(
                id=row['id'], project_id=row['project_id'], author_id=row['author_id'],
                base_version_id=row['base_version_id'], proposed_version_id=row['proposed_version_id'],
                status=PRStatus(row['status']), analysis_status=row['analysis_status'],
                analysis_result=analysis_result, analysis_error=row['analysis_error'],
                diff_summary=diff_summary, base_file_count=row['base_file_count'],
                proposed_file_count=row['proposed_file_count'], created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        return None

    async def list_prs(self, project_id: str | None = None) -> list[ResearchPR]:
        pool = await self._get_pool()
        if project_id:
            rows = await pool.fetch("SELECT * FROM research_prs WHERE project_id=$1 ORDER BY created_at DESC", project_id)
        else:
            rows = await pool.fetch("SELECT * FROM research_prs ORDER BY created_at DESC")
        prs = []
        for row in rows:
            diff_summary = json.loads(row['diff_summary']) if row['diff_summary'] else None
            analysis_result = json.loads(row['analysis_result']) if row['analysis_result'] else None
            prs.append(ResearchPR(
                id=row['id'], project_id=row['project_id'], author_id=row['author_id'],
                base_version_id=row['base_version_id'], proposed_version_id=row['proposed_version_id'],
                status=PRStatus(row['status']), analysis_status=row['analysis_status'],
                analysis_result=analysis_result, analysis_error=row['analysis_error'],
                diff_summary=diff_summary, base_file_count=row['base_file_count'],
                proposed_file_count=row['proposed_file_count'], created_at=row['created_at'],
                updated_at=row['updated_at']
            ))
        return prs

    async def update_pr(self, pr: ResearchPR):
        await self.create_pr(pr)

    async def add_comment(self, comment: Comment) -> Comment:
        pool = await self._get_pool()
        await pool.execute("INSERT INTO pr_comments (id, pr_id, author_id, content, created_at) VALUES ($1, $2, $3, $4, $5)",
                           comment.id, comment.pr_id, comment.author_id, comment.content, comment.created_at)
        return comment

    async def get_comments(self, pr_id: str) -> list[Comment]:
        pool = await self._get_pool()
        rows = await pool.fetch("SELECT * FROM pr_comments WHERE pr_id=$1 ORDER BY created_at ASC", pr_id)
        return [Comment(id=r['id'], pr_id=r['pr_id'], author_id=r['author_id'], content=r['content'], created_at=r['created_at']) for r in rows]

    async def add_review(self, review: Review) -> Review:
        pool = await self._get_pool()
        await pool.execute("INSERT INTO pr_reviews (id, pr_id, reviewer_id, verdict, content, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                           review.id, review.pr_id, review.reviewer_id, review.verdict.value, review.content, review.created_at)
        return review

    async def get_reviews(self, pr_id: str) -> list[Review]:
        pool = await self._get_pool()
        rows = await pool.fetch("SELECT * FROM pr_reviews WHERE pr_id=$1 ORDER BY created_at ASC", pr_id)
        return [Review(id=r['id'], pr_id=r['pr_id'], reviewer_id=r['reviewer_id'], verdict=PRStatus(r['verdict']), content=r['content'], created_at=r['created_at']) for r in rows]

    async def create_job_record(self, job: JobRecord) -> JobRecord:
        pool = await self._get_pool()
        await pool.execute("INSERT INTO jobs (job_id, status, created_at, updated_at, result, error) VALUES ($1, $2, $3, $4, $5, $6)",
                           job.jobId, job.status.value, job.createdAt, job.updatedAt, json.dumps(job.result) if job.result else None, job.error)
        return job

    async def get_job_record(self, job_id: str) -> JobRecord | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT * FROM jobs WHERE job_id=$1", job_id)
        if row:
            result = json.loads(row['result']) if row['result'] else None
            return JobRecord(
                jobId=row['job_id'], status=JobStatus(row['status']),
                createdAt=row['created_at'], updatedAt=row['updated_at'],
                result=result, error=row['error']
            )
        return None

    async def update_job_record(self, job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None):
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT result FROM jobs WHERE job_id=$1", job_id)
        current_result = json.loads(row['result']) if row and row['result'] else {}
        if result is not None:
            current_result = result
        if progress is not None:
            if not isinstance(current_result, dict):
                current_result = {}
            current_result['_progress'] = progress

        updated_at = _utc_now_iso()
        await pool.execute("UPDATE jobs SET status=$1, updated_at=$2, result=$3, error=$4 WHERE job_id=$5",
                           status.value, updated_at, json.dumps(current_result) if current_result else None, error, job_id)

    async def save_research_project(self, project: ResearchProject):
        pool = await self._get_pool()
        await pool.execute("INSERT INTO research_projects (project_id, payload, created_at) VALUES ($1, $2, $3) ON CONFLICT (project_id) DO UPDATE SET payload=$2",
                           project.projectId, json.dumps(project.model_dump()), project.createdAt)

    async def get_research_project(self, project_id: str) -> ResearchProject | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT payload FROM research_projects WHERE project_id=$1", project_id)
        if row and row['payload']:
            return ResearchProject.model_validate(json.loads(row['payload']))
        return None

    async def save_findings(self, version_id: str, findings: list[ImpactFinding]):
        pool = await self._get_pool()
        for f in findings:
            await pool.execute("INSERT INTO impact_findings (finding_id, version_id, payload, created_at) VALUES ($1, $2, $3, $4) ON CONFLICT (finding_id) DO UPDATE SET payload=$3",
                               f.findingId, version_id, json.dumps(f.model_dump()), f.createdAt)

    async def get_findings_by_version(self, version_id: str) -> list[ImpactFinding]:
        pool = await self._get_pool()
        rows = await pool.fetch("SELECT payload FROM impact_findings WHERE version_id=$1", version_id)
        return [ImpactFinding.model_validate(json.loads(r['payload'])) for r in rows if r['payload']]

    async def save_evidence(self, version_id: str, evidence: list[Evidence]):
        pool = await self._get_pool()
        for e in evidence:
            await pool.execute("INSERT INTO evidence_records (evidence_id, version_id, payload, created_at) VALUES ($1, $2, $3, $4) ON CONFLICT (evidence_id) DO UPDATE SET payload=$3",
                               e.evidenceId, version_id, json.dumps(e.model_dump()), e.createdAt)

    async def get_evidence_by_version(self, version_id: str) -> list[Evidence]:
        pool = await self._get_pool()
        rows = await pool.fetch("SELECT payload FROM evidence_records WHERE version_id=$1", version_id)
        return [Evidence.model_validate(json.loads(r['payload'])) for r in rows if r['payload']]

    async def save_agent_run(self, run: ResearchAgentRun):
        pool = await self._get_pool()
        await pool.execute("INSERT INTO agent_runs (run_id, project_id, payload, updated_at) VALUES ($1, $2, $3, $4) ON CONFLICT (run_id) DO UPDATE SET payload=$3, updated_at=$4",
                           run.run_id, run.project_id, json.dumps(run.model_dump()), run.updated_at)

    async def get_agent_run(self, run_id: str) -> ResearchAgentRun | None:
        pool = await self._get_pool()
        row = await pool.fetchrow("SELECT payload FROM agent_runs WHERE run_id=$1", run_id)
        if row and row['payload']:
            return ResearchAgentRun.model_validate(json.loads(row['payload']))
        return None


# ---------------------------------------------------------------------------
# Factory — selects appropriate persistent or in-memory provider
# ---------------------------------------------------------------------------
def get_db_provider() -> DatabaseProvider:
    """
    Return the appropriate database provider:
    - If an instance is already registered (e.g. mock_db in tests) → return it.
    - If FORCE_IN_MEMORY is set → InMemoryAdapter (for test isolation).
    - If DATABASE_URL is set and starts with 'postgres' → PostgresAdapter (production).
    - Otherwise → SqliteAdapter with RBR_DB_URL or ./rbr_local.db (durable local dev).
    """
    if hasattr(get_db_provider, '_instance') and get_db_provider._instance is not None:
        return get_db_provider._instance

    if os.getenv('FORCE_IN_MEMORY') == '1':
        get_db_provider._instance = InMemoryAdapter()
        return get_db_provider._instance

    database_url = os.getenv('DATABASE_URL', '')
    if database_url.startswith('postgres') or database_url.startswith('postgresql'):
        get_db_provider._instance = PostgresAdapter(database_url)
        return get_db_provider._instance

    # Default to durable SQLite adapter
    db_path = os.getenv('RBR_DB_URL', './rbr_local.db')
    get_db_provider._instance = SqliteAdapter(db_path)
    return get_db_provider._instance
