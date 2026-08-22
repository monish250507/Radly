# PaperBlast — Architecture Audit (Pre-Migration Baseline)

Date: 2026-08-22
Scope: full inspection of the live codebase (`api/`, `server/`, `client/`, configs) plus recorded baseline runs on Node v22.17.0, npm 11.13.0, Vercel CLI 59.1.3.
Method: every claim below was verified by reading the source file cited or by executing the check locally. Nothing is assumed from documentation.

---

## 1. Complete Current Architecture

```
Browser (React 18 SPA, Vite dev server :3000)
   │  fetch('/api/...')            (dev: Vite proxy → localhost:5000; prod: Vercel rewrite)
   ▼
Vercel rewrite /api/(.*) → api/index.js          ← serverless entry (re-exports Express app)
   │
   ▼
server/index.js  — single Express app (also runnable standalone via `npm run server` on :5000)
   ├── POST /api/ingest-github   → git clone --depth 1 into os.tmpdir() scratch,
   │                               fallback: codeload.github.com ZIP × branches main|master|dev
   │                               → server/codeParser.js (regex symbol extraction)
   ├── POST /api/parse-paper     → server/paperParser.js (pdf-parse / mammoth / JSZip + regex AST)
   ├── POST /api/analyze-impact  → server/impactEngine.js
   │                                 ├─ deterministic symbol↔section/equation matcher (always runs)
   │                                 └─ server/groqClient.js (Groq chat completions, temp 0.0,
   │                                    model chain groq/compound → qwen/qwen3.6-27b → openai/gpt-oss-120b;
   │                                    any failure ⇒ static reachability fallback result)
   ├── GET  /api/health          → status + groqConfigured flag
   └── GET  *                    → serves ../dist/index.html when built (standalone mode)

client/src/App.jsx — the only component that calls the API (via safeFetchJson helper);
                     all other components (BlastRadiusHeader, WhatIfConsole, CodeGraphViewer,
                     PaperImpactViewer, DependencyFlow) are purely presentational.
State: entirely client-side React useState. No database. No persistence layer anywhere.
```

Untracked leftovers from the deleted Python implementation remain **on local disk only**
(`src/rbr/**`, `tests/**`, `scripts/**`, `.venv/`, `.coverage`, stale `__pycache__`). They are not
part of the repository and are ignored for this audit.

## 2. Real Execution Flow (verified end-to-end)

1. User pastes repo URL → `POST /api/ingest-github {repoUrl}` → clone-or-zip → `extractCodeSymbols()` → `{success, repo, fileCount, files[], symbols[]}` → stored in `useState(codeSymbols)`.
2. User uploads PDF/text → `POST /api/parse-paper {paperText | paperFileBase64+fileType}` → `extractTextFromDocument()` → `parsePaperStructure()` → `{success, paperAST}` → `useState(paperAST)`.
3. User enters change query → `POST /api/analyze-impact {codeSymbols, paperAST, query}` → static matching always computed first → Groq synthesis attempted → sanitized/fallback result `{analysis}` → rendered across 5 tabs; exportable as client-generated JSON report.
4. Errors surface as a dismissible banner fed by `safeFetchJson` in App.jsx.

## 3. Existing APIs

| Route | Method | Input (verified from code) | Output | Status |
|---|---|---|---|---|
| `/api/ingest-github` | POST | `{repoUrl}` or `{codeFiles:[{name,content}]}` | `{success, repo, fileCount, files[], symbols[]}` | URL path works; direct-files path broken (see §8) |
| `/api/parse-paper` | POST | `{paperText}` or `{paperFileBase64, fileType}` | `{success, extractedLength, paperAST}` | works |
| `/api/analyze-impact` | POST | `{codeSymbols[], paperAST{sections,equations,tables}, query}` | `{success, analysis}` | works incl. no-key fallback |
| `/api/health` | GET | – | `{status:'OK', service, timestamp, groqConfigured}` | works |

Validation is ad-hoc per route (inline `if (!x) return res.status(400)`); error responses are `{error: string}` with no error code/type taxonomy.

## 4. Existing Data Structures

**ASTSymbol** (codeParser.js): `{symbol, type: 'Class'|'Function'|'Variable'|'ClassVariable (X)'|'ConfigKey', value, line, file}`.

**PaperAST** (paperParser.js): `{rawText, sections[{id 'sec-N-slug', title, content[], startLine, endLine, text}], equations[{id 'eq-N', label, content, raw, type}], tables[{id 'table-N', label, caption, content, type:'latex'|'markdown'}], numbers[{value, index}]}`.

**Analysis** (impactEngine.js): `{overall_impact_score, risk_level CRITICAL|HIGH|MAJOR|MINOR|NONE, confidence_score, execution_time_ms, cost_efficiency{tokens_used_est, estimated_cost_usd, hardware_accelerator}, impact_summary{sections_affected, equations_affected, tables_affected}, affected_sections[{section_id,title,risk,confidence,reason,current_text,suggested_text}], affected_equations[], affected_tables[], lineage_graph[{source,target,relationship}], agent_collaboration_trace[{agent,role,output_summary}]}`.

Notes:
- There is **no explicit status field** on analysis results; callers cannot distinguish AI-synthesized vs fallback results except via `cost_efficiency.hardware_accelerator` prose.
- `cost_efficiency.tokens_used_est` is a hardcoded constant (`1280`) in the AI path — a fabricated-looking metric presented to users as an audit number.
- Default confidences are hardcoded (92/94/88).

## 5. Existing Production Risks

1. **Broken feature in production**: direct code-file upload 500s (§8). 
2. **Weak GitHub URL validation**: regex `github\.com\/` substring-matches `notgithub.com`; bad hosts fall through to ~30s clone timeout + up to 3×6s ZIP attempts before returning 404 — inside one synchronous serverless request.
3. **Synchronous long requests**: analyze-impact can chain up to 3 sequential Groq HTTP calls per request; ingestion may spend 30s cloning. No `maxDuration` configured in vercel.json/api.
4. **Body limit mismatch**: Express allows 50 MB JSON but Vercel enforces ≈4.5 MB request body; client patches over this with a 413-specific message (App.jsx safeFetchJson).
5. **GROQ_API_KEY read once at module load** (groqClient.js:4); missing key still issues 3 doomed network calls per analysis instead of short-circuiting.
6. **Model IDs unverified**: the fallback chain includes `qwen/qwen3.6-27b` / `openai/gpt-oss-120b`; if these are not valid Groq-hosted models each analysis pays extra failed-call latency before reaching a working model.
7. **Fabricated-looking metrics**: fixed token estimates and default confidence scores presented as measurements (honesty risk for a provenance product).
8. **No centralized error handling/logging/correlation**: per-route try/catch, `console.*` only; incidents cannot be traced across log lines.
9. **`app.get('*')` + static serving** duplicated between standalone mode and Vercel rewrites — two SPA-fallback mechanisms that must be kept consistent.
10. Build warning: `vite build` does not empty `dist/` (stale assets can survive builds).
11. npm audit: 32 vulnerabilities reported at install (1 critical) — not remediated here; flagged for later.

## 6. Existing Vercel Constraints (as they bind this codebase)

- Stateless request/response functions only; the app already keeps no durable state (scratch dir under `os.tmpdir()` is ephemeral — acceptable, used transiently).
- No long-running process: standalone `app.listen` correctly gated behind `!process.env.VERCEL` (server/index.js:263).
- Request size cap (~4.5 MB) < Express 50 MB limit (risk #4).
- Function duration caps make the 30 s clone + multi-fetch fallback path fragile without `maxDuration`.
- Subprocess use (`git clone`) depends on the function image shipping a git binary — must be verified against the deployed runtime before relying on Strategy 1 there; ZIP fallback already covers its absence.

## 7. Existing Tests

None. The Node codebase has zero tests and zero test tooling (`npm test` has no script). The old Python suite was removed from the repo in commit history and survives only as untracked disk leftovers.

## 8. Recorded Baseline (executed 2026-08-22)

| Check | Result |
|---|---|
| `npm run build` (frontend) | PASS — 36 modules, 3.11 s; warning: outDir not emptied |
| `npm run lint` | NO SCRIPT — no linter configured |
| `npm test` | NO SCRIPT — no tests exist |
| `vercel build` | SKIPPED — requires project link/auth (`vercel pull`/VERCEL_TOKEN) unavailable locally; deliberately not faked |
| Boot server + `GET /api/health` | PASS — `groqConfigured:false` (no GROQ_API_KEY locally) |
| `POST /api/parse-paper` | PASS — sections/equations extracted correctly |
| `POST /api/ingest-github` (repo URL, real network) | PASS — 19 files, 6883 symbols from this repo |
| `POST /api/ingest-github` (direct codeFiles) | **FAIL (pre-existing)** — 500 `ERR_INVALID_ARG_TYPE`; client sends `{name,content}`, parser reads `file.path` (codeParser.js:14 via index.js:67) |
| `POST /api/analyze-impact` | PASS — documented static-reachability fallback after 3× Groq 401 (key absent), 1.43 s |
| Invalid-host ingest | Returns 404 after ~50 s of wasted retries (risk #2) |

Integration checks requiring secrets, skipped honestly:
- **GROQ_API_KEY** unavailable locally → real LLM synthesis path NOT exercised here; only its absence-path (fallback) was. It is exercised in the deployed environment where the key exists.
- **vercel build/dev** require Vercel auth/link — skipped locally, not simulated.

## 9. Proposed Migration Boundaries

Minimum structural foundation only — no behavior/product changes:

| CURRENT COMPONENT | CURRENT RESPONSIBILITY | CURRENT PROBLEM | TARGET RESPONSIBILITY | MIGRATION STRATEGY |
|---|---|---|---|---|
| Per-route try/catch (index.js) | Ad-hoc 500s | Duplicated, inconsistent, opaque | Centralized error middleware + typed AppError | Add `server/errors.js`, wrap routes, keep response shape `{error}` superset-compatible |
| console.* scattered | Logging | Unstructured, uncorrelatable | Structured JSON logs w/ levels | Add `server/logger.js`; replace call sites mechanically |
| none | Request tracing | Impossible to correlate | Correlation ID per request (`x-request-id`), echoed in responses/logs | Middleware assigns/propagates ID; threads through logger context |
| implicit success/error | Analysis outcome signal | Fallback invisible to clients | Explicit `status` + `engine.mode` on analysis payloads | impactEngine tags output (`ai_synthesized`\|`static_fallback`); additive fields only |
| health endpoint | Ping | No version/env info | Version/build/environment exposure | Add `server/versionInfo.js` sourced from package.json + env |
| inline env reads (PORT, GROQ key at module load) | Config | Scattered; key read eagerly | Single `server/config.js`; lazy key access; explicit missing-config errors | Routes/services import config object |
| monolith index.js | Routing+ingestion+parsing | Mixed concerns | Thin routing layer delegating to service modules | Extract handlers into `server/routes/*.js` incrementally; engine/parser modules untouched |
| dev/prod blur | Runtime detection | Ad-hoc `process.env.VERCEL` checks | Explicit `config.env` (`development`\|`production`) derived once | Consumed by logger verbosity + error detail policies |

Non-goals for this stage: job/workflow system, persistence layer, new features, UI changes beyond nothing user-facing, dependency upgrades.

## 10. Exact Files Modified/Added in This Stage

Added:
- `docs/ARCHITECTURE_AUDIT.md` (this file)
- `server/config.js`
- `server/logger.js`
- `server/errors.js`
- `server/middleware/requestContext.js`
- `server/middleware/errorHandler.js`
- `server/versionInfo.js`

Modified (minimal, behavior-preserving):
- `server/index.js` — wire middleware + central error handler; routes delegate unchanged logic
- `server/groqClient.js` — lazy env read + structured logging + short-circuit when key missing
- `server/impactEngine.js` — additive `status`/`engine.mode` fields; logger swap
- `package.json` — version metadata consumed by versionInfo (no script changes required yet)

Explicitly deferred to later stages (recorded so future work has a map):
- Fix for direct-file upload contract bug (needs decision: normalize `{name}`→`path` server-side vs change client payload)
- URL validation hardening + retry-budget trimming
- Test harness selection and first regression tests (baseline §8 becomes the reference)
- `maxDuration` / route-level timeouts for serverless safety
- Job abstraction for heavy work; persistence boundary design
