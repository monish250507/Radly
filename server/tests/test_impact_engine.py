import asyncio

from server.domain.models import VerificationStatus
from server.engine.impact_engine import calculate_blast_radius
from server.engine.status_model import derive_risk_level, resolve_overall_status


def test_resolve_overall_status():
    # had_processing_error -> ANALYSIS_FAILED
    assert resolve_overall_status(True, 0, 0, 0, False) == VerificationStatus.ANALYSIS_FAILED
    
    # ai ran but found nothing -> NO_DEPENDENCY_FOUND
    assert resolve_overall_status(False, 0, 0, 0, True) == VerificationStatus.NO_DEPENDENCY_FOUND
    
    # only unanchored claims exist -> UNABLE_TO_VERIFY
    assert resolve_overall_status(False, 0, 0, 1, True) == VerificationStatus.UNABLE_TO_VERIFY
    
    # anchored but no deterministic evidence -> NEEDS_REVIEW
    assert resolve_overall_status(False, 0, 1, 0, True) == VerificationStatus.NEEDS_REVIEW
    
    # deterministic evidence exists -> LIKELY (because currently verifiable needs full run)
    assert resolve_overall_status(False, 1, 1, 0, True) == VerificationStatus.LIKELY
    
    # ai did not run, no evidence -> ANALYSIS_FAILED
    assert resolve_overall_status(False, 0, 0, 0, False) == VerificationStatus.ANALYSIS_FAILED

def test_derive_risk_level():
    assert derive_risk_level(0.0, False) == 'NONE'
    assert derive_risk_level(0.1, False) == 'MINOR'
    assert derive_risk_level(0.4, False) == 'MAJOR'
    assert derive_risk_level(0.8, False) == 'HIGH'
    assert derive_risk_level(0.8, True) == 'CRITICAL'
    assert derive_risk_level(-1.0, False) == 'NONE'

def test_calculate_blast_radius_no_groq():
    # Without groq configured, it should fallback and return ANALYSIS_FAILED
    import server.engine.config as config_mod
    config_mod.config.Groq.CONFIGURED = False
    
    code_symbols = [{'symbol': 'tau', 'type': 'Variable', 'value': '0.07', 'file': 'clip/model.py', 'line': 42}]
    paper_ast = {'rawText': 'We use tau=0.07 in contrastive loss.', 'sections': [], 'equations': [], 'tables': []}
    
    res = asyncio.run(calculate_blast_radius(code_symbols, paper_ast, "test"))
    
    assert res['status'] == VerificationStatus.ANALYSIS_FAILED.value
    assert res['overall_impact_score'] is None
    assert res['risk_level'] == 'NONE'
    assert res['confidence_score'] is None
    assert res['engine']['mode'] == 'static_fallback'
    
    # Should contain additive domain object
    assert 'domain' in res
    assert res['domain']['overallStatus'] == VerificationStatus.ANALYSIS_FAILED.value
