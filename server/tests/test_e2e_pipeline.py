"""
test_e2e_pipeline.py — End-to-end integration pipeline tests.
Covers: code ingestion -> paper parsing -> impact analysis -> frontend response contract.
"""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from server.main import app


client = TestClient(app)


def test_e2e_upload_parse_analyze_contract():
    """
    Validates end-to-end workflow corresponding to frontend UI tabs:
    1. /api/ingest-github (Direct Upload)
    2. /api/parse-paper
    3. /api/analyze-impact
    4. Confirms all fields expected by App.jsx are populated.
    """
    # 1. Code Ingestion
    code_files = [
        {
            "name": "model.py",
            "content": (
                "class Transformer:\n"
                "    def __init__(self, lr=0.001):\n"
                "        self.lr = lr\n"
                "    def step(self):\n"
                "        loss = 0.5\n"
                "        return loss\n"
            )
        }
    ]

    ingest_resp = client.post("/api/ingest-github", json={"codeFiles": code_files})
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["success"] is True
    assert len(ingest_data["symbols"]) > 0
    symbols = ingest_data["symbols"]

    # 2. Paper Parsing
    paper_text = (
        "# 1. Introduction\nWe introduce a Transformer trained with learning rate 0.001.\n\n"
        "# 2. Methodology\nEquation (1) defines our loss function: L = 0.5 * loss.\n\n"
        "# 3. Results\nTable 1 shows accuracy 95%."
    )

    paper_resp = client.post("/api/parse-paper", json={"documentBuffer": paper_text, "fileType": "txt"})
    assert paper_resp.status_code == 200
    paper_data = paper_resp.json()
    assert paper_data["success"] is True
    paper_ast = paper_data["paperAST"]
    assert len(paper_ast["sections"]) >= 3

    # 3. Impact Analysis (Mock LLM response for deterministic assertion)
    mock_ai_response = {
        "overall_impact_score": 75,
        "risk_level": "MEDIUM",
        "affected_sections": [
            {
                "section_id": "sec_1",
                "title": "Methodology",
                "verification": "VERIFIED",
                "risk": "MEDIUM",
                "reason": "Modified lr in optimizer affects Methodology"
            }
        ],
        "affected_equations": [],
        "affected_tables": []
    }

    mock_agent_conclude = {
        "action": "conclude",
        "conclusion": "Changes to learning rate impact Methodology section",
        "evidence": ["ev_1"]
    }

    mock_skeptic_verdict = {
        "action": "verdict",
        "verdict": "VERIFIED",
        "reason": "Evidence confirmed by deterministic parameter mapping."
    }

    with patch('server.engine.impact_engine.call_groq_api') as mock_llm:
        mock_llm.side_effect = [mock_ai_response, mock_agent_conclude, mock_skeptic_verdict]

        analysis_resp = client.post("/api/analyze-impact", json={
            "codeSymbols": symbols,
            "paperAST": paper_ast,
            "queryOrCodeChange": "Changed lr default from 0.001 to 0.01",
            "opts": {}
        })

        assert analysis_resp.status_code == 200
        analysis = analysis_resp.json()

        # 4. Frontend UI Contract Verification (App.jsx tabs)
        # Tab: Overview
        assert "status" in analysis
        assert "risk_level" in analysis
        assert "engine" in analysis
        assert "validation_summary" in analysis["engine"]

        # Tab: Changes
        assert "affected_sections" in analysis
        assert isinstance(analysis["affected_sections"], list)

        # Tab: Experiments
        assert "affected_equations" in analysis
        assert "affected_tables" in analysis

        # Tab: Lineage Graph
        assert "lineage_graph" in analysis
        assert isinstance(analysis["lineage_graph"], list)

        # Tab: Agent Trace
        assert "agent_collaboration_trace" in analysis
        assert len(analysis["agent_collaboration_trace"]) > 0

        # Domain persistence payload
        assert "domain" in analysis
        assert "findings" in analysis["domain"]
