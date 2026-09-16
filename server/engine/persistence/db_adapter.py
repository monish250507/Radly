import json
import os
import uuid
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
    """Abstract interface for Persistence."""
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

    # Research PRs, Comments & Reviews
    async def create_pr(self, pr: ResearchPR) -> ResearchPR: raise NotImplementedError
    async def get_pr(self, pr_id: str) -> ResearchPR | None: raise NotImplementedError
    async def list_prs(self, project_id: str | None = None) -> list[ResearchPR]: raise NotImplementedError
    async def update_pr(self, pr: ResearchPR): raise NotImplementedError
    async def add_comment(self, comment: Comment) -> Comment: raise NotImplementedError
    async def get_comments(self, pr_id: str) -> list[Comment]: raise NotImplementedError
    async def add_review(self, review: Review) -> Review: raise NotImplementedError
    async def get_reviews(self, pr_id: str) -> list[Review]: raise NotImplementedError

    # Jobs
    async def create_job_record(self, job: JobRecord) -> JobRecord: raise NotImplementedError
    async def get_job_record(self, job_id: str) -> JobRecord | None: raise NotImplementedError
    async def update_job_record(self, job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None): raise NotImplementedError

    # Research / Evidence Domain
    async def save_research_project(self, project: ResearchProject): raise NotImplementedError
    async def get_research_project(self, project_id: str) -> ResearchProject | None: raise NotImplementedError
    async def save_findings(self, version_id: str, findings: list[ImpactFinding]): raise NotImplementedError
    async def get_findings_by_version(self, version_id: str) -> list[ImpactFinding]: raise NotImplementedError
    async def save_evidence(self, version_id: str, evidence: list[Evidence]): raise NotImplementedError
    async def get_evidence_by_version(self, version_id: str) -> list[Evidence]: raise NotImplementedError
    async def save_agent_run(self, run: ResearchAgentRun): raise NotImplementedError
    async def get_agent_run(self, run_id: str) -> ResearchAgentRun | None: raise NotImplementedError


# ---------------------------------------------------------------------------
# InMemoryAdapter — Pure in-memory zero-dependency adapter
# ---------------------------------------------------------------------------
class InMemoryAdapter(DatabaseProvider):
    """
    Stateless, fast in-memory persistence provider.
    Requires no external database, SQLite files, migrations, or database credentials.
    Ideal for cloud deployments (Render, Hugging Face Spaces, Vercel, Docker).
    """
    def __init__(self, *args, **kwargs):
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


# Backward compatibility aliases so legacy references work seamlessly
SqliteAdapter = InMemoryAdapter
PostgresAdapter = InMemoryAdapter


# ---------------------------------------------------------------------------
# Factory — returns the global in-memory provider
# ---------------------------------------------------------------------------
_global_db_instance: InMemoryAdapter | None = None

def get_db_provider() -> InMemoryAdapter:
    """
    Return the in-memory database provider.
    Zero configuration, zero external dependencies, 100% cloud-ready.
    """
    global _global_db_instance
    if hasattr(get_db_provider, '_instance') and get_db_provider._instance is not None:
        return get_db_provider._instance

    if _global_db_instance is None:
        _global_db_instance = InMemoryAdapter()

    return _global_db_instance
