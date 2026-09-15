# PaperBlast System Architecture

PaperBlast bridges machine learning codebases and scientific paper manuscripts by transforming code changes into verifiable impact assessments against published equations, tables, and claims.

```
┌────────────────────────────────────────────────────────┐
│                   Frontend (React + Vite)              │
│       Code Ingest ──► Paper Parse ──► Blast Radius     │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP JSON API
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Server                      │
│        Rate Limiter • Auth Guards • Async Jobs         │
├───────────────────────────┬────────────────────────────┤
│   AST Code Parser         │    Paper Structure Parser  │
│   (Python AST, JS, Config)│    (PDF, LaTeX, Markdown)  │
├───────────────────────────┴────────────────────────────┤
│              Dual-Agent Impact Engine                  │
│       Agent Runner (Search/Trace) ◄──► Skeptic Arbiter │
├────────────────────────────────────────────────────────┤
│                 Provenance Graph                       │
│    Deterministic Artifact Tracing (Code ➔ Paper)       │
├────────────────────────────────────────────────────────┤
│                Durable Persistence Layer               │
│        SQLite (Local Dev)  /  PostgreSQL (Prod)        │
└────────────────────────────────────────────────────────┘
```

---

## Core Subsystems

### 1. Deterministic AST Code Parser (`server/engine/code_parser.py`)
- **Multi-Language Parsing**: Traverses Python source files via `ast.NodeVisitor`, JavaScript/TypeScript variable definitions, and JSON/YAML configuration keys.
- **Fail-Safe Sentinel Isolation**: Syntax errors and corrupt files produce `EXTRACTION_FAILED` sentinels rather than unverified heuristic guesses. Sentinels are strictly quarantined and filtered out from downstream verification.
- **Size Bounds**: Files exceeding 5 MB are automatically bypassed to protect parser performance.

### 2. Multi-Format Document Extraction (`server/engine/paper_parser.py`)
- **Adapter Pipeline**: Handles PDF (`pypdf`), Word (`docx`), LaTeX, and plain text.
- **Structural Decomposition**: Segments papers into numbered sections, LaTeX math equations (`$`, `$$`, `\begin{equation}`), Markdown/LaTeX tables, and numerical scientific claims.
- **Content Hashing**: SHA-256 hashes generated for every extracted section to detect manuscript modifications and staleness.

### 3. Dual-Agent Orchestration & Skeptic Hard-Gating (`server/engine/impact_engine.py`)
- **Primary Agent Orchestrator (`agent_runner.py`)**: Executes bounded iterations over the artifact index using deterministic tools (`CodeSearch`, `ASTQuery`, `PaperSearch`, `GraphTraversal`).
- **Adversarial Skeptic Arbiter (`skeptic_runner.py`)**: Intercepts proposed conclusions to actively test for contradictions or weak semantic correlations.
- **Authoritative Gating Rules**:
  - `REJECTED`: Skeptic rejections hard-demote findings to `REJECTED` or `UNABLE_TO_VERIFY`. A rejected finding can **never** surface as `VERIFIED`.
  - `CONFLICTING_EVIDENCE`: Propagates to flag contradictory parameter values.
  - `NEEDS_REVIEW`: Demotes unproven claims lacking deterministic code evidence.
  - `VERIFIED`: Permitted only when backed by verified AST source evidence.

### 4. Bipartite Provenance Graph (`server/engine/provenance_graph.py`)
- **Deterministic Edge Mapping**: Links code hyperparameter symbols to downstream experiment runners, tables, and manuscript claims.
- **Multi-Hop Data-Flow**: Traces variable assignments and call hierarchies across multiple files to calculate the true blast radius of a code modification.

### 5. Multi-Tier Durable Persistence (`server/engine/persistence/db_adapter.py`)
- **Provider Interface (`DatabaseProvider`)**:
  - `SqliteAdapter`: Production local storage (`rbr_local.db`) with WAL mode, foreign keys, and multi-worker isolation.
  - `PostgresAdapter`: Production cloud SQL via `asyncpg` for PostgreSQL / Supabase deployments.
  - `InMemoryAdapter`: Isolated adapter for fast unit testing.
- **Full Entity Durability**: Research PRs, peer review comments, review verdicts, asynchronous background jobs, analysis versions, and evidence domain records survive process restarts.

### 6. Authentication & Role-Based Access Control (`server/engine/auth.py`)
- **Cryptographic Security**: HMAC-SHA256 (`HS256`) signed JWT tokens using minimum 32-byte secret keys per RFC 7518 Section 3.2.
- **Claims Enforcement**: Strict validation of issuer (`iss`), audience (`aud`), expiration (`exp`), and issued-at (`iat`).
- **Role Hierarchy**: Enforces granular permissions (`OWNER` > `MAINTAINER` > `RESEARCHER` > `REVIEWER` > `VIEWER`).
