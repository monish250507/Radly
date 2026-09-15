# Radly: Project Summary Writeup

> **Submission Summary** (Under 200 Words)

```text
Problem: Machine learning codebases and paper manuscripts rapidly desynchronize during research iteration. Hyperparameter changes (like LoRA rank r or loss scaling tau) silently invalidate paper parameter budgets, math formulations, and benchmark tables, causing reproducibility failures and broken peer reviews.

Agent Architecture: Radly uses a dual-agent pipeline over a real-time bipartite AST graph G = (V_code ∪ V_paper, E_deps):
1. Code AST Parser (code_parser.py): Shallow-clones repositories to index line-level AST symbols and function hierarchies.
2. Manuscript Analyst (paper_parser.py): Extracts structural sections, equations, and tables across PDF, DOCX, and LaTeX.
3. Dual-Agent Engine (impact_engine.py): Primary Agent Orchestrator traverses the artifact graph while an adversarial Skeptic Arbiter hard-gates claims to eliminate hallucinations and synthesize verified impact findings.

Evidence & Data Sources: Real-time public GitHub source code (.py, .js, .ts) via shallow git cloning, and manuscript documents (PDFs via pypdf, DOCX via python-docx, LaTeX, and TXT).

Expected Impact: Eliminates manual paper-code proofreading, prevents peer-review rejections due to stale claims, and guarantees 100% mathematical lockstep between open-source code and published papers.
```

---

### Project Links:
- **Live Production URL**: [https://radly.vercel.app](https://radly.vercel.app)
- **YouTube Demo Video**: [https://youtu.be/iAgQBcwuMZU](https://youtu.be/iAgQBcwuMZU?si=WBNU0XGO803-UskE)
- **GitHub Repository**: [https://github.com/monish250507/Research_Blast_Radius](https://github.com/monish250507/Research_Blast_Radius)
