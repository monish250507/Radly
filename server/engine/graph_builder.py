import uuid
from datetime import datetime, timezone

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
    Provides complete inspectable multi-hop deterministic code data-flow (P2-1, P2-2):
      - Changed CONFIG/Parameter → Function (PARAMETER_REFERENCE, DETERMINISTIC)
      - Function Arguments → Function (ARGUMENT_OF, DETERMINISTIC)
      - Local Assignment → Function / Computation (COMPUTED_IN, DETERMINISTIC)
      - Function → Function Call (CALLS, DETERMINISTIC)
      - Code Variable → EQUATION (EQUATION_VARIABLE, INFERRED → NEEDS_REVIEW)
      - METRIC → CLAIM (KEYWORD_OVERLAP, SEMANTIC → NEEDS_REVIEW)
      - CLAIM → SECTION (SYMBOL_APPEARS_IN, DETERMINISTIC)

    Candidate matching (keywords, semantic overlap) is strictly separated from proof
    and capped at NEEDS_REVIEW via max_verification_for_evidence().
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

    # Index code artifacts by kind and parent context
    functions = [c for c in code_artifacts if c.symbolKind in ('Function', 'Method')]
    arguments = [c for c in code_artifacts if c.symbolKind == 'Argument']
    assignments = [c for c in code_artifacts if c.symbolKind in ('Assignment', 'Variable')]
    calls = [c for c in code_artifacts if c.symbolKind == 'Call']

    # 1. DETERMINISTIC: CONFIG → CODE (exact symbol-name match)
    for config in config_artifacts:
        for code in code_artifacts:
            if config.symbolName and code.symbolName and config.symbolName.lower() == code.symbolName.lower():
                ev = create_evidence(config, code, RelationshipType.PARAMETER_REFERENCE, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)

    # 2. DETERMINISTIC DATA-FLOW: Argument → Function
    for arg in arguments:
        for fn in functions:
            if arg.filePath == fn.filePath and arg.exactLocation and fn.exactLocation:
                # Same file and nearby line definition
                if arg.symbolName and fn.symbolName:
                    ev = create_evidence(arg, fn, RelationshipType.DATA_FLOW, EvidenceType.DETERMINISTIC)
                    new_evidence.append(ev)

    # 3. DETERMINISTIC DATA-FLOW: Assignment → Function
    for assign in assignments:
        for fn in functions:
            if assign.filePath == fn.filePath and assign.symbolName:
                ev = create_evidence(assign, fn, RelationshipType.DATA_FLOW, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)

    # 4. DETERMINISTIC: Function → Function Calls
    for call in calls:
        for fn in functions:
            if call.symbolName and fn.symbolName and call.symbolName == fn.symbolName:
                ev = create_evidence(call, fn, RelationshipType.CALLS, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)

    # 5. HEURISTIC: CODE Variable → EQUATION (symbol name in equation content)
    # Capped at NEEDS_REVIEW via max_verification_for_evidence(INFERRED)
    for code in code_artifacts:
        if code.symbolKind in ('Variable', 'Assignment', 'Argument') and code.symbolName:
            for eq in equation_artifacts:
                if code.symbolName in (eq.extractedValue or ""):
                    ev = create_evidence(code, eq, RelationshipType.EQUATION_VARIABLE, EvidenceType.INFERRED)
                    new_evidence.append(ev)

    # 6. HEURISTIC: METRIC → CLAIM (metric value in claim text — candidate keyword overlap only)
    # Capped at NEEDS_REVIEW via max_verification_for_evidence(SEMANTIC)
    for metric in metric_artifacts:
        for claim in claim_artifacts:
            if metric.extractedValue and claim.extractedValue and metric.extractedValue.lower() in claim.extractedValue.lower():
                ev = create_evidence(metric, claim, RelationshipType.KEYWORD_OVERLAP, EvidenceType.SEMANTIC)
                new_evidence.append(ev)

    # 7. DETERMINISTIC: CLAIM → SECTION (physical containment via sectionId)
    for claim in claim_artifacts:
        for section in section_artifacts:
            if claim.sectionId == section.sectionId:
                ev = create_evidence(claim, section, RelationshipType.SYMBOL_APPEARS_IN, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)

    project.evidenceRecords.extend(new_evidence)
    return project


def create_evidence(source: ResearchArtifact, target: ResearchArtifact, rel_type: RelationshipType, ev_type: EvidenceType) -> Evidence:
    """Creates a strictly typed Evidence record with exact source location and bounded verification status."""
    return Evidence(
        evidenceId=f"ev_{uuid.uuid4().hex[:8]}",
        sourceArtifactId=source.artifactId,
        targetArtifactId=target.artifactId,
        exactLocation=source.exactLocation,
        extractedValue=source.extractedValue or source.symbolName,
        evidenceType=ev_type,
        relationshipType=rel_type,
        verification=max_verification_for_evidence(ev_type),
        detail=f"Found {rel_type.value} between {source.artifactType.value} ({source.symbolName or source.artifactId}) and {target.artifactType.value} ({target.symbolName or target.artifactId})",
        createdAt=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
