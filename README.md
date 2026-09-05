# PaperBlast

PaperBlast is a research engineering tool designed to map code changes (Git diffs) directly to scientific impact in research manuscripts. 

Rather than relying on hallucination-prone LLM summarization, PaperBlast builds a deterministic **Provenance Graph** connecting configuration to experiments, metrics, claims, and figures. It then uses a bounded **Agent Orchestrator** and **Skeptic Verifier** to query this graph, ensuring that any claim about code impacting a paper is backed by rigid evidence.

## Architecture Diagram

```mermaid
graph TD
    subgraph Client [Frontend (Vite / React)]
        UI[Change Console UI]
        GraphView[Code Graph Viewer]
        Impact[Paper Impact Viewer]
    end

    subgraph API [Backend API (FastAPI / Vercel Serverless)]
        PRRouter[PR Router]
        JobRouter[Job Engine]
    end

    subgraph Core [PaperBlast Impact Engine]
        CodeAST[Code AST Parser]
        PaperAST[Manuscript AST Parser]
        Graph[Provenance Graph Builder]
        Agent[Agent Orchestrator]
        Skeptic[Skeptic Verifier]
    end

    UI -->|Trigger Analysis| PRRouter
    PRRouter --> JobRouter
    JobRouter --> CodeAST
    JobRouter --> PaperAST
    CodeAST --> Graph
    PaperAST --> Graph
    Graph --> Agent
    Agent <--> Skeptic
    Agent -->|Impact Report| UI
```

## Functional Requirements
- **AST Parsing:** Must extract code symbols (functions, classes, variables) from source code and map them to line numbers.
- **Document Parsing:** Must parse scientific manuscripts (PDF, TXT) into sections, claims, equations, and tables.
- **Graph Construction:** Must build a deterministic bipartite graph linking codebase symbols to manuscript components.
- **Impact Analysis:** Must orchestrate an AI agent to analyze diffs and traverse the provenance graph to determine blast radius.
- **Skeptic Verification:** Must employ an adversarial "Skeptic" agent to challenge hallucinated or unsupported impact claims.
- **Vercel Compatibility:** Must run on stateless Serverless architectures (e.g., Vercel Lambda) without local filesystem databases.

## Non-Functional Requirements
- **Performance:** End-to-end impact analysis must complete within standard serverless timeout constraints (under 30-60s depending on payload size).
- **Scalability:** Must support concurrent analysis jobs using a queued, tick-based state machine for AI agents.
- **Reliability:** Must degrade gracefully (fallback to static keyword matching) if the LLM API is unavailable.
- **Maintainability:** Codebase must be strictly typed (`mypy`) and pass a robust suite of deterministic mutation tests.

## Installation & CLI Usage
PaperBlast provides a CLI that connects to your deployed API:
```bash
python cli.py ingest https://github.com/monish250507/Research_Blast_Radius
python cli.py analyze HEAD~1..HEAD
```

## GitHub Action
You can integrate PaperBlast directly into your CI pipeline using the provided GitHub action. It runs the impact analysis on every PR and flags if a code change impacts a scientific claim without adequate verification.

## Limitations
- **Language Support**: Currently heavily optimized for Python AST parsing.
- **Verification**: The Skeptic agent can only verify evidence that is deterministically traceable in the graph. It cannot verify undocumented manual data transformations.

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up the Vercel local dev environment and run the test suite.

## Security
See [SECURITY.md](SECURITY.md) for our RBAC model and prompt injection mitigations.
