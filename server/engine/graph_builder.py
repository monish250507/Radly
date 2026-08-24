from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
from ..domain.models import (
    ResearchProject, ResearchArtifact, Evidence, EvidenceEdge, 
    ArtifactType, RelationshipType, EvidenceType, VerificationStatus,
    max_verification_for_evidence
)
from .logger import paperblast_logger as logger

def build_provenance_graph(project: ResearchProject) -> ResearchProject:
    """
    Constructs EvidenceEdges and Evidence records deterministically based on parsed artifacts.
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
    dataset_artifacts = artifacts_by_type.get(ArtifactType.DATASET, [])
    claim_artifacts = artifacts_by_type.get(ArtifactType.CLAIM, [])
    section_artifacts = artifacts_by_type.get(ArtifactType.SECTION, [])
    metric_artifacts = artifacts_by_type.get(ArtifactType.METRIC, [])
    result_artifacts = artifacts_by_type.get(ArtifactType.RESULT, [])
    equation_artifacts = artifacts_by_type.get(ArtifactType.EQUATION, [])

    # CONFIG -> CODE (Heuristic: config key matches variable assignment)
    for config in config_artifacts:
        for code in code_artifacts:
            if config.symbolName and code.symbolName and config.symbolName.lower() == code.symbolName.lower():
                ev = create_evidence(config, code, RelationshipType.PARAMETER_REFERENCE, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)
                
    # METRIC -> CLAIM (Metric name appears in claim)
    for metric in metric_artifacts:
        for claim in claim_artifacts:
            if metric.extractedValue and claim.extractedValue and metric.extractedValue.lower() in claim.extractedValue.lower():
                ev = create_evidence(metric, claim, RelationshipType.KEYWORD_OVERLAP, EvidenceType.SEMANTIC)
                new_evidence.append(ev)
                
    # CLAIM -> SECTION (Claim is physically located in section)
    for claim in claim_artifacts:
        for section in section_artifacts:
            if claim.sectionId == section.sectionId:
                ev = create_evidence(claim, section, RelationshipType.SYMBOL_APPEARS_IN, EvidenceType.DETERMINISTIC)
                new_evidence.append(ev)
                
    # RESULT -> METRIC
    for result in result_artifacts:
        for metric in metric_artifacts:
            # Simple heuristic: result is near metric in text
            ev = create_evidence(result, metric, RelationshipType.AI_SUGGESTED, EvidenceType.INFERRED)
            new_evidence.append(ev)
            
    # PARAMETER -> EQUATION
    # If a code variable matches an equation variable
    for code in code_artifacts:
        if code.symbolKind == 'Variable' and code.symbolName:
            for eq in equation_artifacts:
                # eq variables are usually 1 letter. If match:
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
