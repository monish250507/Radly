# PaperBlast Architecture

PaperBlast operates entirely via a Serverless Vercel Backend (FastAPI). 

## 1. Provenance Graph (`engine/graph_builder.py`)
The foundation of PaperBlast is a deterministic bipartite graph. It maps Code artifacts (Configs, Data Pipelines) to Experiments, which emit Results, which link to Paper Artifacts (Metrics, Tables, Claims).

## 2. Agent Orchestrator (`engine/agent_runner.py`)
The LLM is NOT the source of truth. It is a tool-using director. The orchestrator receives a goal (e.g. "What happens if I change learning_rate?"), issues deterministic tool calls (e.g. `CodeSearch`, `GraphTraversal`), and collects observations. 

## 3. Skeptic Verifier (`engine/skeptic_runner.py`)
Before a conclusion is finalized, an adversarial Skeptic agent reviews the evidence. It actively tries to disprove the primary orchestrator by looking for contradictory config or weak semantic matches. Only if the evidence holds up does the conclusion become `VERIFIED`.

## 4. Collaboration & Identity (`engine/collaboration.py`)
State is fully durable. We use strict RBAC models (`OWNER`, `MAINTAINER`, `RESEARCHER`, `VIEWER`) backed by a Database Adapter interface. Guest analysis can be seamlessly migrated into persistent Research Projects.
