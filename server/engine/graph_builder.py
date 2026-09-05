import uuid
from datetime import datetime

from ..domain.models import (
    ArtifactType,
    Evidence,
    EvidenceType,
    RelationshipType,
    ResearchArtifact,
    ResearchProject,
    max_verification_for_evidence,
)


def build_provenance_graph(project: ResearchProject) -> ResearchProject:
    """
    Constructs EvidenceEdges and Evidence records from parsed artifacts.

    DETERMINISTIC edges (can reach VERIFIED):
      - CONFIG → CODE via exact symbol-name match (PARAMETER_REFERENCE)
      - CLAIM → SECTION via sectionId match (SYMBOL_APPEARS_IN)
      - CODE/Variable → EQUATION via symbol-in-equation-content (EQUATION_VARIABLE)

    HEURISTIC edges (capped at NEEDS_REVIEW):
      - METRIC → CLAIM via value substring match (KEYWORD_OVERLAP / SEMANTIC)

    P0 FIX: AI_SUGGESTED edges removed entirely — they cannot be displayed as
    dependency proof. AI output may only be used as semantic candidate hints
    for a human or deterministic verifier to confirm.
    """
    new_evidence = []

    all_artifacts = (
        project.artifacts.code +
        project.artifacts.sections +
        project.artifacts.equations +
        project.artifacts.tables
    )

    artifacts_by_type = {}
    for art in all_artifacts:
        if art.artifactType not in artifacts_by_type:
            artifacts_by_type[art.artifactType] = []
        artifacts_by_type[art.artifactType].append(art)

    code_artifacts = artifacts_by_type.get(ArtifactType.CODE, [])
    config_artifacts = artifacts_by_type.get(ArtifactType.CONFIG, [])
    claim_artifacts = artifacts_by_type.get(ArtifactType.CLAIM, [])
    section_artifacts = artifacts_by_type.get(ArtifactType.SECTION, [])
    metric_artifacts = artifacts_by_type.get(ArtifactType.METRIC, [])
    equation_artifacts = artifacts_by_type.get(ArtifactType.EQUATION, [])

    # DETERMINISTIC: CONFIG → CODE (exact symbol-name match)
    for config in config_artifacts:
        for code in code_artifacts:
            if config.symbolName and code.symbolName and config.symbolName.lower() == code.symbolName.lower():
                ev = create_evidence(config, code, RelationshipType.PARAMETER_REFERENCE, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)

    # HEURISTIC: METRIC → CLAIM (metric value appears in claim text — keyword overlap only)
    # Capped at NEEDS_REVIEW via max_verification_for_evidence(SEMANTIC)
    for metric in metric_artifacts:
        for claim in claim_artifacts:
            if metric.extractedValue and claim.extractedValue and metric.extractedValue.lower() in claim.extractedValue.lower():
                ev = create_evidence(metric, claim, RelationshipType.KEYWORD_OVERLAP, EvidenceType.SEMANTIC)
                new_evidence.append(ev)

    # DETERMINISTIC: CLAIM → SECTION (physical containment via sectionId)
    for claim in claim_artifacts:
        for section in section_artifacts:
            if claim.sectionId == section.sectionId:
                ev = create_evidence(claim, section, RelationshipType.SYMBOL_APPEARS_IN, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)

    # P0 FIX: Removed RESULT → METRIC AI_SUGGESTED block.
    # Simple heuristic "result is near metric" is not dependency proof.

    # HEURISTIC: CODE Variable → EQUATION (symbol name found in equation content)
    # Capped at NEEDS_REVIEW via max_verification_for_evidence(INFERRED)
    for code in code_artifacts:
        if code.symbolKind == 'Variable' and code.symbolName:
            for eq in equation_artifacts:
                if code.symbolName in (eq.extractedValue or ""):
                    ev = create_evidence(code, eq, RelationshipType.EQUATION_VARIABLE, EvidenceType.INFERRED)
                    new_evidence.append(ev)

    project.evidenceRecords.extend(new_evidence)
    return project

def create_evidence(source: ResearchArtifact, target: ResearchArtifact, rel_type: RelationshipType, ev_type: EvidenceType) -> Evidence:
    return Evidence(
        evidenceId=f"ev_{uuid.uuid4().hex[:8]}",
        sourceArtifactId=source.artifactId,
        targetArtifactId=target.artifactId,
        evidenceType=ev_type,
        relationshipType=rel_type,
        verification=max_verification_for_evidence(ev_type),
        detail=f"Found {rel_type.value} between {source.artifactType.value} and {target.artifactType.value}",
        createdAt=datetime.utcnow().isoformat() + "Z"
    )
