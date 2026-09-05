import hashlib
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

class ArtifactType(str, Enum):
    CODE = 'CODE'
    CONFIG = 'CONFIG'
    DATASET = 'DATASET'
    PREPROCESSING = 'PREPROCESSING'
    EXPERIMENT = 'EXPERIMENT'
    RESULT = 'RESULT'
    METRIC = 'METRIC'
    FIGURE = 'FIGURE'
    TABLE = 'TABLE'
    EQUATION = 'EQUATION'
    CLAIM = 'CLAIM'
    SECTION = 'SECTION'
    ENVIRONMENT = 'ENVIRONMENT'

class EvidenceType(str, Enum):
    SEMANTIC = 'SEMANTIC'
    INFERRED = 'INFERRED'
    USER_PROVIDED = 'USER_PROVIDED'
    EXECUTION_OBSERVED = 'EXECUTION_OBSERVED'
    DETERMINISTIC = 'DETERMINISTIC'

class RelationshipType(str, Enum):
    PARAMETER_REFERENCE = 'PARAMETER_REFERENCE'
    SYMBOL_APPEARS_IN = 'SYMBOL_APPEARS_IN'
    KEYWORD_OVERLAP = 'KEYWORD_OVERLAP'
    EQUATION_VARIABLE = 'EQUATION_VARIABLE'
    CLAIM_VALIDATES = 'CLAIM_VALIDATES'
    FIGURE_GENERATED_BY = 'FIGURE_GENERATED_BY'
    TABLE_POPULATED_BY = 'TABLE_POPULATED_BY'
    AI_SUGGESTED = 'AI_SUGGESTED'
    UNKNOWN = 'UNKNOWN'

class VerificationStatus(str, Enum):
    VERIFIED = 'VERIFIED'
    LIKELY = 'LIKELY'
    NEEDS_REVIEW = 'NEEDS_REVIEW'
    NO_DEPENDENCY_FOUND = 'NO_DEPENDENCY_FOUND'
    UNABLE_TO_VERIFY = 'UNABLE_TO_VERIFY'
    ANALYSIS_FAILED = 'ANALYSIS_FAILED'
    CONFLICTING_EVIDENCE = 'CONFLICTING_EVIDENCE'
    AFFECTED = 'AFFECTED'
    REJECTED = 'REJECTED'
    EXECUTION_UNAVAILABLE = 'EXECUTION_UNAVAILABLE'

class ExecutionMode(str, Enum):
    PREDICTED = 'PREDICTED'
    OBSERVED_BY_EXECUTION = 'OBSERVED_BY_EXECUTION'

class AnalysisState(str, Enum):
    CURRENT = 'CURRENT'
    STALE = 'STALE'
    PARTIAL = 'PARTIAL'

class ExtractionStatus(str, Enum):
    OK = 'OK'
    PARTIAL = 'PARTIAL'
    FAILED = 'FAILED'

class JobStatus(str, Enum):
    QUEUED = 'QUEUED'
    PROCESSING = 'PROCESSING'
    READY = 'READY'
    STALE = 'STALE'
    FAILED = 'FAILED'

class JobRecord(BaseModel):
    jobId: str
    status: JobStatus = JobStatus.QUEUED
    result: Any | None = None
    error: str | None = None
    createdAt: str
    updatedAt: str

class AgentStatus(str, Enum):
    QUEUED = 'QUEUED'
    RUNNING = 'RUNNING'
    WAITING_FOR_TOOL = 'WAITING_FOR_TOOL'
    WAITING_FOR_EVIDENCE = 'WAITING_FOR_EVIDENCE'
    WAITING_FOR_SKEPTIC = 'WAITING_FOR_SKEPTIC'
    NEEDS_REVIEW = 'NEEDS_REVIEW'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'

class ToolCall(BaseModel):
    tool_id: str
    name: str
    arguments: dict[str, Any]

class ToolObservation(BaseModel):
    tool_id: str
    result: Any
    is_error: bool = False

class ResearchAgentRun(BaseModel):
    run_id: str
    project_id: str
    goal: str
    current_state: AgentStatus = AgentStatus.QUEUED
    iteration_count: int = 0
    max_iterations: int = 15
    tool_calls: list[ToolCall] = Field(default_factory=list)
    observations: list[ToolObservation] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    current_conclusion: str | None = None
    status: VerificationStatus = VerificationStatus.UNABLE_TO_VERIFY
    skeptic_iterations: int = 0
    skeptic_max_iterations: int = 5
    skeptic_observations: list[ToolObservation] = Field(default_factory=list)
    created_at: str
    updated_at: str

def max_verification_for_evidence(evidence_type: EvidenceType) -> VerificationStatus:
    if evidence_type == EvidenceType.DETERMINISTIC:
        return VerificationStatus.VERIFIED
    elif evidence_type in (EvidenceType.EXECUTION_OBSERVED, EvidenceType.USER_PROVIDED):
        return VerificationStatus.LIKELY
    elif evidence_type in (EvidenceType.INFERRED, EvidenceType.SEMANTIC):
        return VerificationStatus.NEEDS_REVIEW
    return VerificationStatus.UNABLE_TO_VERIFY

def stable_id(typ: str, source: str, location: str) -> str:
    inp = f"{typ}:{source}:{location}"
    hashed = hashlib.sha1(inp.encode('utf-8')).hexdigest()[:12]
    return f"art_{hashed}"

def content_hash(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha1(str(text).encode('utf-8')).hexdigest()[:16]

class ResearchArtifact(BaseModel):
    artifactId: str
    artifactType: ArtifactType
    source: str
    filePath: str | None = None
    exactLocation: str
    extractionStatus: ExtractionStatus = ExtractionStatus.OK
    version: str | None = None
    contentHash: str | None = None
    
    # Code/Config fields
    symbolName: str | None = None
    symbolKind: str | None = None
    extractedValue: str | None = None
    
    # Section fields
    sectionId: str | None = None
    title: str | None = None
    startLine: int | None = None
    endLine: int | None = None
    
    # Equation fields
    equationId: str | None = None
    label: str | None = None
    equationType: str | None = None
    
    # Table fields
    tableId: str | None = None
    caption: str | None = None

class ArtifactIndex(BaseModel):
    codeArtifacts: list[ResearchArtifact]
    sectionArtifacts: list[ResearchArtifact]
    equationArtifacts: list[ResearchArtifact]
    tableArtifacts: list[ResearchArtifact]
    all: list[ResearchArtifact]

class Evidence(BaseModel):
    evidenceId: str
    sourceArtifactId: str | None = None
    targetArtifactId: str | None = None
    exactLocation: str | None = None
    extractedValue: str | None = None
    evidenceType: EvidenceType
    relationshipType: RelationshipType
    verification: VerificationStatus
    detail: str = ''
    analysisVersion: str | None = None
    createdAt: str

class EvidenceEdge(BaseModel):
    edgeId: str
    sourceLabel: str = ''
    targetLabel: str = ''
    sourceArtifactId: str | None = None
    targetArtifactId: str | None = None
    evidenceIds: list[str] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNABLE_TO_VERIFY
    relationshipType: RelationshipType = RelationshipType.UNKNOWN
    detail: str = ''

class ImpactFinding(BaseModel):
    findingId: str
    changeReference: str = ''
    affectedArtifactId: str | None = None
    affectedArtifactType: str | None = None
    affectedTitle: str = ''
    status: VerificationStatus
    risk: str
    reason: str = ''
    evidenceIds: list[str] = Field(default_factory=list)
    evidencePath: list[str] = Field(default_factory=list)
    hasEvidence: bool = False
    analysisVersionId: str | None = None
    currentText: str | None = None
    suggestedText: str | None = None
    createdAt: str

class AnalysisVersion(BaseModel):
    versionId: str
    schemaVersion: str = SCHEMA_VERSION
    serverVersion: str
    nodeVersion: str | None = None
    commitSha: str | None = None
    repoUrl: str | None = None
    repoSnapshotHash: str
    manuscriptId: str | None = None
    manuscriptHash: str
    symbolCount: int = 0
    sectionCount: int = 0
    createdAt: str
    state: AnalysisState = AnalysisState.CURRENT
    staleReasons: list[str] | None = None

class ProjectSummary(BaseModel):
    totalArtifacts: int = 0
    totalEvidence: int = 0
    totalFindings: int = 0
    findingsWithEvidence: int = 0
    findingsNeedingReview: int = 0

class ProjectArtifacts(BaseModel):
    code: list[ResearchArtifact] = Field(default_factory=list)
    sections: list[ResearchArtifact] = Field(default_factory=list)
    equations: list[ResearchArtifact] = Field(default_factory=list)
    tables: list[ResearchArtifact] = Field(default_factory=list)
    total: int = 0

class ResearchProject(BaseModel):
    projectId: str
    analysisVersion: AnalysisVersion
    query: str = ''
    overallStatus: VerificationStatus = VerificationStatus.UNABLE_TO_VERIFY
    artifacts: ProjectArtifacts = Field(default_factory=ProjectArtifacts)
    evidenceRecords: list[Evidence] = Field(default_factory=list)
    findings: list[ImpactFinding] = Field(default_factory=list)
    summary: ProjectSummary = Field(default_factory=ProjectSummary)
    createdAt: str
