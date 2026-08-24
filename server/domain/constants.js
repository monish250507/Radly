/**
 * PaperBlast Domain Constants
 * Schema version must be bumped whenever any domain object shape changes.
 * This enables stale-analysis detection across analysis runs.
 */

export const SCHEMA_VERSION = '1.0.0';

// ---------------------------------------------------------------------------
// Artifact Types
// ---------------------------------------------------------------------------
export const ArtifactType = Object.freeze({
  CODE:           'CODE',          // Source code file, function, class, variable
  CONFIG:         'CONFIG',        // Configuration file entry (JSON/YAML key-value)
  DATASET:        'DATASET',       // Dataset reference or loading call
  PREPROCESSING:  'PREPROCESSING', // Data preprocessing step
  EXPERIMENT:     'EXPERIMENT',    // Experiment script / training run
  RESULT:         'RESULT',        // Logged metric, result file
  METRIC:         'METRIC',        // Specific metric value (e.g. accuracy=98.3%)
  FIGURE:         'FIGURE',        // Generated figure / plot reference
  TABLE:          'TABLE',         // Table in paper or result file
  EQUATION:       'EQUATION',      // Mathematical equation
  CLAIM:          'CLAIM',         // Explicit textual claim in the manuscript
  SECTION:        'SECTION',       // Manuscript section heading + body
  ENVIRONMENT:    'ENVIRONMENT'    // Runtime environment (Python version, GPU, etc.)
});

// ---------------------------------------------------------------------------
// Evidence Types — epistemic strength ordering (weakest → strongest)
// ---------------------------------------------------------------------------
export const EvidenceType = Object.freeze({
  /**
   * The relationship was established by keyword/symbol text overlap only.
   * Weakest evidence. Max verification: NEEDS_REVIEW.
   */
  SEMANTIC:            'SEMANTIC',

  /**
   * An LLM produced the claim. LLM output is NOT evidence.
   * It is a hypothesis requiring human review. Max verification: NEEDS_REVIEW.
   */
  INFERRED:            'INFERRED',

  /**
   * A human explicitly asserted this relationship.
   * Max verification: LIKELY (still not reproducibly observed).
   */
  USER_PROVIDED:       'USER_PROVIDED',

  /**
   * The relationship was observed during code execution (e.g., runtime trace).
   * Max verification: LIKELY (execution context still needed for VERIFIED).
   */
  EXECUTION_OBSERVED:  'EXECUTION_OBSERVED',

  /**
   * The relationship was established by deterministic static analysis
   * (e.g., exact variable assignment → exact paper equation citation).
   * Max verification: VERIFIED. Not yet achievable by current engine.
   */
  DETERMINISTIC:       'DETERMINISTIC'
});

// ---------------------------------------------------------------------------
// Relationship Types between evidence source and target artifacts
// ---------------------------------------------------------------------------
export const RelationshipType = Object.freeze({
  PARAMETER_REFERENCE:    'PARAMETER_REFERENCE',   // Code param ↔ paper text value
  SYMBOL_APPEARS_IN:      'SYMBOL_APPEARS_IN',     // Code symbol text found in section
  KEYWORD_OVERLAP:        'KEYWORD_OVERLAP',        // Query keyword found in section
  EQUATION_VARIABLE:      'EQUATION_VARIABLE',     // Code var matches equation variable
  CLAIM_VALIDATES:        'CLAIM_VALIDATES',        // Code result validates a paper claim
  FIGURE_GENERATED_BY:    'FIGURE_GENERATED_BY',   // Figure produced by code path
  TABLE_POPULATED_BY:     'TABLE_POPULATED_BY',    // Table values from code output
  AI_SUGGESTED:           'AI_SUGGESTED',          // LLM asserted this relationship
  UNKNOWN:                'UNKNOWN'
});

// ---------------------------------------------------------------------------
// Verification Status — re-exported for consumers of the domain module
// Max status per evidence type:
//   SEMANTIC          → NEEDS_REVIEW
//   INFERRED          → NEEDS_REVIEW
//   USER_PROVIDED     → LIKELY
//   EXECUTION_OBSERVED → LIKELY
//   DETERMINISTIC     → VERIFIED
// ---------------------------------------------------------------------------
export const VerificationStatus = Object.freeze({
  VERIFIED:             'VERIFIED',
  LIKELY:               'LIKELY',
  NEEDS_REVIEW:         'NEEDS_REVIEW',
  NO_DEPENDENCY_FOUND:  'NO_DEPENDENCY_FOUND',
  UNABLE_TO_VERIFY:     'UNABLE_TO_VERIFY',
  ANALYSIS_FAILED:      'ANALYSIS_FAILED',
  CONFLICTING_EVIDENCE: 'CONFLICTING_EVIDENCE'   // NEW: contradictory evidence found
});

// ---------------------------------------------------------------------------
// Analysis lifecycle states
// ---------------------------------------------------------------------------
export const AnalysisState = Object.freeze({
  CURRENT: 'CURRENT',
  STALE:   'STALE',    // source versions no longer match analysis versions
  PARTIAL: 'PARTIAL'   // some inputs changed but analysis not re-run
});

// ---------------------------------------------------------------------------
// Extraction status for artifacts
// ---------------------------------------------------------------------------
export const ExtractionStatus = Object.freeze({
  OK:      'OK',       // Artifact extracted cleanly
  PARTIAL: 'PARTIAL',  // Extracted but with warnings (e.g., truncated)
  FAILED:  'FAILED'    // Extraction failed; artifact may be incomplete
});

/**
 * Returns the maximum VerificationStatus achievable for a given EvidenceType.
 */
export function maxVerificationForEvidence(evidenceType) {
  switch (evidenceType) {
    case EvidenceType.DETERMINISTIC:       return VerificationStatus.VERIFIED;
    case EvidenceType.EXECUTION_OBSERVED:  return VerificationStatus.LIKELY;
    case EvidenceType.USER_PROVIDED:       return VerificationStatus.LIKELY;
    case EvidenceType.INFERRED:            return VerificationStatus.NEEDS_REVIEW;
    case EvidenceType.SEMANTIC:            return VerificationStatus.NEEDS_REVIEW;
    default:                               return VerificationStatus.UNABLE_TO_VERIFY;
  }
}
