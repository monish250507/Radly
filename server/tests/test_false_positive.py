"""
test_false_positive.py — P2: False-positive restraint tests.

Proves that harmless changes (e.g. comments) do not trigger false impact findings.
"""
from server.domain.models import VerificationStatus
from server.engine.graph_builder import build_provenance_graph
from server.engine.impact_engine import compare_graphs


def test_harmless_comment_mutation_not_flagged(mini_project, harmless_code_files, mini_paper_ast):
    """
    Changing a comment should not alter the AST symbols in a meaningful way,
    and should not produce blast radius findings.
    """
    base_proj = build_provenance_graph(mini_project)
    
    from server.engine.code_parser import extract_code_symbols
    harmless_symbols = extract_code_symbols(harmless_code_files)
    
    from server.domain.factories import (
        build_artifact_index,
        make_analysis_version,
        make_research_project,
    )
    idx = build_artifact_index(harmless_symbols, mini_paper_ast, "github.com/test/repo", "ms-test")
    av = make_analysis_version(harmless_symbols, mini_paper_ast, {"version":"test"}, "github.com/test/repo", "ms-test")
    
    proposed_proj = make_research_project(
        analysisVersion=av,
        artifacts=idx,
        evidenceRecords=[],
        findings=[],
        query="Harmless change",
        overallStatus=VerificationStatus.UNABLE_TO_VERIFY
    )
    proposed_proj = build_provenance_graph(proposed_proj)
    
    findings = compare_graphs(base_proj, proposed_proj)
    
    # Check that no artifacts are actually AFFECTED
    affected_findings = [f for f in findings if f.status == VerificationStatus.AFFECTED]
    assert len(affected_findings) == 0, "Harmless comment change produced false positive impact findings"
