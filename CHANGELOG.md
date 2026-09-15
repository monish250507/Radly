# Changelog

All notable changes to Radly will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-05

### Added
- **P1 Implementation Complete**: Full end-to-end impact tracing pipeline.
- Real PDF (`pypdf`), DOCX (`python-docx`), and LaTeX document adapters with strict extraction status mapping.
- Real Git repository tracking for Research PRs via GitHub ZIP endpoints.
- New `ChangeConsole` replacing the legacy `WhatIfConsole` with a streamlined UX.
- New `ImpactHeader` replacing `BlastRadiusHeader`, emphasizing explicit verification statuses over arbitrary percentages.
- `App.jsx` redesigned with dedicated Researcher Tabs (Overview, Changes, Paper Impact, Experiments).
- Developer Mode added to gate technical internals (Code AST, Agent Trace, Lineage Graph).
- Production-grade rate limiting (sliding window) and 10MB request size guards in FastAPI.

### Changed
- Removed simulated `asyncio.sleep(1)` job execution; jobs now track real AST/document analysis stages.
- AST `SyntaxError` now strict: returns `EXTRACTION_FAILED` sentinel instead of silently failing over to regex heuristics.
- AI lineage graph generation constrained: AI now operates as a semantic mapper, while final verification demands deterministic source edges.

### Fixed
- Fixed Vercel routing where `/api/*` was directed to a missing Node.js `index.js` file; backend is now properly mapped to FastAPI `main.py`.

## [1.0.0] - 2026-08-21
- Initial public release of Radly prototype.
