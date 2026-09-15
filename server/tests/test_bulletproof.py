"""
test_bulletproof.py — Comprehensive reliability, stress, and edge-case test suite.
Validates concurrency, adversarial payloads, error resilience, security boundaries,
and deterministic degradation across the entire Radly architecture.
"""
import asyncio
import os
import tempfile
import time
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException

from server.domain.auth_models import (
    Comment, DiffHunk, FileDiff, DiffSummary, PRStatus, ResearchPR, Review, Role, User
)
from server.domain.models import (
    ArtifactType, EvidenceType, VerificationStatus, ResearchAgentRun, AgentStatus
)
from server.engine.auth import (
    JWT_SECRET, JWT_ALGORITHM, JWT_ISSUER, JWT_AUDIENCE,
    create_access_token, decode_token, require_role
)
from server.engine.code_parser import extract_code_symbols, parse_python_ast, is_extraction_failed
from server.engine.paper_parser import (
    extract_text_from_document, parse_paper_structure, _extract_latex_sync
)
from server.engine.impact_engine import calculate_blast_radius
from server.engine.persistence.db_adapter import SqliteAdapter, InMemoryAdapter


# ===========================================================================
# 1. Concurrency & Stress Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_concurrent_sqlite_writes_and_reads():
    """
    Stress test: 10 concurrent tasks writing PRs, adding comments, and reading
    simultaneously in SQLite to prove transaction isolation and absence of locks.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "concurrent_test.db")
        adapter = SqliteAdapter(db_path)

        async def worker(worker_id: int):
            pr_id = f"pr_concurrent_{worker_id}"
            pr = ResearchPR(
                id=pr_id,
                project_id="proj_stress",
                author_id=f"user_{worker_id}",
                base_version_id="main",
                proposed_version_id="feature",
                status=PRStatus.OPEN,
                analysis_status="PROCESSING",
                created_at="2026-09-14T10:00:00Z"
            )
            await adapter.create_pr(pr)

            # Add multiple comments concurrently
            for i in range(5):
                comment = Comment(
                    id=f"c_{worker_id}_{i}",
                    pr_id=pr_id,
                    author_id=f"user_{worker_id}",
                    content=f"Stress comment {i} from worker {worker_id}",
                    created_at="2026-09-14T10:01:00Z"
                )
                await adapter.add_comment(comment)

            # Read back
            loaded = await adapter.get_pr(pr_id)
            assert loaded is not None
            assert loaded.id == pr_id

            comments = await adapter.get_comments(pr_id)
            assert len(comments) == 5

        # Execute 10 workers in parallel
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify total PRs in project
        all_prs = await adapter.list_prs("proj_stress")
        assert len(all_prs) == 10


# ===========================================================================
# 2. Adversarial AST Code Parser Tests
# ===========================================================================
def test_ast_parser_handles_syntax_errors_gracefully():
    """
    Syntax errors must not raise exceptions or crash the parser.
    They must emit an EXTRACTION_FAILED sentinel and be excluded from clean results.
    """
    invalid_python = "def broken_function(:\n    return missing_paren"
    files = [{"path": "bad_syntax.py", "content": invalid_python}]
    
    symbols = extract_code_symbols(files)
    # clean symbols list must exclude failed files
    assert len(symbols) == 0

    # parse_python_ast directly emits the sentinel
    raw = parse_python_ast(invalid_python, "bad_syntax.py")
    assert len(raw) == 1
    assert is_extraction_failed(raw[0])
    assert raw[0]["extraction_status"] == "FAILED"


def test_ast_parser_handles_empty_and_whitespace_files():
    files = [
        {"path": "empty.py", "content": ""},
        {"path": "spaces.py", "content": "    \n\n\t  \n"},
        {"path": "comments_only.py", "content": "# Just a comment\n# Another comment\n\"\"\"Docstring only\"\"\""}
    ]
    symbols = extract_code_symbols(files)
    assert isinstance(symbols, list)


def test_ast_parser_skips_oversized_files():
    huge_content = "x = 1\n" * (6 * 1024 * 1024 // 6)  # > 5MB
    files = [{"path": "huge.py", "content": huge_content}]
    symbols = extract_code_symbols(files)
    assert len(symbols) == 0


def test_ast_parser_handles_deeply_nested_structures():
    deep_code = """
class Level1:
    class Level2:
        class Level3:
            def method(self):
                def inner_1():
                    def inner_2():
                        return 42
                    return inner_2()
                return inner_1()
"""
    files = [{"path": "deep.py", "content": deep_code}]
    symbols = extract_code_symbols(files)
    symbol_names = [s["symbol"] for s in symbols]
    assert "Level1" in symbol_names
    assert "Level2" in symbol_names
    assert "Level3" in symbol_names
    assert "method" in symbol_names


# ===========================================================================
# 3. Adversarial Document Parser Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_document_extraction_corrupted_pdf_raises():
    """Corrupted PDF bytes must raise ValueError cleanly without hanging."""
    corrupted_data = "this_is_not_a_valid_pdf_stream_content"
    with pytest.raises(ValueError) as exc:
        await extract_text_from_document(corrupted_data, file_type="pdf")
    assert "PDF extraction failed" in str(exc.value) or "failed" in str(exc.value).lower()


def test_latex_parser_unclosed_equations():
    """Unclosed or broken LaTeX math blocks must parse without infinite regex loops."""
    broken_latex = r"""
\section{Introduction}
Here is an unclosed equation:
\begin{equation}
E = mc^2
% Notice no \end{equation}

\section{Methodology}
Another regular paragraph.
\begin{table}
\caption{Test table}
\end{table}
"""
    result = _extract_latex_sync(broken_latex)
    assert result.status == "OK"
    assert "Introduction" in result.text


def test_parse_paper_structure_empty_text():
    ast = parse_paper_structure("")
    assert ast["sections"] == []
    assert ast["equations"] == []
    assert ast["tables"] == []


# ===========================================================================
# 4. Impact Engine Boundary & Degradation Tests
# ===========================================================================
@pytest.mark.asyncio
async def test_impact_engine_zero_inputs_returns_clean_result():
    """Zero symbols and zero paper sections must return NO_DEPENDENCY_FOUND without crash."""
    empty_paper = {"sections": [], "equations": [], "tables": []}
    with patch("server.engine.impact_engine.call_groq_api", return_value={"affected_sections": []}):
        result = await calculate_blast_radius([], empty_paper, "empty change", {})
        assert result["status"] == VerificationStatus.NO_DEPENDENCY_FOUND.value
        assert result["risk_level"] == "NONE"
        assert result["affected_sections"] == []


@pytest.mark.asyncio
async def test_impact_engine_llm_failure_degrades_to_static_matching(mini_symbols, mini_paper_ast):
    """When the LLM fails with an exception, pipeline must gracefully degrade to static keyword matching."""
    with patch("server.engine.impact_engine.call_groq_api", side_effect=Exception("Groq API 503 Service Unavailable")):
        result = await calculate_blast_radius(
            mini_symbols,
            mini_paper_ast,
            "learning_rate changed",
            {}
        )
        assert result["engine"]["mode"] == "static_fallback"
        assert result["status"] == VerificationStatus.ANALYSIS_FAILED.value
        assert "AI synthesis failed" in result["engine"]["note"]


# ===========================================================================
# 5. Authentication & Security Boundary Tests
# ===========================================================================
def test_jwt_tampered_signature_rejected():
    token = create_access_token({"email": "admin@example.com", "sub": "usr_admin"})
    tampered = token[:-4] + "xxxx"
    import jwt
    with pytest.raises(jwt.PyJWTError):
        decode_token(tampered)


def test_jwt_wrong_issuer_rejected():
    payload = {
        "email": "user@example.com",
        "sub": "usr_1",
        "iss": "malicious_issuer",
        "aud": JWT_AUDIENCE,
        "exp": int(time.time()) + 3600
    }
    import jwt
    bad_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidIssuerError):
        decode_token(bad_token)


def test_jwt_wrong_audience_rejected():
    payload = {
        "email": "user@example.com",
        "sub": "usr_1",
        "iss": JWT_ISSUER,
        "aud": "wrong_audience",
        "exp": int(time.time()) + 3600
    }
    import jwt
    bad_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidAudienceError):
        decode_token(bad_token)


@pytest.mark.asyncio
async def test_rbac_boundary_viewer_cannot_approve():
    """A VIEWER must be rejected with 403 if attempting an action requiring REVIEWER privileges."""
    db = InMemoryAdapter()
    user = await db.create_user("viewer@example.com")
    await db.add_project_member(user.id, "proj_secret", Role.VIEWER)

    with patch("server.engine.auth.get_db_provider", return_value=db):
        checker = require_role(Role.REVIEWER)
        with pytest.raises(HTTPException) as exc:
            await checker("proj_secret", user)
        assert exc.value.status_code == 403
        assert "requires reviewer privileges" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_rbac_boundary_non_member_forbidden():
    """A user who is not a member of a project must receive 403."""
    db = InMemoryAdapter()
    user = await db.create_user("outsider@example.com")
    # Not added to proj_private

    with patch("server.engine.auth.get_db_provider", return_value=db):
        checker = require_role(Role.VIEWER)
        with pytest.raises(HTTPException) as exc:
            await checker("proj_private", user)
        assert exc.value.status_code == 403
        assert "Not a member" in exc.value.detail


# ===========================================================================
# 6. Normalized Diff Summary & Subprocess Guards
# ===========================================================================
def test_diff_summary_model_validation():
    hunk = DiffHunk(
        old_start=10, old_lines=3, new_start=10, new_lines=4,
        header="@@ -10,3 +10,4 @@",
        lines=["- x = 1", "+ x = 2", "+ y = 3"]
    )
    file_diff = FileDiff(
        path="test.py", status="modified", additions=2, deletions=1, hunks=[hunk]
    )
    summary = DiffSummary(
        description="Refactor variables",
        total_files_changed=1,
        total_additions=2,
        total_deletions=1,
        modified=[file_diff]
    )
    assert summary.total_files_changed == 1
    assert summary.modified[0].hunks[0].new_lines == 4


# ===========================================================================
# 7. Middleware Guards: Rate Limiting, Payload Size & Headers
# ===========================================================================
def test_middleware_timing_header_present():
    """Every HTTP response must carry X-Response-Time-Ms."""
    from fastapi.testclient import TestClient
    from server.main import app
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.status_code == 200
    assert "X-Response-Time-Ms" in response.headers
    assert int(response.headers["X-Response-Time-Ms"]) >= 0


def test_middleware_payload_size_limit_rejection():
    """Requests exceeding MAX_REQUEST_SIZE (10 MB) must be rejected with 413."""
    from fastapi.testclient import TestClient
    from server.main import app
    client = TestClient(app)

    # Simulate a payload with Content-Length header exceeding 10MB
    oversized_headers = {"content-length": str(11 * 1024 * 1024)}
    response = client.post("/api/parse-paper", json={"documentBuffer": "x"}, headers=oversized_headers)
    assert response.status_code == 413
    data = response.json()
    assert "too large" in data.get("error", "").lower()


def test_middleware_rate_limiting_enforcement():
    """Writing more than 30 times in the sliding window triggers a 429."""
    from fastapi.testclient import TestClient
    from server.main import app, _rate_windows
    client = TestClient(app)

    # Clear rate window for test isolation
    _rate_windows.clear()

    # Issue 30 write requests (allowed)
    for _ in range(30):
        resp = client.post("/api/parse-paper", json={"documentBuffer": "test", "fileType": "txt"})
        assert resp.status_code in (200, 400)

    # 31st write request must be rate limited
    limited_resp = client.post("/api/parse-paper", json={"documentBuffer": "test", "fileType": "txt"})
    assert limited_resp.status_code == 429
    assert "Rate limit exceeded" in limited_resp.json().get("error", "")

    # Cleanup rate window
    _rate_windows.clear()


# ===========================================================================
# 8. Background Jobs Pipeline Tests
# ===========================================================================
def test_background_job_pipeline_full_lifecycle():
    """
    Test starting an asynchronous analysis job, validating execution
    in background tasks, and retrieving the completed result.
    """
    from fastapi.testclient import TestClient
    from server.main import app
    client = TestClient(app)

    payload = {
        "files": [
            {"path": "hyperparams.py", "content": "learning_rate = 0.001\nbatch_size = 64"}
        ],
        "paper": {
            "content": "# Methodology\nWe train with learning_rate 0.001 and batch_size 64.",
            "fileType": "txt"
        },
        "changeQuery": "Changed learning_rate to 0.01"
    }

    mock_llm_response = {
        "overall_impact_score": 80,
        "risk_level": "HIGH",
        "affected_sections": [{"section_id": "sec_1", "title": "Methodology", "verification": "VERIFIED", "risk": "HIGH", "reason": "lr changed"}],
        "affected_equations": [],
        "affected_tables": []
    }

    with patch("server.engine.impact_engine.call_groq_api", return_value=mock_llm_response):
        start_resp = client.post("/api/jobs/analyze", json=payload)
        assert start_resp.status_code == 200
        job_id = start_resp.json()["jobId"]
        assert job_id.startswith("job_")

        # In TestClient, background tasks execute synchronously
        status_resp = client.get(f"/api/jobs/{job_id}")
        assert status_resp.status_code == 200
        job_data = status_resp.json()
        assert job_data["status"] == "READY"
        assert "result" in job_data
        assert job_data["result"]["risk_level"] == "HIGH"


def test_background_job_missing_query_validation():
    """Submitting an analysis job with empty query must fail cleanly."""
    from fastapi.testclient import TestClient
    from server.main import app
    client = TestClient(app)

    # Empty string should fail Pydantic validator with 422
    resp = client.post("/api/jobs/analyze", json={"files": [], "changeQuery": "   "})
    assert resp.status_code == 422


def test_background_job_not_found_returns_404():
    """Querying a non-existent job ID returns 404."""
    from fastapi.testclient import TestClient
    from server.main import app
    client = TestClient(app)

    resp = client.get("/api/jobs/job_non_existent_12345")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


# ===========================================================================
# 9. Multi-Language Ingestion & Agnostic Parsing
# ===========================================================================
def test_multi_language_code_symbol_extraction():
    """
    Direct code ingestion must parse heterogeneous multi-language repositories:
    Python AST, JavaScript/TypeScript definitions, and JSON/YAML configuration keys.
    """
    files = [
        {
            "path": "train.py",
            "content": "class Trainer:\n    def train(self, epochs=10):\n        return epochs\n"
        },
        {
            "path": "frontend/config.js",
            "content": "const API_URL = 'https://api.example.com';\nlet MAX_RETRIES = 5;\n"
        },
        {
            "path": "hyperparams.json",
            "content": '{\n  "learning_rate": 0.0001,\n  "optimizer": "AdamW"\n}'
        }
    ]
    symbols = extract_code_symbols(files)
    symbols_by_name = {s["symbol"]: s for s in symbols}

    # Python
    assert "Trainer" in symbols_by_name
    assert symbols_by_name["Trainer"]["type"] == "Class"
    assert "train" in symbols_by_name
    assert "Method" in symbols_by_name["train"]["type"]

    # JS
    assert "API_URL" in symbols_by_name
    assert symbols_by_name["API_URL"]["type"] == "Variable"
    assert "MAX_RETRIES" in symbols_by_name

    # JSON config
    assert "learning_rate" in symbols_by_name
    assert symbols_by_name["learning_rate"]["type"] == "ConfigKey"


# ===========================================================================
# 10. Research PR Review & Merge Lifecycle Guard
# ===========================================================================
@pytest.mark.asyncio
async def test_pr_merge_blocked_when_analysis_incomplete():
    """
    A reviewer cannot merge a PR while impact analysis is still processing.
    Must return 409 Conflict until analysis reaches COMPLETE or FAILED.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SqliteAdapter(os.path.join(tmpdir, "review_test.db"))
        author = await db.create_user("author@example.com")
        reviewer = await db.create_user("reviewer@example.com")
        proj_id = await db.create_project()
        await db.add_project_member(author.id, proj_id, Role.OWNER)
        await db.add_project_member(reviewer.id, proj_id, Role.REVIEWER)

        pr = ResearchPR(
            id="pr_pending_analysis",
            project_id=proj_id,
            author_id=author.id,
            base_version_id="v1",
            proposed_version_id="v2",
            status=PRStatus.OPEN,
            analysis_status="PROCESSING",
            created_at="2026-09-14T12:00:00Z"
        )
        await db.create_pr(pr)

        from server.routers.pr_router import submit_review, SubmitReviewRequest
        with patch("server.routers.pr_router.get_db_provider", return_value=db), \
             patch("server.engine.auth.get_db_provider", return_value=db):
            # Attempt merge while PROCESSING
            with pytest.raises(HTTPException) as exc:
                await submit_review(
                    pr.id,
                    SubmitReviewRequest(verdict=PRStatus.MERGED, content="Looks good"),
                    user=reviewer
                )
            assert exc.value.status_code == 409
            assert "impact analysis is not yet complete" in exc.value.detail

            # Transition analysis to COMPLETE
            pr.analysis_status = "COMPLETE"
            await db.update_pr(pr)

            # Now merge should succeed
            res = await submit_review(
                pr.id,
                SubmitReviewRequest(verdict=PRStatus.MERGED, content="Approved and merged"),
                user=reviewer
            )
            assert res["status"] == "submitted"
            assert res["pr_status"] == PRStatus.MERGED.value

            # Verify in DB
            reloaded = await db.get_pr(pr.id)
            assert reloaded.status == PRStatus.MERGED


# ===========================================================================
# 11. Dynamic Schema Endpoint Reflection
# ===========================================================================
def test_domain_schema_reflects_active_db_adapter():
    """The /api/domain/schema endpoint must accurately reflect active persistence adapter."""
    from fastapi.testclient import TestClient
    from server.main import app
    client = TestClient(app)

    resp = client.get("/api/domain/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert "persistenceMode" in data
    assert "persistenceDurable" in data
    assert isinstance(data["persistenceDurable"], bool)
    assert data["persistenceMode"] in ("sqlite", "postgres", "in-memory")

