import os
import re
import time
import shutil
import zipfile
import asyncio
from pathlib import Path
from tempfile import mkdtemp
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from .engine.config import config
from .engine.logger import paperblast_logger as logger
from .engine.code_parser import extract_code_symbols
from .engine.paper_parser import extract_text_from_document, parse_paper_structure
from .engine.impact_engine import calculate_blast_radius
from .domain.models import SCHEMA_VERSION, JobStatus
from .engine.jobs import create_job, get_job, update_job_status
from fastapi import BackgroundTasks

class AnalyzeRequest(BaseModel):
    files: List[Dict[str, Any]]
    paper: Dict[str, Any]
    changeQuery: Optional[str] = None
    options: Optional[Dict[str, Any]] = None

app = FastAPI(title=config.Service.FRIENDLY_NAME)

@app.post("/api/jobs/analyze")
async def start_analysis_job(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    job_id = create_job()
    
    async def process_job():
        update_job_status(job_id, JobStatus.PROCESSING)
        try:
            await asyncio.sleep(1) # simulate work
            update_job_status(job_id, JobStatus.READY, result={"message": "Analysis Complete"})
        except Exception as e:
            update_job_status(job_id, JobStatus.FAILED, error=str(e))
            
    background_tasks.add_task(process_job)
    return {"jobId": job_id}

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers.pr_router import pr_router
app.include_router(pr_router)

class IngestGithubRequest(BaseModel):
    repoUrl: Optional[str] = None
    codeFiles: Optional[List[Dict[str, Any]]] = None

class ParsePaperRequest(BaseModel):
    documentBuffer: Optional[str] = None
    fileType: Optional[str] = 'txt'

class AnalyzeImpactRequest(BaseModel):
    codeSymbols: List[Dict[str, Any]]
    paperAST: Dict[str, Any]
    queryOrCodeChange: str
    opts: Optional[Dict[str, Any]] = None

@app.middleware("http")
async def add_request_context(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start_time) * 1000)
    logger.info("request completed", {
        "method": request.method,
        "path": request.url.path,
        "statusCode": response.status_code,
        "durationMs": duration_ms
    })
    return response

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
        proc = await asyncio.create_subprocess_shell(
            f'git clone --depth 1 --filter=blob:none {clean_url}.git "{target_dir}"',
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
                        zip_path = os.path.join(mkdtemp(), 'repo.zip')
                        with open(zip_path, 'wb') as f:
                            f.write(resp.content)
                        with zipfile.ZipFile(zip_path, 'r') as zf:
                            for fn in zf.namelist():
                                ext = os.path.splitext(fn)[1].lower()
                                if ext in valid_exts and not fn.endswith('/') and '/test' not in fn and '/venv' not in fn:
                                    content = zf.read(fn).decode('utf-8', errors='ignore')
                                    code_files.append({'path': fn, 'content': content})
                        break
                except Exception as e:
                    pass

    if not code_files:
        raise HTTPException(status_code=404, detail="Could not retrieve repository contents.")

    symbols = extract_code_symbols(code_files)
    return {
        "success": True,
        "repo": f"{owner}/{repo}",
        "fileCount": len(code_files),
        "files": [{"path": f["path"], "lineCount": len(f["content"].split("\n"))} for f in code_files],
        "symbols": symbols
    }

@app.post("/api/parse-paper")
async def parse_paper(req: ParsePaperRequest):
    if not req.documentBuffer:
        raise HTTPException(status_code=400, detail="Document content required.")
    
    raw_text = await extract_text_from_document(req.documentBuffer, req.fileType)
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
        req.opts
    )
    return result

@app.get("/api/health")
async def health_check():
    return {
        "status": "OK",
        "service": config.Service.NAME,
        "version": "1.0.0",
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
        "persistenceMode": "development-in-memory",
        "persistenceDurable": False,
        "note": "In-memory persistence only. Attach Vercel KV or external DB for production durability."
    }

dist_path = Path(__file__).parent.parent / "dist"
if dist_path.exists() and dist_path.is_dir():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="dist")
