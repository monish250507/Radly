import json
import uuid
from datetime import datetime

from ..domain.models import (
    AgentStatus,
    ResearchAgentRun,
    ResearchProject,
    ToolObservation,
    VerificationStatus,
)
from .groq_client import call_groq_api
from .logger import paperblast_logger as logger
from .tools import TOOLS_SCHEMA, execute_tool


async def tick_skeptic(run: ResearchAgentRun, project: ResearchProject) -> ResearchAgentRun:
    """
    Executes one adversarial verification step to challenge the primary agent's conclusion.
    """
    if run.current_state != AgentStatus.WAITING_FOR_SKEPTIC:
        return run

    if run.skeptic_iterations >= run.skeptic_max_iterations:
        run.status = VerificationStatus.UNABLE_TO_VERIFY
        run.current_state = AgentStatus.COMPLETED
        run.updated_at = datetime.utcnow().isoformat() + "Z"
        return run

    run.skeptic_iterations += 1

    sys_prompt = """You are the Skeptic Verification Agent. Your job is to actively attempt to DISPROVE the primary orchestrator's conclusion using the bounded deterministic tools.
You must test:
1. Is every referenced source real?
2. Does every deterministic dependency path exist?
3. Which relationships are deterministic vs semantic?
4. Is there contradictory evidence?
5. Is the conclusion stronger than the evidence?

Output valid JSON ONLY.

To verify evidence, request a tool:
{
  "action": "tool_call",
  "tool": "ToolName",
  "arguments": {"key": "value"}
}

If you have completed your verification, output a verdict:
{
  "action": "verdict",
  "verdict": "VERIFIED" | "REJECTED" | "NEEDS_REVIEW" | "CONFLICTING_EVIDENCE" | "UNABLE_TO_VERIFY",
  "reason": "Detailed explanation of why the evidence holds or falls apart."
}
"""

    history_text = f"Goal: {run.goal}\n"
    history_text += f"Primary Orchestrator Conclusion: {run.current_conclusion}\n"
    history_text += f"Evidence Claimed: {run.evidence_refs}\n\n"
    
    history_text += "Skeptic Tool Observations:\n"
    for obs in run.skeptic_observations:
        history_text += f"- Tool [{obs.tool_id}] result: {json.dumps(obs.result)[:200]}\n"
        
    history_text += "\nAllowed Tools:\n" + json.dumps(TOOLS_SCHEMA, indent=2)
    history_text += "\n\nChallenge the conclusion. What is your next action?"

    try:
        messages = [{"role": "user", "content": history_text}]
        response = await call_groq_api(messages, system_prompt=sys_prompt, response_format_json=True)
        
        if not isinstance(response, dict):
            raise ValueError("AI returned non-JSON string")
        
        if response.get("action") == "tool_call":
            tool_name = str(response.get("tool"))
            tool_args = response.get("arguments", {})
            
            tool_id = f"skep_tool_{uuid.uuid4().hex[:6]}"
            tool_result = execute_tool(tool_name, tool_args, project)
            
            obs = ToolObservation(tool_id=tool_id, result=tool_result, is_error=False)
            run.skeptic_observations.append(obs)
            # Stay in WAITING_FOR_SKEPTIC for next tick
            
        elif response.get("action") == "verdict":
            verdict_str = response.get("verdict", "UNABLE_TO_VERIFY")
            try:
                run.status = VerificationStatus(verdict_str)
            except ValueError:
                run.status = VerificationStatus.NEEDS_REVIEW
                
            reason = response.get("reason", "")
            # Append reason to conclusion or keep it as final artifact status reason
            run.current_conclusion = f"{run.current_conclusion}\n[Skeptic Verdict: {run.status.value}] {reason}"
            
            run.current_state = AgentStatus.COMPLETED
            
        else:
            run.skeptic_observations.append(ToolObservation(
                tool_id="sys", 
                result={"error": "Malformed action. Must be 'tool_call' or 'verdict'."}, 
                is_error=True
            ))
            
    except Exception as e:
        logger.error("Skeptic tick failed", {"error": str(e)})
        run.skeptic_observations.append(ToolObservation(tool_id="sys", result={"error": str(e)}, is_error=True))

    run.updated_at = datetime.utcnow().isoformat() + "Z"
    return run
