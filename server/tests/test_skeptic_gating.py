"""
test_skeptic_gating.py — Tests for P0-1 authoritative Skeptic hard-gating.
Proves that a rejected finding must NEVER surface as VERIFIED, and that
adversarial Skeptic verdicts strictly constrain final finding statuses.
"""
from unittest.mock import patch
import pytest

from server.domain.models import AgentStatus, VerificationStatus, ResearchAgentRun
from server.engine.impact_engine import calculate_blast_radius


@pytest.mark.asyncio
async def test_skeptic_rejection_prevents_verified_findings(mini_symbols, mini_paper_ast):
    """
    P0-1: Even if AI or heuristics suggest a section is affected/verified,
    if the Skeptic outputs REJECTED, no finding may surface as VERIFIED.
    """
    # 1. Primary AI returns proposed affected sections
    ai_impact_response = {
        "overall_impact_score": 85,
        "risk_level": "HIGH",
        "affected_sections": [
            {
                "section_id": "sec_1",
                "title": "Methodology",
                "verification": "VERIFIED",
                "risk": "HIGH",
                "reason": "Learning rate parameter changed"
            }
        ],
        "affected_equations": [],
        "affected_tables": [],
        "lineage_graph": []
    }

    # 2. Agent runner concludes and asks for skeptic
    agent_step = {
        "action": "conclude",
        "conclusion": "Change directly impacts learning rate in Methodology",
        "evidence": ["ev_1"]
    }

    # 3. Skeptic evaluates and REJECTS the claim
    skeptic_verdict = {
        "action": "verdict",
        "verdict": "REJECTED",
        "reason": "The parameter is local to debugging and not referenced in the paper equation."
    }

    with patch('server.engine.impact_engine.call_groq_api') as mock_llm:
        mock_llm.side_effect = [ai_impact_response, agent_step, skeptic_verdict]

        result = await calculate_blast_radius(
            mini_symbols,
            mini_paper_ast,
            "Modified learning rate parameter in optimizer",
            {"repoUrl": "https://github.com/example/repo"}
        )

        # Assertions on final result
        assert result['status'] == VerificationStatus.REJECTED.value

        # Every section must NOT be VERIFIED
        for sec in result['affected_sections']:
            assert sec.get('verification') == VerificationStatus.REJECTED.value
            assert sec.get('status') != VerificationStatus.VERIFIED.value

        # Every finding in domain model must NOT be VERIFIED
        domain_findings = result['domain'].get('findings', [])
        assert len(domain_findings) > 0
        for f in domain_findings:
            assert f['status'] == VerificationStatus.REJECTED.value
            assert "Rejected by Skeptic" in f.get('reason', '')


@pytest.mark.asyncio
async def test_skeptic_conflicting_evidence_constrains_findings(mini_symbols, mini_paper_ast):
    """
    P0-1: If the Skeptic identifies CONFLICTING_EVIDENCE, findings must be marked CONFLICTING_EVIDENCE.
    """
    ai_impact_response = {
        "overall_impact_score": 70,
        "risk_level": "MEDIUM",
        "affected_sections": [
            {
                "section_id": "sec_1",
                "title": "Methodology",
                "verification": "VERIFIED",
                "risk": "MEDIUM",
                "reason": "Batch size changed"
            }
        ]
    }

    agent_step = {
        "action": "conclude",
        "conclusion": "Batch size modified",
        "evidence": ["ev_1"]
    }

    skeptic_verdict = {
        "action": "verdict",
        "verdict": "CONFLICTING_EVIDENCE",
        "reason": "Contradictory batch size definitions across files."
    }

    with patch('server.engine.impact_engine.call_groq_api') as mock_llm:
        mock_llm.side_effect = [ai_impact_response, agent_step, skeptic_verdict]

        result = await calculate_blast_radius(
            mini_symbols,
            mini_paper_ast,
            "Modified batch size",
            {"repoUrl": "https://github.com/example/repo"}
        )

        assert result['status'] == VerificationStatus.CONFLICTING_EVIDENCE.value
        for sec in result['affected_sections']:
            assert sec.get('verification') == VerificationStatus.CONFLICTING_EVIDENCE.value


@pytest.mark.asyncio
async def test_skeptic_needs_review_demotes_verified(mini_symbols, mini_paper_ast):
    """
    P0-1: If the Skeptic outputs NEEDS_REVIEW, findings must not remain VERIFIED.
    """
    ai_impact_response = {
        "overall_impact_score": 50,
        "risk_level": "LOW",
        "affected_sections": [
            {
                "section_id": "sec_1",
                "title": "Methodology",
                "verification": "VERIFIED",
                "risk": "LOW",
                "reason": "Docstring tweak"
            }
        ]
    }

    agent_step = {
        "action": "conclude",
        "conclusion": "Docstring updated",
        "evidence": ["ev_1"]
    }

    skeptic_verdict = {
        "action": "verdict",
        "verdict": "NEEDS_REVIEW",
        "reason": "Unable to deterministically confirm code dependency."
    }

    with patch('server.engine.impact_engine.call_groq_api') as mock_llm:
        mock_llm.side_effect = [ai_impact_response, agent_step, skeptic_verdict]

        result = await calculate_blast_radius(
            mini_symbols,
            mini_paper_ast,
            "Updated docstrings",
            {"repoUrl": "https://github.com/example/repo"}
        )

        assert result['status'] == VerificationStatus.NEEDS_REVIEW.value
        for sec in result['affected_sections']:
            assert sec.get('verification') == VerificationStatus.NEEDS_REVIEW.value
