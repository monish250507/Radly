# Known Limitations

## 1. Execution Sandboxing
Radly is currently a purely static analysis tool backed by a deterministic graph and LLM agent orchestration. Because we operate in an isolated environment without heavy VM capabilities, **safe execution of arbitrary research code is not available**.
- The system returns `EXECUTION_UNAVAILABLE` rather than attempting to `eval()` or unsafely run shell scripts.
- All numerical impact analyses are strictly marked `PREDICTED`, never `OBSERVED_BY_EXECUTION`.

## 2. Supported Inputs
- The AST parser is optimized for standard Python (`.py`) and React/JS (`.ts`, `.tsx`, `.js`). Other languages (C++, R, Go) fall back to simplistic line-level parsing.
- Manuscript parsing currently relies on plain text extraction. Complex PDF rendering artifacts (e.g. nested sub-tables) may occasionally fail to link to the provenance graph.

## 3. Tool Bounds
- If the required evidence takes more than `max_iterations` tools to uncover (e.g., deeply convoluted pointer arithmetic in legacy codebases), the Agent will abort and return `UNABLE_TO_VERIFY`.
