import asyncio
import os
import re
import shutil
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .domain.models import SCHEMA_VERSION, JobStatus
from .engine.code_parser import extract_code_symbols
from .engine.config import config
from .engine.impact_engine import calculate_blast_radius
from .engine.jobs import create_job, get_job, update_job_status
from .engine.logger import radly_logger as logger
from .engine.paper_parser import extract_text_from_document, parse_paper_structure


# ---------------------------------------------------------------------------
# Request Models (with validation)
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    files: list[dict[str, Any]] = []
    paper: dict[str, Any] | None = None
    changeQuery: str | None = None
    options: dict[str, Any] | None = None

    @field_validator('changeQuery')
    @classmethod
    def validate_query(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('changeQuery cannot be an empty string.')
        return v


# ---------------------------------------------------------------------------
# Rate limiter — sliding window (production: replace with Redis)
# ---------------------------------------------------------------------------
_rate_windows: dict = defaultdict(list)

RATE_LIMITS = {
    'write': {'max': 30,  'window': 60},   # 30 write requests per 60s per IP
    'read':  {'max': 120, 'window': 60},   # 120 read requests per 60s per IP
}

def _check_rate_limit(client_ip: str, kind: str = 'read') -> bool:
    """Returns True if allowed, False if rate-limited."""
    limit = RATE_LIMITS.get(kind, RATE_LIMITS['read'])
    now = time.monotonic()
    window_key = f"{client_ip}:{kind}"
    timestamps = _rate_windows[window_key]
    # Prune old entries
    cutoff = now - limit['window']
    _rate_windows[window_key] = [t for t in timestamps if t > cutoff]
    if len(_rate_windows[window_key]) >= limit['max']:
        return False
    _rate_windows[window_key].append(now)
    return True


# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------
app = FastAPI(
    title=config.Service.FRIENDLY_NAME,
    description='Radly — Research Code & Paper Impact Analyzer API',
    version=config.Service.VERSION,
    docs_url='/api/docs',
    redoc_url='/api/redoc',
    openapi_url='/api/openapi.json',
)

@app.post("/api/jobs/analyze")
async def start_analysis_job(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    P0 FIX: Real analysis pipeline replaces the simulated asyncio.sleep(1) job.
    A job only reaches READY after the actual stages complete.
    Stages: symbol extraction → paper parsing → impact analysis.
    """
    job_id = await create_job()

    async def process_job():
        await update_job_status(job_id, JobStatus.PROCESSING, progress="stage:extract_symbols")
        try:
            # Stage 1: Extract code symbols from provided files
            code_symbols = extract_code_symbols(req.files) if req.files else []
            await update_job_status(job_id, JobStatus.PROCESSING, progress="stage:parse_paper")

            # Stage 2: Parse paper structure from provided paper content
            paper_content = req.paper.get("content", "") if req.paper else ""
            file_type = req.paper.get("fileType", "txt") if req.paper else "txt"
            if paper_content:
                raw_text = await extract_text_from_document(paper_content, file_type)
                paper_ast = parse_paper_structure(raw_text)
            else:
                paper_ast = {"sections": [], "equations": [], "tables": [], "claims": []}
            await update_job_status(job_id, JobStatus.PROCESSING, progress="stage:calculate_impact")

            # Stage 3: Run deterministic impact analysis
            change_query = req.changeQuery or ""
            if not change_query:
                await update_job_status(
                    job_id, JobStatus.FAILED,
                    error="changeQuery is required for impact analysis. Provide a code diff, PR description, or change description."
                )
                return

            result = await calculate_blast_radius(
                code_symbols,
                paper_ast,
                change_query,
                req.options or {}
            )

            await update_job_status(job_id, JobStatus.READY, result=result)

        except Exception as e:
            logger.error("Job pipeline failed", {"job_id": job_id, "error": str(e)})
            await update_job_status(job_id, JobStatus.FAILED, error=str(e))

    background_tasks.add_task(process_job)
    return {"jobId": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Middleware: request logging + rate limiting + request size guard
# ---------------------------------------------------------------------------
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB

@app.middleware('http')
async def request_middleware(request: Request, call_next):
    start = time.monotonic()
    client_ip = request.client.host if request.client else 'unknown'
    method = request.method
    path = request.url.path

    # Request size guard
    content_length = request.headers.get('content-length')
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        logger.warn('Request exceeds size limit', {'ip': client_ip, 'path': path, 'size': content_length})
        return Response(
            content='{"error": "Request body too large. Maximum 10 MB."}',
            status_code=413,
            media_type='application/json'
        )

    # Rate limiting
    is_write = method in ('POST', 'PUT', 'PATCH', 'DELETE')
    kind = 'write' if is_write else 'read'
    if not _check_rate_limit(client_ip, kind):
        limit = RATE_LIMITS[kind]
        logger.warn('Rate limit exceeded', {'ip': client_ip, 'path': path, 'kind': kind})
        return Response(
            content=f'{{"error": "Rate limit exceeded. Max {limit["max"]} {kind} requests per {limit["window"]}s."}}',
            status_code=429,
            media_type='application/json'
        )

    response = await call_next(request)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    logger.info('Request completed', {
        'method': method, 'path': path,
        'status': response.status_code, 'ms': elapsed_ms, 'ip': client_ip
    })
    response.headers['X-Response-Time-Ms'] = str(elapsed_ms)
    return response


from .routers.pr_router import pr_router

app.include_router(pr_router)

class IngestGithubRequest(BaseModel):
    repoUrl: str | None = None
    codeFiles: list[dict[str, Any]] | None = None

class ParsePaperRequest(BaseModel):
    documentBuffer: str | None = None
    fileType: str | None = 'txt'

class AnalyzeImpactRequest(BaseModel):
    codeSymbols: list[dict[str, Any]]
    paperAST: dict[str, Any]
    queryOrCodeChange: str
    opts: dict[str, Any] | None = None

@app.post("/api/ingest-github")
async def ingest_github(req: IngestGithubRequest):
    if req.codeFiles:
        symbols = extract_code_symbols(req.codeFiles)
        return {
            "success": True,
            "repo": "Direct Upload",
            "fileCount": len(req.codeFiles),
            "files": [{"path": f.get("name") or f.get("path"), "lineCount": len(f.get("content", "").split("\n"))} for f in req.codeFiles],
            "symbols": symbols
        }

    if not req.repoUrl:
        raise HTTPException(status_code=400, detail="Repository URL or code files required.")

    clean_url = re.sub(r'(\.git|/)$', '', req.repoUrl)
    match = re.search(r'github\.com/([^/]+)/([^/]+)', clean_url)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL structure.")

    owner, repo = match.groups()
    code_files = []
    valid_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml', '.cpp', '.cu', '.h', '.c', '.rs', '.go'}

    # Strategy 1: Git clone
    target_dir = mkdtemp(prefix=f"repo_{owner}_{repo}_")
    try:
        proc = await asyncio.create_subprocess_exec(
            'git', 'clone', '--depth', '1', '--filter=blob:none', f"{clean_url}.git", target_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            proc.kill()
            
        if os.path.exists(target_dir):
            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'venv', '__pycache__'} and not d.startswith('.')]
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in valid_exts and '/test' not in root.replace('\\', '/'):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, target_dir).replace('\\', '/')
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                code_files.append({'path': rel_path, 'content': f.read()})
                        except Exception:
                            pass
    except Exception as e:
        logger.warn('git clone skipped/failed', {'reason': str(e), 'repo': f"{owner}/{repo}"})
    finally:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)

    # Strategy 2: Zip fallback
    if not code_files:
        async with httpx.AsyncClient() as client:
            for branch in ['main', 'master', 'dev']:
                try:
                    zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
                    resp = await client.get(zip_url, timeout=6.0, headers={'User-Agent': 'Mozilla/5.0'})
                    if resp.status_code == 200:
                        zip_dir = mkdtemp(prefix="zip_download_")
                        try:
                            zip_path = os.path.join(zip_dir, 'repo.zip')
                            with open(zip_path, 'wb') as zip_f:
                                zip_f.write(resp.content)
                            with zipfile.ZipFile(zip_path, 'r') as zf:
                                for fn in zf.namelist():
                                    ext = os.path.splitext(fn)[1].lower()
                                    if ext in valid_exts and not fn.endswith('/') and '/test' not in fn and '/venv' not in fn:
                                        content = zf.read(fn).decode('utf-8', errors='ignore')
                                        code_files.append({'path': fn, 'content': content})
                        finally:
                            shutil.rmtree(zip_dir, ignore_errors=True)
                        break
                except Exception:
                    pass

    # Filter out cookiecutter template dummy folders and third-party vendored code
    ignored_subpaths = {'cookiecutter', 'templates', 'node_modules', '.git', '__pycache__', 'test', 'tests', 'venv', '.venv'}
    code_files = [f for f in code_files if not any(ign in f['path'].lower() for ign in ignored_subpaths)]

    symbols = extract_code_symbols(code_files)
    # Cap symbols payload returned to frontend at 2000 most relevant symbols to keep browser ultra-fast
    total_symbols_count = len(symbols)
    if len(symbols) > 2000:
        symbols = symbols[:2000]

    return {
        "success": True,
        "repo": f"{owner}/{repo}",
        "fileCount": len(code_files),
        "totalSymbolsCount": total_symbols_count,
        "files": [{"path": f["path"], "lineCount": len(f["content"].split("\n"))} for f in code_files[:100]],
        "symbols": symbols
    }

@app.post("/api/parse-paper")
@app.post("/api/parse-document")
async def parse_paper(req: ParsePaperRequest):
    if not req.documentBuffer:
        raise HTTPException(status_code=400, detail="Document content required.")
    
    raw_text = await extract_text_from_document(req.documentBuffer, req.fileType or 'txt')
    paper_ast = parse_paper_structure(raw_text)
    
    return {
        "success": True,
        "paperAST": paper_ast
    }

@app.post("/api/analyze-impact")
async def analyze_impact(req: AnalyzeImpactRequest):
    if not req.queryOrCodeChange:
        raise HTTPException(status_code=400, detail="queryOrCodeChange is required")
    if not req.codeSymbols:
        raise HTTPException(status_code=400, detail="codeSymbols is required")
    if not req.paperAST:
        raise HTTPException(status_code=400, detail="paperAST is required")
        
    result = await calculate_blast_radius(
        req.codeSymbols,
        req.paperAST,
        req.queryOrCodeChange,
        req.opts or {}
    )
    return result

@app.get("/api/health")
async def health_check():
    return {
        "status": "OK",
        "service": config.Service.NAME,
        "version": config.Service.VERSION,
        "runtime": config.RUNTIME_MODE,
        "env": config.ENV,
        "groq_configured": config.Groq.CONFIGURED,
        "domain_schema": SCHEMA_VERSION
    }

@app.get("/api/domain/schema")
async def domain_schema():
    from .domain.models import ArtifactType, EvidenceType, VerificationStatus
    return {
        "schemaVersion": SCHEMA_VERSION,
        "artifactTypes": [e.value for e in ArtifactType],
        "evidenceTypes": [e.value for e in EvidenceType],
        "verificationStatuses": [e.value for e in VerificationStatus],
        "persistenceMode": "in-memory",
        "persistenceDurable": False,
        "note": "Active persistence: in-memory (cloud-optimized, zero-db)."
    }

dist_path = Path(__file__).parent.parent / "dist"
if dist_path.exists() and dist_path.is_dir():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="dist")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=config.PORT)

