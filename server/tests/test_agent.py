from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from server.domain.models import AgentStatus, ResearchAgentRun, VerificationStatus
from server.engine.agent_runner import tick_agent
from server.tests.test_provenance_graph import make_dummy_project


@pytest.fixture
def mock_groq():
    with patch("server.engine.agent_runner.call_groq_api") as mock:
        yield mock

@pytest.mark.anyio
async def test_agent_multi_step_success(mock_groq):
    # LLM response sequence
    mock_groq.side_effect = [
        # Tick 1: Call ASTQuery
        {"action": "tool_call", "tool": "ASTQuery", "arguments": {"artifact_id": "art_code1"}},
        # Tick 2: Call PaperSearch
        {"action": "tool_call", "tool": "PaperSearch", "arguments": {"keyword": "accuracy"}},
        # Tick 3: Conclude
        {
            "action": "conclude", 
            "conclusion": "The accuracy claim is affected.", 
            "status": "NEEDS_REVIEW", 
            "evidence_refs": ["art_claim1"]
        }
    ]
    
    project = make_dummy_project()
    now_iso = datetime.now(timezone.utc).isoformat()
    run = ResearchAgentRun(
        run_id="run_1",
        project_id="p1",
        goal="What happens if I change learning_rate?",
        created_at=now_iso,
        updated_at=now_iso
    )
    
    # Tick 1
    run = await tick_agent(run, project)
    assert run.iteration_count == 1
    assert run.current_state == AgentStatus.WAITING_FOR_TOOL
    assert len(run.tool_calls) == 1
    assert run.tool_calls[0].name == "ASTQuery"
    assert len(run.observations) == 1
    assert not run.observations[0].is_error
    
    # Tick 2
    run = await tick_agent(run, project)
    assert run.iteration_count == 2
    assert run.tool_calls[1].name == "PaperSearch"
    
    # Tick 3
    run = await tick_agent(run, project)
    assert run.iteration_count == 3
    assert run.current_state == AgentStatus.WAITING_FOR_SKEPTIC
    assert run.current_conclusion == "The accuracy claim is affected."
    assert run.status == VerificationStatus.NEEDS_REVIEW

@pytest.mark.anyio
async def test_agent_iteration_limit():
    project = make_dummy_project()
    run = ResearchAgentRun(
        run_id="run_2",
        project_id="p1",
        goal="Infinite loop test",
        max_iterations=2,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    
    # Force state machine limit
    run.iteration_count = 2
    run = await tick_agent(run, project)
    
    assert run.current_state == AgentStatus.FAILED
    assert "Max iterations reached" in run.current_conclusion

@pytest.mark.anyio
async def test_agent_malformed_tool_call(mock_groq):
    mock_groq.side_effect = [
        {"invalid_key": "not an action"}
    ]
    project = make_dummy_project()
    run = ResearchAgentRun(
        run_id="run_3",
        project_id="p1",
        goal="Test error recovery",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    
    run = await tick_agent(run, project)
    assert run.iteration_count == 1
    assert run.observations[-1].is_error
    assert "Malformed action" in run.observations[-1].result["error"]
