import uuid
import json
import os
from datetime import datetime
from typing import Any

from ..domain.models import JobRecord, JobStatus

_job_queue: dict[str, JobRecord] = {}
_pool = None

async def _get_pool():
    global _pool
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        return None
    if not _pool:
        import asyncpg
        _pool = await asyncpg.create_pool(database_url)
        async with _pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    result TEXT,
                    error TEXT
                )
            ''')
    return _pool

async def create_job() -> str:
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat() + "Z"
    
    pool = await _get_pool()
    if pool:
        await pool.execute("INSERT INTO jobs (job_id, status, created_at, updated_at) VALUES ($1, $2, $3, $4)",
            job_id, JobStatus.QUEUED.value, created_at, created_at)
    else:
        _job_queue[job_id] = JobRecord(
            jobId=job_id, status=JobStatus.QUEUED, createdAt=created_at, updatedAt=created_at
        )
    return job_id

async def get_job(job_id: str) -> JobRecord | None:
    pool = await _get_pool()
    if pool:
        row = await pool.fetchrow("SELECT * FROM jobs WHERE job_id=$1", job_id)
        if row:
            result = json.loads(row['result']) if row['result'] else None
            return JobRecord(
                jobId=row['job_id'], status=JobStatus(row['status']),
                createdAt=row['created_at'], updatedAt=row['updated_at'],
                result=result, error=row['error']
            )
        return None
    else:
        return _job_queue.get(job_id)

async def update_job_status(job_id: str, status: JobStatus, result: Any = None, error: str = None, progress: str = None):
    pool = await _get_pool()
    updated_at = datetime.utcnow().isoformat() + "Z"
    
    if pool:
        row = await pool.fetchrow("SELECT result FROM jobs WHERE job_id=$1", job_id)
        if not row: return
        
        current_result = json.loads(row['result']) if row['result'] else {}
        if result is not None: current_result = result
        if progress is not None:
            if not isinstance(current_result, dict): current_result = {}
            current_result['_progress'] = progress
            
        await pool.execute("UPDATE jobs SET status=$1, updated_at=$2, result=$3, error=$4 WHERE job_id=$5",
            status.value, updated_at, json.dumps(current_result) if current_result else None, error, job_id)
    else:
        job = _job_queue.get(job_id)
        if job:
            job.status = status
            job.updatedAt = updated_at
            if result is not None: job.result = result
            if error is not None: job.error = error
            if progress is not None:
                if job.result is None: job.result = {}
                if isinstance(job.result, dict): job.result['_progress'] = progress

