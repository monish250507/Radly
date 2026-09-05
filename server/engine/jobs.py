import uuid
from datetime import datetime
from typing import Any

from ..domain.models import JobRecord, JobStatus

# In-process job store (development only — jobs do not survive restarts).
# P0 NOTE: For production, replace with a durable job backend (e.g. Redis, Postgres).
_job_queue: dict[str, JobRecord] = {}

def create_job() -> str:
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    _job_queue[job_id] = JobRecord(
        jobId=job_id,
        status=JobStatus.QUEUED,
        createdAt=datetime.utcnow().isoformat() + "Z",
        updatedAt=datetime.utcnow().isoformat() + "Z"
    )
    return job_id

def get_job(job_id: str) -> JobRecord | None:
    return _job_queue.get(job_id)

def update_job_status(job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None):
    """Update job status and optionally set result, error, or stage progress label."""
    job = _job_queue.get(job_id)
    if job:
        job.status = status
        job.updatedAt = datetime.utcnow().isoformat() + "Z"
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        if progress is not None:
            # Store progress on result dict so callers can poll stage
            if job.result is None:
                job.result = {}
            if isinstance(job.result, dict):
                job.result['_progress'] = progress

