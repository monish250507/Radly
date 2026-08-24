import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch

from server.domain.models import ResearchAgentRun, AgentStatus, VerificationStatus
from server.engine.skeptic_runner import tick_skeptic
from server.tests.test_provenance_graph import make_dummy_project

@pytest.fixture
def mock_groq():
    with patch("server.engine.skeptic_runner.call_groq_api") as mock:
        yield mock

@pytest.mark.anyio
async def test_skeptic_wrong_parameter_mapping(mock_groq):
    # Skeptic intercepts and rejects
    mock_groq.side_effect = [
        {"action": "tool_call", "tool": "CodeSearch", "arguments": {"query": "tau"}},
        {"action": "verdict", "verdict": "REJECTED", "reason": "Tau is not found in the codebase."}
    ]
    
    project = make_dummy_project()
    run = ResearchAgentRun(
        run_id="run_skep_1",
        project_id="p1",
        goal="Check tau",
        current_state=AgentStatus.WAITING_FOR_SKEPTIC,
        current_conclusion="Tau affects Section 2",
        evidence_refs=["ev_123"],
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )
    
    # Tick 1: Request tool
    run = await tick_skeptic(run, project)
    assert run.skeptic_iterations == 1
    assert run.current_state == AgentStatus.WAITING_FOR_SKEPTIC
    assert len(run.skeptic_observations) == 1
    assert not run.skeptic_observations[0].is_error
    
    # Tick 2: Reject
    run = await tick_skeptic(run, project)
    assert run.skeptic_iterations == 2
    assert run.current_state == AgentStatus.COMPLETED
    assert run.status == VerificationStatus.REJECTED
    assert "Tau is not found" in run.current_conclusion

@pytest.mark.anyio
async def test_skeptic_iteration_limit():
    project = make_dummy_project()
    run = ResearchAgentRun(
        run_id="run_skep_2",
        project_id="p1",
        goal="Check loop",
        current_state=AgentStatus.WAITING_FOR_SKEPTIC,
        skeptic_max_iterations=2,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )
    
    run.skeptic_iterations = 2
    run = await tick_skeptic(run, project)
    
    assert run.current_state == AgentStatus.COMPLETED
    assert run.status == VerificationStatus.UNABLE_TO_VERIFY
