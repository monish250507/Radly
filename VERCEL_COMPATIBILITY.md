# Vercel & Production Compatibility Audit

PaperBlast is fully compatible with Vercel's serverless Edge/Node architecture as well as standalone containerized environments.

---

## Architecture Guarantees

### 1. Persistence Decoupling
- **PostgreSQL / Neon / Supabase Ready**: The persistence layer (`server/engine/persistence/db_adapter.py`) dynamically selects `PostgresAdapter` when `DATABASE_URL` / `RBR_DB_URL` points to Postgres, and `SqliteAdapter` for local development.
- **Zero Global Memory Leaks**: In-memory dict caches have been completely eliminated from `pr_router.py` and `jobs.py`. All state resides durably in the database.

### 2. Execution Boundedness
- **Discrete Tick State Machine**: The Agent Orchestrator and Skeptic Arbiter execute bounded steps (`agent_runner.py` and `skeptic_runner.py`).
- **No Infinite Loops**: Strict bounds (`max_iterations` and `skeptic_max_iterations`) prevent serverless function timeouts.
- **Job Polling Flow**: Asynchronous analysis requests run through `/api/jobs/analyze` returning a `job_id`, allowing clients to poll status (`QUEUED`, `PROCESSING`, `READY`, `FAILED`) without blocking edge connections.

### 3. Subprocess & System Security
- **Safe Process Spawning**: All Git clone and diff operations use `asyncio.create_subprocess_exec` with explicit argument lists, fully compliant with hardened serverless runtimes.
- **Stateless CLI**: The CLI (`paperblast` command) interacts entirely through REST APIs (`httpx`), requiring no local shell-level access on the server.
