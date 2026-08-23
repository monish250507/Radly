/**
 * PaperBlast Verification Status Model
 *
 * Epistemic rules enforced by this module:
 * - A conclusion must never become stronger than its evidence.
 * - LLM output is not evidence. It is a hypothesis that requires review.
 * - Keyword/symbol text overlap is not deterministic proof.
 * - If no dependency can be established: NO_DEPENDENCY_FOUND.
 * - If processing fails: ANALYSIS_FAILED.
 * - If a relationship is plausible but not proven: NEEDS_REVIEW or LIKELY.
 * - VERIFIED is reserved for deterministic, reproducible evidence only.
 */

export const VerificationStatus = Object.freeze({
  /**
   * Deterministic, reproducible evidence established the dependency.
   * e.g. exact variable assignment → section citation with line-level anchoring.
   * NOTE: the current engine does not yet produce VERIFIED claims.
   * Reserved for future call-graph or citation analysis.
   */
  VERIFIED: 'VERIFIED',

  /**
   * Multiple converging signals (keyword match + AST symbol + AI agreement)
   * make the dependency highly plausible, but not deterministically proven.
   */
  LIKELY: 'LIKELY',

  /**
   * A signal (keyword overlap, AI suggestion) found a possible dependency.
   * Human review is required before treating this as a confirmed finding.
   * This is the MAXIMUM status LLM output may receive.
   */
  NEEDS_REVIEW: 'NEEDS_REVIEW',

  /**
   * No keyword, symbol, or AI match found any dependency between the
   * proposed change and any paper element.
   */
  NO_DEPENDENCY_FOUND: 'NO_DEPENDENCY_FOUND',

  /**
   * A signal was found but could not be validated against the real document
   * (e.g., AI returned a section_id that does not exist in the parsed paperAST).
   */
  UNABLE_TO_VERIFY: 'UNABLE_TO_VERIFY',

  /**
   * Processing failed (AI error, parse error, malformed input).
   * No finding should be reported as a positive result.
   */
  ANALYSIS_FAILED: 'ANALYSIS_FAILED'
});

/**
 * Build a structured evidence record.
 */
export function makeEvidence(type, verification, detail, extra = {}) {
  return { type, verification, detail, ...extra };
}

/**
 * Derive the overall analysis status from processing outcomes.
 *
 * @param {object} opts
 * @param {boolean} opts.hadProcessingError  - True if a non-recoverable error occurred
 * @param {number}  opts.deterministicEvidenceCount - Count of VERIFIED evidence items
 * @param {number}  opts.anchoredClaimCount  - Count of NEEDS_REVIEW items with valid IDs
 * @param {number}  opts.unanchoredClaimCount - Count of UNABLE_TO_VERIFY items
 * @param {boolean} opts.aiSynthesisRan      - Whether Groq synthesis completed
 * @returns {string} A VerificationStatus value
 */
export function resolveOverallStatus({
  hadProcessingError,
  deterministicEvidenceCount,
  anchoredClaimCount,
  unanchoredClaimCount,
  aiSynthesisRan
}) {
  if (hadProcessingError) return VerificationStatus.ANALYSIS_FAILED;

  if (deterministicEvidenceCount === 0 && anchoredClaimCount === 0) {
    if (unanchoredClaimCount > 0) return VerificationStatus.UNABLE_TO_VERIFY;
    if (!aiSynthesisRan) return VerificationStatus.ANALYSIS_FAILED;
    return VerificationStatus.NO_DEPENDENCY_FOUND;
  }

  if (deterministicEvidenceCount > 0) return VerificationStatus.LIKELY;

  // anchoredClaimCount > 0, deterministicEvidenceCount === 0
  return VerificationStatus.NEEDS_REVIEW;
}

/**
 * Derive a risk level from the ratio of affected sections to total sections.
 * Risk is only meaningful when there are anchored claims.
 *
 * @param {number}  coverageRatio           - Fraction of sections affected (0–1)
 * @param {boolean} allAnchoredItemsLikely  - True if all items are LIKELY or better
 * @returns {string} CRITICAL | HIGH | MAJOR | MINOR | NONE
 */
export function deriveRiskLevel(coverageRatio, allAnchoredItemsLikely) {
  if (!(coverageRatio >= 0)) return 'NONE';
  const percent = coverageRatio * 100;
  if (percent <= 0) return 'NONE';
  if (percent >= 67 && allAnchoredItemsLikely) return 'CRITICAL';
  if (percent >= 67) return 'HIGH';
  if (percent >= 34) return 'MAJOR';
  return 'MINOR';
}
