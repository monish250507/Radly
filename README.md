# PaperBlast

PaperBlast is a research engineering tool designed to map code changes (Git diffs) directly to scientific impact in research manuscripts. 

Rather than relying on hallucination-prone LLM summarization, PaperBlast builds a deterministic **Provenance Graph** connecting configuration to experiments, metrics, claims, and figures. It then uses a bounded **Agent Orchestrator** and **Skeptic Verifier** to query this graph, ensuring that any claim about code impacting a paper is backed by rigid evidence.

## Architecture
See [ARCHITECTURE.md](ARCHITECTURE.md) for a deep dive into the Bipartite Graph, the Agent State Machine, and the Skeptic Arbiter layer.

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
