import uuid
from datetime import datetime
from typing import Dict, Any
from ..domain.models import JobRecord, JobStatus, ResearchProject

# In-memory mock for persistence
_job_queue: Dict[str, JobRecord] = {}

def create_job() -> str:
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    _job_queue[job_id] = JobRecord(
        jobId=job_id,
        status=JobStatus.QUEUED,
        createdAt=datetime.utcnow().isoformat() + "Z",
        updatedAt=datetime.utcnow().isoformat() + "Z"
    )
    return job_id

def get_job(job_id: str) -> JobRecord:
    return _job_queue.get(job_id)

def update_job_status(job_id: str, status: JobStatus, result: Any = None, error: str = None):
    job = _job_queue.get(job_id)
    if job:
        job.status = status
        job.updatedAt = datetime.utcnow().isoformat() + "Z"
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
