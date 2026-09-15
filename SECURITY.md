# Security Policy

## Reporting a Vulnerability
If you discover a security vulnerability in Radly, please report it via GitHub Security Advisories. Do not open a public issue.

## Threat Model
Radly analyzes potentially untrusted code and manuscripts. 
- **Code Execution**: The Python AST parser operates statically. It does not `eval()` or execute untrusted code.
- **Prompt Injection**: All user input (diffs, paper text) is strictly parameterized into bounded tool schemas. The orchestrator cannot run arbitrary commands.
- **IDOR**: Authorization is enforced entirely server-side via `require_role()` dependency injection. JWT tokens or secure session IDs are required for all persistent actions.
