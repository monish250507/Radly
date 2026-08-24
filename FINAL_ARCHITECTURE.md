# Final PaperBlast Architecture

PaperBlast fundamentally shifts research reproduction from a manual verification process to an automated, deterministic pipeline managed by agentic state machines.

## 1. Provenance Graph (Deterministic Core)
At the base level, PaperBlast builds a strict Bipartite Provenance Graph. It maps Code configurations (`learning_rate`, `batch_size`) directly to the numerical results in Paper Tables/Figures.

## 2. Execution Layer
- **Mode**: The system explicitly operates in `PREDICTED` mode currently because it lacks a heavy sandbox (e.g. gVisor, Docker) within the Vercel execution context.
- **Rule**: "Never claim deterministic reproduction unless the environment supports it." Without safe execution, the engine sets status to `EXECUTION_UNAVAILABLE`.

## 3. Agent Orchestrator & Skeptic Arbiter
- The LLM acts purely as an Orchestrator over the Deterministic Core.
- The Orchestrator gathers evidence via bounded tools (`ASTQuery`, `PaperSearch`).
- Before any conclusion is presented, the **Skeptic Arbiter** receives the conclusion and attempts to disprove it by verifying if the evidence is factual or merely a semantic hallucination.

## 4. Collaborative Persistence (Identity & Research PRs)
- **Role-Based Access Control**: `OWNER`, `MAINTAINER`, `RESEARCHER`, `REVIEWER`, `VIEWER`.
- **Database Adapter**: The persistence layer is an asynchronous interface ready for Postgres, completely abstracted away from local process-global memory.
- **Research PRs**: Attach a Git diff to an agent analysis, enabling rigorous Peer Review of the scientific consequences of a code change before merging.
