import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from .models import (
    ArtifactType, EvidenceType, RelationshipType, VerificationStatus,
    ExtractionStatus, AnalysisState, SCHEMA_VERSION,
    ResearchArtifact, ArtifactIndex, Evidence, EvidenceEdge, ImpactFinding,
    AnalysisVersion, ResearchProject, ProjectArtifacts, ProjectSummary,
    stable_id, content_hash, max_verification_for_evidence
)

# Global sequences for ID generation
_evidence_seq = 0
_finding_seq = 0
_version_seq = 0

def get_current_iso_time() -> str:
    return datetime.utcnow().isoformat() + "Z"

def next_evidence_id() -> str:
    global _evidence_seq
    _evidence_seq += 1
    return f"ev_{int(time.time() * 1000):x}_{_evidence_seq:04x}"

def next_finding_id() -> str:
    global _finding_seq
    _finding_seq += 1
    return f"find_{int(time.time() * 1000):x}_{_finding_seq:04x}"

def next_version_id() -> str:
    global _version_seq
    _version_seq += 1
    return f"av_{int(time.time() * 1000):x}_{_version_seq:04x}"

# ---------------------------------------------------------------------------
# Artifact Factories
# ---------------------------------------------------------------------------

def code_artifact_from_symbol(sym: Dict[str, Any], repo_source: Optional[str] = None) -> ResearchArtifact:
    file_path = sym.get('file')
    line = sym.get('line')
    location = f"{file_path}:{line}"
    source = repo_source or file_path or "unknown"
    art_id = stable_id(ArtifactType.CODE.value, source, location)
    
    val = sym.get('value')
    extracted_val = str(val) if val is not None else None
    
    return ResearchArtifact(
        artifactId=art_id,
        artifactType=ArtifactType.CODE,
        source=source,
        filePath=file_path,
        exactLocation=location,
        symbolName=sym.get('symbol'),
        symbolKind=sym.get('type'),
        extractedValue=extracted_val,
        contentHash=content_hash(f"{sym.get('symbol')}:{extracted_val}"),
        extractionStatus=ExtractionStatus.OK
    )

def config_artifact_from_symbol(sym: Dict[str, Any], repo_source: Optional[str] = None) -> ResearchArtifact:
    art = code_artifact_from_symbol(sym, repo_source)
    art.artifactType = ArtifactType.CONFIG
    return art

def section_artifact(sec: Dict[str, Any], manuscript_source: Optional[str] = None) -> ResearchArtifact:
    source = manuscript_source or 'manuscript'
    sec_id = sec.get('id')
    art_id = stable_id(ArtifactType.SECTION.value, source, str(sec_id))
    
    return ResearchArtifact(
        artifactId=art_id,
        artifactType=ArtifactType.SECTION,
        source=source,
        exactLocation=f"lines {sec.get('startLine')}–{sec.get('endLine')}",
        sectionId=sec_id,
        title=sec.get('title'),
        extractedValue=sec.get('text'),
        startLine=sec.get('startLine'),
        endLine=sec.get('endLine'),
        contentHash=content_hash(sec.get('text')),
        extractionStatus=ExtractionStatus.OK
    )

def equation_artifact(eq: Dict[str, Any], manuscript_source: Optional[str] = None) -> ResearchArtifact:
    source = manuscript_source or 'manuscript'
    eq_id = eq.get('id')
    art_id = stable_id(ArtifactType.EQUATION.value, source, str(eq_id))
    
    return ResearchArtifact(
        artifactId=art_id,
        artifactType=ArtifactType.EQUATION,
        source=source,
        exactLocation=str(eq_id),
        equationId=eq_id,
        label=eq.get('label'),
        extractedValue=eq.get('content'),
        equationType=eq.get('type'),
        contentHash=content_hash(eq.get('content')),
        extractionStatus=ExtractionStatus.OK
    )

def table_artifact(tbl: Dict[str, Any], manuscript_source: Optional[str] = None) -> ResearchArtifact:
    source = manuscript_source or 'manuscript'
    tbl_id = tbl.get('id')
    art_id = stable_id(ArtifactType.TABLE.value, source, str(tbl_id))
    
    return ResearchArtifact(
        artifactId=art_id,
        artifactType=ArtifactType.TABLE,
        source=source,
        exactLocation=str(tbl_id),
        tableId=tbl_id,
        label=tbl.get('label'),
        caption=tbl.get('caption'),
        extractedValue=tbl.get('content'),
        contentHash=content_hash(tbl.get('content')),
        extractionStatus=ExtractionStatus.OK
    )

def build_artifact_index(code_symbols: List[Dict[str, Any]], paper_ast: Dict[str, Any], repo_source: Optional[str] = None, manuscript_source: Optional[str] = None) -> ArtifactIndex:
    code_artifacts = []
    for sym in (code_symbols or []):
        if sym.get('type') == 'ConfigKey':
            code_artifacts.append(config_artifact_from_symbol(sym, repo_source))
        else:
            code_artifacts.append(code_artifact_from_symbol(sym, repo_source))
            
    section_artifacts = [section_artifact(sec, manuscript_source) for sec in (paper_ast.get('sections') or [])]
    equation_artifacts = [equation_artifact(eq, manuscript_source) for eq in (paper_ast.get('equations') or [])]
    table_artifacts = [table_artifact(tbl, manuscript_source) for tbl in (paper_ast.get('tables') or [])]
    
    all_artifacts = code_artifacts + section_artifacts + equation_artifacts + table_artifacts
    
    return ArtifactIndex(
        codeArtifacts=code_artifacts,
        sectionArtifacts=section_artifacts,
        equationArtifacts=equation_artifacts,
        tableArtifacts=table_artifacts,
        all=all_artifacts
    )

# ---------------------------------------------------------------------------
# Evidence Factories
# ---------------------------------------------------------------------------

def make_evidence(
    evidenceType: EvidenceType,
    relationshipType: RelationshipType,
    sourceArtifactId: Optional[str] = None,
    targetArtifactId: Optional[str] = None,
    exactLocation: Optional[str] = None,
    extractedValue: Optional[str] = None,
    detail: str = '',
    analysisVersion: Optional[str] = None
) -> Evidence:
    verification = max_verification_for_evidence(evidenceType)
    
    return Evidence(
        evidenceId=next_evidence_id(),
        sourceArtifactId=sourceArtifactId,
        targetArtifactId=targetArtifactId,
        exactLocation=exactLocation,
        extractedValue=str(extractedValue) if extractedValue is not None else None,
        evidenceType=evidenceType,
        relationshipType=relationshipType,
        verification=verification,
        detail=detail,
        analysisVersion=analysisVersion,
        createdAt=get_current_iso_time()
    )

def evidence_from_static_matches(
    static_matches: List[Dict[str, Any]],
    section_artifact_map: Dict[str, str],
    symbol_key_to_artifact_id: Optional[Dict[str, str]],
    analysis_version: str
) -> dict:
    evidence_records = []
    edges = []
    
    for match in (static_matches or []):
        sym_key = match.get('symbol')
        source_id = symbol_key_to_artifact_id.get(sym_key) if symbol_key_to_artifact_id else None
        target_id = section_artifact_map.get(match.get('targetId'))
        
        is_keyword = match.get('evidenceBasis') == 'keyword_match'
        ev_type = EvidenceType.SEMANTIC
        rel_type = RelationshipType.KEYWORD_OVERLAP if is_keyword else RelationshipType.SYMBOL_APPEARS_IN
        
        extracted_val = sym_key.replace('Query Keyword (', '').replace(')', '') if is_keyword else None
        
        ev = make_evidence(
            sourceArtifactId=source_id,
            targetArtifactId=target_id,
            exactLocation=sym_key,
            extractedValue=extracted_val,
            evidenceType=ev_type,
            relationshipType=rel_type,
            detail=match.get('reason') or '',
            analysisVersion=analysis_version
        )
        evidence_records.append(ev)
        
        import hashlib
        edge_id = f"edge_{hashlib.sha1(f'{source_id}:{target_id}'.encode('utf-8')).hexdigest()[:10]}"
        
        edge = EvidenceEdge(
            edgeId=edge_id,
            sourceLabel=sym_key or '',
            targetLabel=match.get('target') or '',
            sourceArtifactId=source_id,
            targetArtifactId=target_id,
            evidenceIds=[ev.evidenceId],
            verification=ev.verification,
            relationshipType=rel_type,
            detail=match.get('reason') or ''
        )
        edges.append(edge)
        
    return {"evidenceRecords": evidence_records, "edges": edges}

def evidence_from_ai_sections(
    valid_sections: List[Dict[str, Any]],
    section_artifact_map: Dict[str, str],
    query: str,
    analysis_version: str
) -> List[Evidence]:
    records = []
    for sec in (valid_sections or []):
        target_id = section_artifact_map.get(sec.get('section_id'))
        ev = make_evidence(
            sourceArtifactId=None,
            targetArtifactId=target_id,
            exactLocation=sec.get('section_id'),
            extractedValue=None,
            evidenceType=EvidenceType.INFERRED,
            relationshipType=RelationshipType.AI_SUGGESTED,
            detail=sec.get('reason') or '(AI assertion without specific source)',
            analysisVersion=analysis_version
        )
        records.append(ev)
    return records

# ---------------------------------------------------------------------------
# Finding Factories
# ---------------------------------------------------------------------------

def make_impact_finding(
    status: VerificationStatus,
    risk: str,
    changeReference: str = '',
    affectedArtifactId: Optional[str] = None,
    affectedArtifactType: Optional[str] = None,
    affectedTitle: str = '',
    reason: str = '',
    evidenceIds: Optional[List[str]] = None,
    analysisVersionId: Optional[str] = None,
    currentText: Optional[str] = None,
    suggestedText: Optional[str] = None
) -> ImpactFinding:
    evidence_ids = evidenceIds or []
    
    return ImpactFinding(
        findingId=next_finding_id(),
        changeReference=changeReference,
        affectedArtifactId=affectedArtifactId,
        affectedArtifactType=affectedArtifactType,
        affectedTitle=affectedTitle,
        status=status,
        risk=risk.upper() if risk else 'MINOR',
        reason=reason,
        evidenceIds=evidence_ids,
        hasEvidence=len(evidence_ids) > 0,
        analysisVersionId=analysisVersionId,
        currentText=currentText,
        suggestedText=suggestedText,
        createdAt=get_current_iso_time()
    )

def findings_from_ai_sections(
    valid_sections: List[Dict[str, Any]],
    section_artifact_map: Dict[str, str],
    ai_evidence_records: List[Evidence],
    change_reference: str,
    analysis_version_id: str
) -> List[ImpactFinding]:
    evidence_by_section = {}
    for ev in (ai_evidence_records or []):
        if ev.targetArtifactId:
            evidence_by_section.setdefault(ev.targetArtifactId, []).append(ev.evidenceId)
            
    findings = []
    for sec in (valid_sections or []):
        art_id = section_artifact_map.get(sec.get('section_id'))
        ev_ids = evidence_by_section.get(art_id, []) if art_id else []
        
        status_str = sec.get('verification')
        try:
            status = VerificationStatus(status_str)
        except ValueError:
            status = VerificationStatus.NEEDS_REVIEW
            
        finding = make_impact_finding(
            changeReference=change_reference,
            affectedArtifactId=art_id,
            affectedArtifactType='SECTION',
            affectedTitle=sec.get('title') or sec.get('section_id', ''),
            status=status,
            risk=sec.get('risk') or 'MINOR',
            reason=sec.get('reason') or '',
            evidenceIds=ev_ids,
            analysisVersionId=analysis_version_id,
            currentText=sec.get('current_text'),
            suggestedText=sec.get('suggested_text')
        )
        findings.append(finding)
    return findings

def findings_from_static_sections(
    static_affected_sections: List[Dict[str, Any]],
    section_artifact_map: Dict[str, str],
    static_evidence_records: List[Evidence],
    change_reference: str,
    analysis_version_id: str
) -> List[ImpactFinding]:
    evidence_by_artifact = {}
    for ev in (static_evidence_records or []):
        if ev.targetArtifactId:
            evidence_by_artifact.setdefault(ev.targetArtifactId, []).append(ev.evidenceId)
            
    findings = []
    for sec in (static_affected_sections or []):
        art_id = section_artifact_map.get(sec.get('section_id'))
        ev_ids = evidence_by_artifact.get(art_id, []) if art_id else []
        
        finding = make_impact_finding(
            changeReference=change_reference,
            affectedArtifactId=art_id,
            affectedArtifactType='SECTION',
            affectedTitle=sec.get('title') or sec.get('section_id', ''),
            status=VerificationStatus.NEEDS_REVIEW,
            risk=sec.get('risk') or 'MINOR',
            reason=sec.get('reason') or '',
            evidenceIds=ev_ids,
            analysisVersionId=analysis_version_id,
            currentText=sec.get('current_text'),
            suggestedText=None
        )
        findings.append(finding)
    return findings

# ---------------------------------------------------------------------------
# Version Factories
# ---------------------------------------------------------------------------

def repo_snapshot_hash(code_symbols: List[Dict[str, Any]]) -> str:
    if not code_symbols:
        return 'empty'
    canonical = "|".join(
        sorted([f"{s.get('file')}:{s.get('line')}:{s.get('symbol')}" for s in code_symbols])
    )
    import hashlib
    return hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:16]

def manuscript_hash(raw_text: Optional[str]) -> str:
    if not raw_text:
        return 'empty'
    import hashlib
    return hashlib.sha1(str(raw_text).encode('utf-8')).hexdigest()[:16]

def make_analysis_version(
    code_symbols: List[Dict[str, Any]],
    paper_ast: Dict[str, Any],
    server_version_info: Dict[str, Any],
    repo_url: Optional[str] = None,
    manuscript_id: Optional[str] = None
) -> AnalysisVersion:
    repo_hash = repo_snapshot_hash(code_symbols)
    paper_hash = manuscript_hash(paper_ast.get('rawText'))
    
    return AnalysisVersion(
        versionId=next_version_id(),
        schemaVersion=SCHEMA_VERSION,
        serverVersion=server_version_info.get('version', '0.0.0'),
        nodeVersion=server_version_info.get('nodeVersion'),
        commitSha=server_version_info.get('commitSha'),
        repoUrl=repo_url,
        repoSnapshotHash=repo_hash,
        manuscriptId=manuscript_id,
        manuscriptHash=paper_hash,
        symbolCount=len(code_symbols) if code_symbols else 0,
        sectionCount=len(paper_ast.get('sections', [])),
        createdAt=get_current_iso_time(),
        state=AnalysisState.CURRENT
    )

def check_staleness(previous_version: Dict[str, Any], current_code_symbols: List[Dict[str, Any]], current_paper_ast: Dict[str, Any]) -> dict:
    reasons = []
    if not previous_version:
        return {"stale": False, "reasons": []}
        
    prev_schema = previous_version.get('schemaVersion')
    if prev_schema != SCHEMA_VERSION:
        reasons.append(f"Schema version changed: was {prev_schema}, now {SCHEMA_VERSION}. Re-analysis required.")
        
    curr_repo_hash = repo_snapshot_hash(current_code_symbols)
    prev_repo_hash = previous_version.get('repoSnapshotHash')
    if prev_repo_hash != curr_repo_hash:
        reasons.append(f"Repository snapshot changed (was {prev_repo_hash}, now {curr_repo_hash}). Code may have been modified.")
        
    curr_paper_hash = manuscript_hash(current_paper_ast.get('rawText'))
    prev_paper_hash = previous_version.get('manuscriptHash')
    if prev_paper_hash != curr_paper_hash:
        reasons.append(f"Manuscript changed (was {prev_paper_hash}, now {curr_paper_hash}). Paper may have been updated.")
        
    return {"stale": len(reasons) > 0, "reasons": reasons}

# ---------------------------------------------------------------------------
# Project Factories
# ---------------------------------------------------------------------------

def make_research_project(
    analysisVersion: AnalysisVersion,
    artifacts: ArtifactIndex,
    evidenceRecords: List[Evidence],
    findings: List[ImpactFinding],
    query: str = '',
    overallStatus: VerificationStatus = VerificationStatus.UNABLE_TO_VERIFY
) -> ResearchProject:
    
    findings_with_evidence = sum(1 for f in findings if f.hasEvidence)
    findings_needing_review = sum(1 for f in findings if f.status == VerificationStatus.NEEDS_REVIEW)
    
    summary = ProjectSummary(
        totalArtifacts=len(artifacts.all),
        totalEvidence=len(evidenceRecords),
        totalFindings=len(findings),
        findingsWithEvidence=findings_with_evidence,
        findingsNeedingReview=findings_needing_review
    )
    
    project_artifacts = ProjectArtifacts(
        code=artifacts.codeArtifacts,
        sections=artifacts.sectionArtifacts,
        equations=artifacts.equationArtifacts,
        tables=artifacts.tableArtifacts,
        total=len(artifacts.all)
    )
    
    return ResearchProject(
        projectId=f"proj_{analysisVersion.versionId}",
        analysisVersion=analysisVersion,
        query=query,
        overallStatus=overallStatus,
        artifacts=project_artifacts,
        evidenceRecords=evidenceRecords,
        findings=findings,
        summary=summary,
        createdAt=get_current_iso_time()
    )
