"""
test_real_world.py — End-to-end real-world integration verification
Tests live GitHub ingestion, real PDF parsing, and live Groq LLM impact analysis.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import httpx

BASE_URL = "http://localhost:5000"

def log(msg, success=True):
    icon = "[PASS]" if success else "[FAIL]"
    print(f"{icon} {msg}")

def test_health():
    resp = httpx.get(f"{BASE_URL}/api/health", timeout=10.0)
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    data = resp.json()
    assert data["status"] == "OK"
    assert data["groq_configured"] is True
    log("API Health Check OK (Groq Configured: True)")

def test_ingest_github():
    repo_url = "https://github.com/karpathy/nanoGPT"
    print(f"\n--> Testing Real GitHub Ingestion from: {repo_url} ...")
    resp = httpx.post(f"{BASE_URL}/api/ingest-github", json={"repoUrl": repo_url}, timeout=60.0)
    assert resp.status_code == 200, f"Ingest failed: {resp.status_code} - {resp.text}"
    data = resp.json()
    assert data["success"] is True, f"Ingest success flag False: {data}"
    file_count = data.get("fileCount", 0)
    symbols = data.get("symbols", [])
    assert file_count > 0, "No files cloned from repo"
    assert len(symbols) > 0, "No AST symbols extracted from repo"
    
    file_names = [f["path"] for f in data.get("files", [])]
    log(f"Cloned {file_count} files ({len(symbols)} AST symbols extracted)")
    log(f"Key files found: {[f for f in file_names if 'train.py' in f or 'model.py' in f]}")
    
    # Check for core symbols like learning_rate or GPT in nanoGPT
    symbol_names = [s.get("symbol") for s in symbols]
    has_lr = any("learning_rate" in s for s in symbol_names)
    has_gpt = any("GPT" in s for s in symbol_names)
    log(f"Found 'learning_rate' symbol: {has_lr}, 'GPT' symbol: {has_gpt}")
    assert has_lr or has_gpt, "Failed to identify key AST symbols in nanoGPT"
    return symbols

def test_parse_real_pdf():
    pdf_path = "real_paper_lora.pdf"
    if not os.path.exists(pdf_path):
        import urllib.request
        print("\n--> Auto-downloading LoRA sample paper (arXiv:2106.09685)...")
        req = urllib.request.Request(
            "https://arxiv.org/pdf/2106.09685.pdf", 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req) as response, open(pdf_path, 'wb') as out_file:
            out_file.write(response.read())
    print(f"\n--> Testing Real PDF Document Parsing: {pdf_path} ...")
    
    import base64
    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    resp = httpx.post(
        f"{BASE_URL}/api/parse-paper",
        json={"documentBuffer": pdf_b64, "fileType": "pdf"},
        timeout=60.0
    )
    assert resp.status_code == 200, f"Parse PDF failed: {resp.status_code} - {resp.text}"
    data = resp.json()
    assert data["success"] is True, f"Parse success flag False: {data}"
    paper_ast = data.get("paperAST", {})
    sections = paper_ast.get("sections", [])
    equations = paper_ast.get("equations", [])
    tables = paper_ast.get("tables", [])
    
    assert len(sections) > 0, "No sections parsed from real PDF"
    log(f"Extracted {len(sections)} sections, {len(equations)} equations, {len(tables)} tables from PDF")
    
    section_titles = [s.get("title") for s in sections[:5]]
    log(f"Sample section titles: {section_titles}")
    return paper_ast

def test_live_impact_analysis(symbols, paper_ast):
    print("\n--> Testing Live Impact Analysis with Groq LLM & Skeptic Arbiter...")
    
    # Test Case 1: High-Impact parameter change
    query_1 = "In train.py, changed learning_rate = 6e-4 to learning_rate = 1e-2 and increased weight_decay = 1e-1"
    print(f"\n[Case 1] Running query: '{query_1}' ...")
    payload_1 = {
        "codeSymbols": symbols[:150],  # send top relevant symbols
        "paperAST": paper_ast,
        "queryOrCodeChange": query_1,
        "repoUrl": "https://github.com/karpathy/nanoGPT"
    }
    resp_1 = httpx.post(f"{BASE_URL}/api/analyze-impact", json=payload_1, timeout=90.0)
    assert resp_1.status_code == 200, f"Impact analysis failed: {resp_1.status_code} - {resp_1.text}"
    data_1 = resp_1.json()
    
    status_1 = data_1.get("status")
    risk_1 = data_1.get("risk_level")
    affected_sections_1 = data_1.get("affected_sections", [])
    lineage_1 = data_1.get("lineage_graph", [])
    trace_1 = data_1.get("agent_collaboration_trace", [])
    findings_1 = data_1.get("domain", {}).get("findings", [])
    
    log(f"Result Status: {status_1} | Risk Level: {risk_1}")
    log(f"Affected Sections: {len(affected_sections_1)} | Lineage Graph Edges: {len(lineage_1)}")
    log(f"Domain Findings: {len(findings_1)} | Agent Trace Steps: {len(trace_1)}")
    assert status_1 is not None, "Missing status"
    assert risk_1 in ["HIGH", "MEDIUM", "LOW", "MINOR", "CRITICAL", "NONE"], f"Invalid risk: {risk_1}"
    assert len(trace_1) > 0, "Missing agent collaboration trace"
    
    # Test Case 2: Harmless documentation change (negative test)
    query_2 = "In README.md, formatted markdown headings and fixed typo in quickstart instructions"
    print(f"\n[Case 2] Running harmless query: '{query_2}' ...")
    payload_2 = {
        "codeSymbols": symbols[:150],
        "paperAST": paper_ast,
        "queryOrCodeChange": query_2,
        "repoUrl": "https://github.com/karpathy/nanoGPT"
    }
    resp_2 = httpx.post(f"{BASE_URL}/api/analyze-impact", json=payload_2, timeout=90.0)
    assert resp_2.status_code == 200, f"Impact analysis failed: {resp_2.status_code} - {resp_2.text}"
    data_2 = resp_2.json()
    status_2 = data_2.get("status")
    risk_2 = data_2.get("risk_level")
    log(f"Harmless Change Status: {status_2} | Risk Level: {risk_2}")
    
    # Assert Skeptic/Pipeline does NOT report CRITICAL/HIGH risk for doc typo
    assert risk_2 in ["NONE", "MINOR", "LOW"], f"Harmless change incorrectly assigned severe risk: {risk_2}"
    for f in data_2.get("domain", {}).get("findings", []):
        assert f.get("status") != "VERIFIED", "Harmless change produced false positive VERIFIED finding"
    log("Harmless change passed: 0 false positive VERIFIED findings.")

async def setup_pr_user_and_token():
    import asyncio
    from server.engine.persistence.db_adapter import get_db_provider
    from server.engine.auth import create_access_token
    from server.domain.auth_models import Role

    db = get_db_provider()
    user = await db.get_user_by_email("researcher@test.com")
    if not user:
        user = await db.create_user("researcher@test.com")
    await db.add_project_member(user.id, "proj_nanogpt", Role.MAINTAINER)
    token = create_access_token({"email": "researcher@test.com", "sub": user.id})
    return token

def test_research_pr_lifecycle():
    print("\n--> Testing Research PR & Durable SQLite Persistence Lifecycle...")
    import asyncio
    token = asyncio.run(setup_pr_user_and_token())
    headers = {"Authorization": f"Bearer {token}"}

    pr_payload = {
        "project_id": "proj_nanogpt",
        "base_repo_url": "https://github.com/karpathy/nanoGPT",
        "base_branch": "master",
        "proposed_repo_url": "https://github.com/karpathy/nanoGPT",
        "proposed_branch": "master",
        "change_description": "In train.py, adjust learning rate decay schedule to 1e-2 for faster warmup."
    }
    
    # 1. Create PR
    create_resp = httpx.post(f"{BASE_URL}/api/prs", json=pr_payload, headers=headers, timeout=30.0)
    assert create_resp.status_code == 201, f"Create PR failed: {create_resp.status_code} - {create_resp.text}"
    pr_data = create_resp.json()
    pr_id = pr_data["pr_id"]
    log(f"Created Research PR {pr_id}")
    
    # 2. Add Comment
    comment_payload = {
        "content": "Verified: Checked against paper parameters."
    }
    comm_resp = httpx.post(f"{BASE_URL}/api/prs/{pr_id}/comments", json=comment_payload, headers=headers, timeout=10.0)
    assert comm_resp.status_code == 201, f"Add comment failed: {comm_resp.text}"
    log(f"Added review comment to PR {pr_id}")
    
    # 3. Add Review
    review_payload = {
        "verdict": "APPROVED",
        "content": "Diff verified against hyperparameter table."
    }
    rev_resp = httpx.post(f"{BASE_URL}/api/prs/{pr_id}/review", json=review_payload, headers=headers, timeout=10.0)
    assert rev_resp.status_code == 201, f"Add review failed: {rev_resp.text}"
    log(f"Added review verdict APPROVED to PR {pr_id}")
    
    # 4. Fetch PR details
    get_resp = httpx.get(f"{BASE_URL}/api/prs/{pr_id}", headers=headers, timeout=10.0)
    assert get_resp.status_code == 200, f"Get PR failed: {get_resp.text}"
    fetched_pr = get_resp.json()
    assert fetched_pr["pr"]["id"] == pr_id
    assert fetched_pr["pr"]["status"] == "APPROVED"
    assert len(fetched_pr["comments"]) >= 1
    assert len(fetched_pr["reviews"]) >= 1
    log(f"Retrieved PR {pr_id}: status={fetched_pr['pr']['status']}, comments={len(fetched_pr['comments'])}, reviews={len(fetched_pr['reviews'])}")

if __name__ == "__main__":
    try:
        test_health()
        symbols = test_ingest_github()
        paper_ast = test_parse_real_pdf()
        test_live_impact_analysis(symbols, paper_ast)
        test_research_pr_lifecycle()
        print("\n=======================================================")
        print("ALL REAL-WORLD INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
        print("=======================================================")
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
