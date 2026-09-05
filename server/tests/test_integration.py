"""
test_integration.py — P2: Integration tests.

Tests the full end-to-end pipeline (Code + Paper + Query -> Result).
"""
from unittest.mock import patch

import pytest

from server.engine.impact_engine import calculate_blast_radius


@pytest.mark.asyncio
async def test_full_pipeline_integration(mini_symbols, mini_paper_ast):
    """
    Run the full calculate_blast_radius pipeline with mocked LLM.
    Ensures the data structures flow correctly from start to finish.
    """
    
    with patch('server.engine.impact_engine.call_groq_api') as mock_llm:
        mock_llm.return_value = {
            "overall_impact_score": 0,
            "risk_level": "MINOR",
            "affected_sections": [
                {
                    "section_id": "sec-3-methodology",
                    "title": "Methodology",
                    "reason": "Learning rate changed",
                    "suggested_text": "We set learning_rate=1e-2",
                    "risk": "MINOR"
                }
            ],
            "affected_equations": [],
            "affected_tables": [],
            "lineage_graph": [
                {
                    "source": "learning_rate",
                    "target": "sec-3-methodology",
                    "relationship": "parameter_used_in_section",
                    "confidence": "HIGH",
                    "explanation": "test"
                }
            ],
            "agent_collaboration_trace": []
        }
        
        result = await calculate_blast_radius(
            mini_symbols, 
            mini_paper_ast, 
            "Changed learning rate to 1e-2",
            {"repoUrl": "github.com/test/repo"}
        )
        
        assert result["status"] in ["ANALYSIS_COMPLETE", "NEEDS_REVIEW"]
        assert result["risk_level"] == "MINOR"
        
        # Verify domain serialization
        assert "domain" in result
        assert result["domain"]["analysisVersion"]["symbolCount"] == len(mini_symbols)
        
        # Check that the mock sections were mapped
        assert len(result["affected_sections"]) == 1
        assert result["affected_sections"][0]["section_id"] == "sec-3-methodology"
