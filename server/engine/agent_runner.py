import json
import uuid
from datetime import datetime, timezone

from ..domain.models import (
    AgentStatus,
    ResearchAgentRun,
    ResearchProject,
    ToolCall,
    ToolObservation,
    VerificationStatus,
)
from .groq_client import call_groq_api
from .logger import paperblast_logger as logger
from .tools import TOOLS_SCHEMA, execute_tool


async def tick_agent(run: ResearchAgentRun, project: ResearchProject, call_groq_fn=None) -> ResearchAgentRun:
    """
    Executes one step of the bounded agent state machine.
    """
    if run.current_state in [AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED, AgentStatus.NEEDS_REVIEW]:
        return run
        
    if run.iteration_count >= run.max_iterations:
        run.current_state = AgentStatus.FAILED
        run.current_conclusion = "Max iterations reached without conclusion."
        run.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return run

    run.current_state = AgentStatus.RUNNING
    run.iteration_count += 1
    
    # Build strict context
    sys_prompt = """You are a Research Orchestration Agent. Your job is to answer the user's research goal using the deterministic tools provided.
You CANNOT invent evidence or fabricate nodes. You must rely purely on the tools.
Output valid JSON ONLY.

If you need more info, output:
{
  "action": "tool_call",
  "tool": "ToolName",
  "arguments": {"key": "value"}
}

If you have sufficient evidence to conclude, output:
{
  "action": "conclude",
  "conclusion": "Explanation...",
  "status": "VERIFIED" | "UNABLE_TO_VERIFY" | "NEEDS_REVIEW" | "CONFLICTING_EVIDENCE",
  "evidence_refs": ["art_123", "ev_456"]
}
"""
    
    # Build conversation history from observations
    history_text = f"Goal: {run.goal}\n\nPast Observations:\n"
    for obs in run.observations:
        history_text += f"- Tool [{obs.tool_id}] result: {json.dumps(obs.result)[:200]}\n"
        
    history_text += "\nAllowed Tools:\n" + json.dumps(TOOLS_SCHEMA, indent=2)
    history_text += "\n\nWhat is your next action?"

    try:
        messages = [{"role": "user", "content": history_text}]
        llm_fn = call_groq_fn or call_groq_api
        response = await llm_fn(messages, system_prompt=sys_prompt, response_format_json=True)
        
        if not isinstance(response, dict):
            raise ValueError("AI returned non-JSON string")
        
        if response.get("action") == "tool_call":
            tool_name = str(response.get("tool"))
            tool_args = response.get("arguments", {})

            tool_id = f"tool_{uuid.uuid4().hex[:6]}"
            tc = ToolCall(tool_id=tool_id, name=tool_name, arguments=tool_args)
            run.tool_calls.append(tc)
            
            # Execute deterministic tool
            tool_result = execute_tool(tool_name, tool_args, project)
            
            obs = ToolObservation(tool_id=tool_id, result=tool_result, is_error=False)
            run.observations.append(obs)
            run.current_state = AgentStatus.WAITING_FOR_TOOL # Basically ready for next tick
            
        elif response.get("action") == "conclude":
            run.current_conclusion = response.get("conclusion")
            
            status_str = response.get("status", "UNABLE_TO_VERIFY")
            try:
                run.status = VerificationStatus(status_str)
            except ValueError:
                run.status = VerificationStatus.NEEDS_REVIEW
                
            run.evidence_refs = response.get("evidence_refs") or response.get("evidence") or []
            run.current_state = AgentStatus.WAITING_FOR_SKEPTIC
            
        else:
            # Malformed
            run.observations.append(ToolObservation(
                tool_id="sys", 
                result={"error": "Malformed action returned. Must be 'tool_call' or 'conclude'."}, 
                is_error=True
            ))
            
    except Exception as e:
        logger.error("Agent tick failed", {"error": str(e)})
        run.observations.append(ToolObservation(tool_id="sys", result={"error": str(e)}, is_error=True))

    run.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return run
