"""
conftest.py — Shared pytest fixtures for the Radly test suite.

The "mini research project" fixture is the benchmark fixture described in the audit PDF:
  config.py (learning_rate=1e-4) → train.py (training function) →
  experiment runner → CSV result → table → claim

This exact fixture chain is used by:
  - test_mutation.py    — controlled mutation produces expected artifact chain
  - test_false_positive.py — harmless mutations not flagged
  - test_evidence.py    — every VERIFIED finding resolves to real source evidence
  - test_dependency.py  — call/reference/assignment/parameter flow assertions
  - test_integration.py — end-to-end analysis result
"""

import pytest

from server.domain.factories import (
    make_analysis_version,
    make_research_project,
)
from server.domain.models import (
    VerificationStatus,
)
from server.engine.code_parser import extract_code_symbols

# ---------------------------------------------------------------------------
# Canonical tiny research project — the PDF benchmark fixture
# ---------------------------------------------------------------------------
MINI_CONFIG_FILE = """
# config.py
learning_rate = 1e-4
batch_size = 32
optimizer = 'Adam'
weight_decay = 1e-5
rank = 4
"""

MINI_TRAIN_FILE = """
# train.py
from config import learning_rate, batch_size, optimizer

def run_experiment(learning_rate=learning_rate, batch_size=batch_size):
    model = build_model(rank=4)
    opt = create_optimizer(optimizer, lr=learning_rate)
    for epoch in range(10):
        loss = train_epoch(model, opt, batch_size)
    save_results(loss)
    return loss
"""

MINI_PAPER_TEXT = r"""
Abstract
We present a fine-tuning approach for language models using LoRA.

Introduction
The learning_rate is set to 1e-4 using the Adam optimizer with weight_decay=1e-5.
We use a rank of 4 for the LoRA adapters.

Methodology
\begin{equation}
L = \sum_{i} \log P(y_i | x_i; \theta)
\end{equation}

Experiments
We run experiments with batch_size=32 on CIFAR-10. The model achieves 95.5% accuracy.
We conclude that LoRA rank=4 outperforms baselines.

\begin{table}
\caption{Results with different learning rates}
\end{table}
"""


@pytest.fixture
def mini_code_files():
    """Minimal two-file research code base: config.py + train.py."""
    return [
        {"path": "config.py", "content": MINI_CONFIG_FILE},
        {"path": "train.py",  "content": MINI_TRAIN_FILE},
    ]


@pytest.fixture
def mini_symbols(mini_code_files):
    """Extracted AST symbols from the mini code base."""
    return extract_code_symbols(mini_code_files)


@pytest.fixture
def mini_paper_ast():
    """Parsed paper structure from the mini paper."""
    from server.engine.paper_parser import parse_paper_structure
    return parse_paper_structure(MINI_PAPER_TEXT)


@pytest.fixture
def mini_project(mini_symbols, mini_paper_ast):
    """
    Full mini ResearchProject with artifact index built from the mini fixtures.
    Use this as the 'base' version in mutation and false-positive tests.
    """
    from server.domain.factories import build_artifact_index
    server_info = {"version": "test"}
    av = make_analysis_version(mini_symbols, mini_paper_ast, server_info, "github.com/test/repo", "ms-test")
    idx = build_artifact_index(mini_symbols, mini_paper_ast, "github.com/test/repo", "ms-test")
    return make_research_project(
        analysisVersion=av,
        artifacts=idx,
        evidenceRecords=[],
        findings=[],
        query="",
        overallStatus=VerificationStatus.UNABLE_TO_VERIFY,
    )


@pytest.fixture
def mutated_lr_code_files():
    """
    Same as mini_code_files but learning_rate changed from 1e-4 to 1e-2.
    This IS a meaningful mutation — should affect Methodology/Experiments sections.
    """
    mutated_config = MINI_CONFIG_FILE.replace("learning_rate = 1e-4", "learning_rate = 1e-2")
    return [
        {"path": "config.py", "content": mutated_config},
        {"path": "train.py",  "content": MINI_TRAIN_FILE},
    ]


@pytest.fixture
def harmless_code_files():
    """
    Same as mini_code_files but only a comment changed.
    This is a HARMLESS mutation — should NOT affect any paper section.
    """
    harmless_config = MINI_CONFIG_FILE.replace("# config.py", "# config.py (updated comment)")
    return [
        {"path": "config.py", "content": harmless_config},
        {"path": "train.py",  "content": MINI_TRAIN_FILE},
    ]
