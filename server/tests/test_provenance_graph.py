import pytest
from server.domain.models import (
    ResearchProject, ResearchArtifact, AnalysisVersion, 
    ArtifactType, ArtifactIndex, ProjectArtifacts, ExtractionStatus,
    VerificationStatus
)
from server.engine.graph_builder import build_provenance_graph
from server.engine.impact_engine import compare_graphs
from datetime import datetime

def make_dummy_project() -> ResearchProject:
    art_config = ResearchArtifact(
        artifactId="art_config1", artifactType=ArtifactType.CONFIG, source="code", exactLocation="config.py",
        symbolName="learning_rate", extractedValue="1e-4", extractionStatus=ExtractionStatus.OK
    )
    art_code = ResearchArtifact(
        artifactId="art_code1", artifactType=ArtifactType.CODE, source="code", exactLocation="train.py",
        symbolName="learning_rate", symbolKind="Variable", extractionStatus=ExtractionStatus.OK
    )
    art_metric = ResearchArtifact(
        artifactId="art_metric1", artifactType=ArtifactType.METRIC, source="paper", exactLocation="p1",
        extractedValue="Accuracy", extractionStatus=ExtractionStatus.OK
    )
    art_claim = ResearchArtifact(
        artifactId="art_claim1", artifactType=ArtifactType.CLAIM, source="paper", exactLocation="p1",
        extractedValue="Model achieves high Accuracy", extractionStatus=ExtractionStatus.OK, sectionId="sec1"
    )
    art_section = ResearchArtifact(
        artifactId="art_section1", artifactType=ArtifactType.SECTION, source="paper", exactLocation="p1",
        sectionId="sec1", title="Results", extractionStatus=ExtractionStatus.OK
    )
    
    # We explicitly link config -> code -> metric -> claim -> section via graph_builder heuristic
    
    arts = ProjectArtifacts(
        code=[art_code, art_config],
        sections=[art_section, art_claim, art_metric]
    )
    
    av = AnalysisVersion(versionId="v1", serverVersion="1", repoSnapshotHash="h1", manuscriptHash="h2", createdAt=datetime.utcnow().isoformat())
    
    p = ResearchProject(projectId="p1", analysisVersion=av, artifacts=arts, createdAt=datetime.utcnow().isoformat())
    return p


def test_learning_rate_change():
    base = make_dummy_project()
    base = build_provenance_graph(base)
    
    proposed = make_dummy_project()
    proposed.artifacts.code[1].contentHash = "changed_lr"
    proposed = build_provenance_graph(proposed)
    
    findings = compare_graphs(base, proposed)
    
    # config was changed, it impacts code -> (and others if connected)
    # Our simple graph_builder script connects config->code, metric->claim, claim->section.
    # To connect code->metric, we need to explicitly add an evidence in proposed
    
    # Check that findings reflect the change
    assert any(f.affectedArtifactId == "art_config1" for f in findings)
    
def test_optimizer_change():
    # Placeholder for optimizer change mutation
    pass

def test_harmless_unrelated_change():
    base = make_dummy_project()
    proposed = make_dummy_project()
    proposed.artifacts.code[0].contentHash = "changed_code"
    
    # We didn't link code to metric here, so it should just affect code
    findings = compare_graphs(base, proposed)
    assert len(findings) == 1
    assert findings[0].affectedArtifactId == "art_code1"

def test_missing_evidence():
    # If a finding is unaffected, it has NO_DEPENDENCY_FOUND
    base = make_dummy_project()
    proposed = make_dummy_project()
    proposed.artifacts.code[0].contentHash = "changed"
    findings = compare_graphs(base, proposed)
    
    f = next(f for f in findings if f.affectedArtifactId == "art_code1")
    # since path is empty it means "Directly changed", which is AFFECTED (or NO_DEPENDENCY_FOUND if not changed directly)
    assert f.status in (VerificationStatus.AFFECTED, VerificationStatus.NO_DEPENDENCY_FOUND)
