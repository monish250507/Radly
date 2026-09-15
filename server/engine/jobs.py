import uuid
from datetime import datetime, timezone
from typing import Any

from ..domain.models import JobRecord, JobStatus
from .persistence.db_adapter import get_db_provider


async def create_job() -> str:
    """Create a new job record in durable storage."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    job = JobRecord(
        jobId=job_id,
        status=JobStatus.QUEUED,
        createdAt=created_at,
        updatedAt=created_at
    )
    db = get_db_provider()
    await db.create_job_record(job)
    return job_id


async def get_job(job_id: str) -> JobRecord | None:
    """Retrieve job record from durable storage."""
    db = get_db_provider()
    return await db.get_job_record(job_id)


async def update_job_status(job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None):
    """Update job status and results in durable storage."""
    db = get_db_provider()
    await db.update_job_record(job_id, status, result=result, error=error, progress=progress)
