from ..domain.models import VerificationStatus


def resolve_overall_status(
    had_processing_error: bool,
    deterministic_evidence_count: int,
    anchored_claim_count: int,
    unanchored_claim_count: int,
    ai_synthesis_ran: bool
) -> VerificationStatus:
    if had_processing_error:
        return VerificationStatus.ANALYSIS_FAILED

    if deterministic_evidence_count == 0 and anchored_claim_count == 0:
        if unanchored_claim_count > 0:
            return VerificationStatus.UNABLE_TO_VERIFY
        if not ai_synthesis_ran:
            return VerificationStatus.ANALYSIS_FAILED
        return VerificationStatus.NO_DEPENDENCY_FOUND

    if deterministic_evidence_count > 0:
        return VerificationStatus.LIKELY

    return VerificationStatus.NEEDS_REVIEW

def derive_risk_level(coverage_ratio: float, all_anchored_items_likely: bool) -> str:
    if coverage_ratio is None or coverage_ratio < 0:
        return 'NONE'
    percent = coverage_ratio * 100
    if percent <= 0:
        return 'NONE'
    if percent >= 67 and all_anchored_items_likely:
        return 'CRITICAL'
    if percent >= 67:
        return 'HIGH'
    if percent >= 34:
        return 'MAJOR'
    return 'MINOR'
