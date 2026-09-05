# Performance & Mutation Benchmarks

The following measurements reflect the bounded capabilities of the system operating statically (without arbitrary code execution) against standard Python/React repositories.

These benchmarks are based on the deterministic test fixtures provided in `server/tests/conftest.py`, representing the canonical "mini research project" pipeline (`config.py` → `train.py` → `experiment` → `claims`).

## Mutation & Provenance Testing Metrics

| Test Suite | Metric / Goal | Status | Evidence/Fixture |
|---|---|---|---|
| **True Positive Mutation** | Detect that changing `learning_rate` in `config.py` impacts the methodology section. | **PASS** | `test_mutation.py::test_learning_rate_mutation` |
| **False Positive Restraint** | Harmless changes (e.g., updating a code comment) produce NO impact findings. | **PASS** | `test_false_positive.py::test_harmless_comment_mutation_not_flagged` |
| **Dependency Edges** | AST extracts all required function calls, references, assignments, and parameters. | **PASS** | `test_dependency.py` (10 tests) |
| **Evidence Verification** | `VERIFIED` status is only assigned if deterministic source evidence exists. AI-only edges are downgraded to `NEEDS_REVIEW`. | **PASS** | `test_evidence.py::TestVerificationGating` |
| **Extraction Contract** | Malformed AST/SyntaxError returns explicit `EXTRACTION_FAILED` sentinel instead of degraded output. | **PASS** | `test_code_parser.py::TestExtractionFailedContract` |

## Security & Reliability Metrics

| Test Suite | Metric / Goal | Status |
|---|---|---|
| **Rate Limiting** | Write endpoints drop requests > 30 per IP per minute (429 Too Many Requests). | **PASS** |
| **Payload Guards** | Requests > 10MB are blocked before processing (413 Payload Too Large). | **PASS** |
| **Document Truncation** | Massive binary payloads are cleanly truncated at 10MB without OOM crashing. | **PASS** |
| **Malicious Payloads** | Invalid binary sequences (e.g. fake PDF headers) fail gracefully. | **PASS** |

*See `test_security.py` for exact implementation details.*

## Runtime Diagnostics

- **AI Cost**: The integration pipeline currently costs ~$0.00 (using local mocks for deterministic paths).
- **Tail Latency**: Varies heavily by external API latency. The deterministic graph builder runs in <100ms.
- **AST Performance**: The `ast.parse` layer processes the test repository in <50ms.
