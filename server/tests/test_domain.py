from server.domain.factories import (
    build_artifact_index,
    check_staleness,
    code_artifact_from_symbol,
    make_analysis_version,
    make_evidence,
    make_impact_finding,
    section_artifact,
)
from server.domain.models import (
    ArtifactType,
    EvidenceType,
    ExtractionStatus,
    RelationshipType,
    VerificationStatus,
    max_verification_for_evidence,
)

SYM_TAU = {'symbol': 'tau', 'type': 'Variable', 'value': '0.07', 'file': 'clip/model.py', 'line': 42}
SYM_LR  = {'symbol': 'learning_rate', 'type': 'Variable', 'value': '1e-4', 'file': 'train.py', 'line': 15}

SEC_INTRO = {'id': 'sec-1-introduction', 'title': 'Introduction', 'text': 'We use tau=0.07 in contrastive loss.', 'startLine': 1, 'endLine': 10}
SEC_METHOD = {'id': 'sec-2-methodology', 'title': 'Methodology', 'text': 'The learning_rate is 1e-4 with LoRA rank=4.', 'startLine': 11, 'endLine': 30}

EQ_1 = {'id': 'eq-1', 'label': 'Equation (1)', 'content': 'L = -log(tau)', 'raw': '\\begin{equation} L \\end{equation}', 'type': 'equation'}
TBL_1 = {'id': 'table-1', 'label': 'Table 1', 'caption': 'Results', 'content': '...', 'type': 'latex'}

PAPER_AST = {
    'rawText': 'We use tau=0.07 in contrastive loss. The learning_rate is 1e-4 with LoRA rank=4.',
    'sections': [SEC_INTRO, SEC_METHOD],
    'equations': [EQ_1],
    'tables': [TBL_1],
    'numbers': []
}

CODE_SYMBOLS = [SYM_TAU, SYM_LR]
QUERY = 'What if tau changes from 0.07 to 0.01?'

def test_code_artifact_from_symbol():
    art = code_artifact_from_symbol(SYM_TAU, 'github.com/user/repo')
    assert art.artifactType == ArtifactType.CODE
    assert art.symbolName == 'tau'
    assert art.filePath == 'clip/model.py'
    assert art.exactLocation == 'clip/model.py:42'
    assert art.extractionStatus == ExtractionStatus.OK
    assert art.contentHash is not None

def test_artifact_id_is_stable():
    a1 = code_artifact_from_symbol(SYM_TAU, 'repo')
    a2 = code_artifact_from_symbol(SYM_TAU, 'repo')
    assert a1.artifactId == a2.artifactId
    a3 = code_artifact_from_symbol(SYM_LR, 'repo')
    assert a1.artifactId != a3.artifactId

def test_section_artifact():
    art = section_artifact(SEC_INTRO, 'ms')
    assert art.artifactType == ArtifactType.SECTION
    assert art.sectionId == SEC_INTRO['id']
    assert art.title == SEC_INTRO['title']

def test_build_artifact_index():
    idx = build_artifact_index(CODE_SYMBOLS, PAPER_AST, 'repo', 'ms')
    assert len(idx.codeArtifacts) == 2
    assert len(idx.sectionArtifacts) == 2
    assert len(idx.equationArtifacts) == 1
    assert len(idx.tableArtifacts) == 1
    assert len(idx.all) == 6

def test_max_verification_for_evidence():
    assert max_verification_for_evidence(EvidenceType.SEMANTIC) == VerificationStatus.NEEDS_REVIEW
    assert max_verification_for_evidence(EvidenceType.INFERRED) == VerificationStatus.NEEDS_REVIEW
    assert max_verification_for_evidence(EvidenceType.DETERMINISTIC) == VerificationStatus.VERIFIED

def test_make_evidence():
    ev = make_evidence(
        evidenceType=EvidenceType.SEMANTIC,
        relationshipType=RelationshipType.KEYWORD_OVERLAP,
        detail='test',
        analysisVersion='v1'
    )
    assert ev.evidenceType == EvidenceType.SEMANTIC
    assert ev.verification == VerificationStatus.NEEDS_REVIEW

def test_make_impact_finding():
    finding = make_impact_finding(
        status=VerificationStatus.NEEDS_REVIEW,
        risk='MINOR',
        changeReference=QUERY,
        affectedArtifactType='SECTION',
        affectedTitle='Introduction',
        reason='test',
        evidenceIds=['ev_1'],
        analysisVersionId='v1'
    )
    assert finding.status == VerificationStatus.NEEDS_REVIEW
    assert finding.hasEvidence is True
    assert finding.risk == 'MINOR'

def test_analysis_version_staleness():
    server_info = {'version': '1.0.0'}
    av = make_analysis_version(CODE_SYMBOLS, PAPER_AST, server_info, 'repo', 'ms')
    
    # Not stale
    staleness = check_staleness(av.model_dump(), CODE_SYMBOLS, PAPER_AST)
    assert staleness['stale'] is False
    
    # Stale due to symbols change
    new_symbols = [SYM_TAU] # dropped one
    staleness = check_staleness(av.model_dump(), new_symbols, PAPER_AST)
    assert staleness['stale'] is True
    assert any('Repository snapshot changed' in r for r in staleness['reasons'])
