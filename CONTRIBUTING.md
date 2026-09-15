# Contributing to PaperBlast

Welcome to **PaperBlast**! We are thrilled that you are interested in contributing. PaperBlast is an open-source, dual-agent research blast-radius engine that detects how modifications to machine learning codebases propagate to claims, equations, and tables in scientific research papers.

Whether you're fixing a bug, adding support for a new programming language AST, building a new paper format adapter, or improving documentation, your contributions are warmly welcomed.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started & Local Development](#getting-started--local-development)
3. [Architecture Overview & Extension Guide](#architecture-overview--extension-guide)
   - [Adding Language AST Parsers](#1-adding-language-ast-parsers)
   - [Adding Document Adapters](#2-adding-document-adapters)
   - [Adding Agent & Skeptic Tools](#3-adding-agent--skeptic-tools)
   - [Extending Persistence Adapters](#4-extending-persistence-adapters)
4. [Testing & Quality Assurance](#testing--quality-assurance)
5. [Code Style & Best Practices](#code-style--best-practices)
6. [Pull Request Workflow](#pull-request-workflow)

---

## Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for everyone, regardless of experience level, gender, sexual orientation, disability, ethnicity, or religion.

- **Be respectful and constructive** in code reviews, discussions, and issue comments.
- **Focus on grounded verification**: PaperBlast is designed to eliminate hallucinations in scientific code review. Keep this precision mindset in your contributions.

---

## Getting Started & Local Development

### Prerequisites

- **Python**: 3.11 or 3.12
- **Node.js**: 18 or 20+ (LTS recommended)
- **Git**: 2.30+
- **Groq API Key**: (Optional for unit tests; required for live AI synthesis)

### Step-by-Step Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/<your-username>/Research_Blast_Radius.git
   cd Research_Blast_Radius
   ```

2. **Set Up Python Virtual Environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   npm install
   ```

4. **Configure Environment Variables**:
   Copy the provided `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to include your configuration:
   ```env
   RBR_DB_URL=sqlite+pysqlite:///./rbr_local.db
   RBR_LLM_PROVIDER=groq
   RBR_LLM_MODEL=openai/gpt-oss-120b
   RBR_LLM_API_KEY=your_groq_api_key_here
   RBR_LLM_TEMPERATURE=0.0
   RBR_LOG_LEVEL=INFO
   ```

5. **Run the Development Servers**:
   ```bash
   # Option A: Single command (runs both backend and frontend)
   npm run dev:all

   # Option B: Run in separate terminals
   # Terminal 1 (FastAPI Backend on port 5000):
   npm run dev:server

   # Terminal 2 (Vite React Client on port 3000):
   npm run dev
   ```

6. **Verify Installation**:
   Open your browser to:
   - Frontend UI: `http://localhost:3000`
   - API Documentation (Swagger): `http://localhost:5000/api/docs`
   - API Health Check: `http://localhost:5000/api/health`

---

## Architecture Overview & Extension Guide

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

### 1. Adding Language AST Parsers
Located in [`server/engine/code_parser.py`](file:///c:/Users/Nevan/Desktop/pb/server/engine/code_parser.py):
- Implement an extraction function (e.g. `parse_rust_ast(code, file_path)`) that returns a list of normalized symbol dictionaries:
  ```python
  {
      "symbol": "learning_rate",
      "type": "Variable" | "Function" | "Class" | "ConfigKey",
      "value": "0.001",
      "file": file_path,
      "line": 42,
      "col_offset": 0,
      "source_text": "let learning_rate = 0.001;"
  }
  ```
- Register the file extension in `extract_code_symbols()`.
- Add unit tests in `server/tests/test_code_parser.py`.

### 2. Adding Document Adapters
Located in [`server/engine/paper_parser.py`](file:///c:/Users/Nevan/Desktop/pb/server/engine/paper_parser.py):
- Support new formats (e.g. Typst, ePUB, HTML) by adding an extractor in `extract_text_from_document()` that returns raw text or an AST.
- Ensure sections, equations (`$`, `$$`), and tables are indexed.
- Add unit tests in `server/tests/test_paper_parser.py`.

### 3. Adding Agent & Skeptic Tools
Located in [`server/engine/tools.py`](file:///c:/Users/Nevan/Desktop/pb/server/engine/tools.py), [`agent_runner.py`](file:///c:/Users/Nevan/Desktop/pb/server/engine/agent_runner.py), and [`skeptic_runner.py`](file:///c:/Users/Nevan/Desktop/pb/server/engine/skeptic_runner.py):
- Tools must define an explicit JSON Schema in `TOOL_DEFINITIONS`.
- Implement deterministic dispatch functions that operate on the `ResearchProject` artifact index.
- Add tool execution tests in `server/tests/test_agent.py` and `server/tests/test_skeptic.py`.

### 4. Extending Persistence Adapters
Located in [`server/engine/persistence/db_adapter.py`](file:///c:/Users/Nevan/Desktop/pb/server/engine/persistence/db_adapter.py):
- All database adapters inherit from `DatabaseProvider`.
- Currently implemented: `InMemoryAdapter`, `SqliteAdapter`, and `PostgresAdapter`.
- Always use parameterized queries (never raw string concatenation) to prevent SQL injection.

---

## Testing & Quality Assurance

PaperBlast maintains a rigorous automated test suite. **All pull requests must pass 100% of the test suite before being merged.**

### Running Tests

```bash
# Run the complete test suite
pytest server/tests/ -v

# Run the bulletproof reliability & stress test suite
pytest server/tests/test_bulletproof.py -v

# Run real-world live integration test (tests live GitHub clone & arXiv PDF)
python scripts/test_real_world.py
```

### Testing Rules
1. **Deterministic by Default**: Unit and pipeline tests must not require a live network connection or paid API keys. Use `unittest.mock.patch` for LLM calls (`call_groq_api`).
2. **Isolated Database State**: Tests using `SqliteAdapter` must write to temporary directories (`tempfile.TemporaryDirectory()`).
3. **No Flaky Tests**: Tests must pass consistently regardless of execution order or timing.

---

## Code Style & Best Practices

- **Python**: Follow PEP 8 style guidelines. Type hints are required for all function arguments and return values.
- **Timezone-Aware Datetimes**: **Never** use deprecated `datetime.utcnow()`. Always use:
  ```python
  from datetime import datetime, timezone
  now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
  ```
- **JWT Key Length**: Per RFC 7518 Section 3.2, HMAC-SHA256 secret keys must be at least 32 bytes (256 bits).
- **Security**: Never log sensitive credentials or API keys. Always use `require_role(Role)` for project endpoints.

---

## Pull Request Workflow

1. **Branch Naming**:
   - Features: `feat/add-rust-parser`
   - Bug Fixes: `fix/sqlite-concurrent-lock`
   - Documentation: `docs/contributing-guide`
   - Performance: `perf/paper-regex-speedup`

2. **Commit Messages**:
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(parser): add AST extraction support for Rust source files`
   - `fix(auth): enforce 32-byte minimum secret key length for HMAC-SHA256`
   - `docs(readme): add Docker Compose quickstart section`

3. **PR Submission Checklist**:
   - [ ] Created a descriptive branch from `main`.
   - [ ] All 136+ unit and bulletproof tests pass (`pytest server/tests/ -v`).
   - [ ] No deprecation warnings or unhandled exceptions.
   - [ ] New functionality is accompanied by new unit tests.
   - [ ] Updated documentation or docstrings where applicable.
   - [ ] No secrets or personal API keys committed.

Thank you for helping make PaperBlast the definitive open-source standard for research code impact analysis!
