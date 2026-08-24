/**
 * Evidence and EvidenceEdge domain objects
 *
 * Evidence is not analysis output — it is the factual record of WHY a finding
 * was made. Every ImpactFinding must reference one or more Evidence records.
 *
 * Epistemic rules:
 * - LLM output (INFERRED) → max NEEDS_REVIEW
 * - Keyword overlap (SEMANTIC) → max NEEDS_REVIEW
 * - User assertion (USER_PROVIDED) → max LIKELY
 * - Runtime trace (EXECUTION_OBSERVED) → max LIKELY
 * - Static deterministic (DETERMINISTIC) → max VERIFIED
 *
 * Evidence objects are plain serializable records. No class instances.
 */

import { createHash } from 'node:crypto';
import {
  EvidenceType,
  RelationshipType,
  VerificationStatus,
  maxVerificationForEvidence
} from './constants.js';

// ---------------------------------------------------------------------------
// ID generation
// ---------------------------------------------------------------------------

let _evidenceSeq = 0;
function nextEvidenceId() {
  _evidenceSeq++;
  return `ev_${Date.now().toString(36)}_${_evidenceSeq.toString(36).padStart(4, '0')}`;
}

// ---------------------------------------------------------------------------
// Evidence factory
// ---------------------------------------------------------------------------

/**
 * Create an Evidence record.
 *
 * @param {object} opts
 * @param {string} opts.sourceArtifactId  - ID of the code/config artifact
 * @param {string} opts.targetArtifactId  - ID of the section/equation/table artifact
 * @param {string} opts.exactLocation     - e.g. "clip/model.py:42" or "lines 11-30"
 * @param {string|null} opts.extractedValue - The actual value found (symbol name, keyword, etc.)
 * @param {string} opts.evidenceType      - One of EvidenceType
 * @param {string} opts.relationshipType  - One of RelationshipType
 * @param {string} opts.detail            - Human-readable explanation of the evidence
 * @param {string} opts.analysisVersion   - The AnalysisVersion.versionId that produced this
 */
export function makeEvidence({
  sourceArtifactId,
  targetArtifactId,
  exactLocation,
  extractedValue = null,
  evidenceType,
  relationshipType,
  detail,
  analysisVersion
}) {
  if (!Object.values(EvidenceType).includes(evidenceType)) {
    throw new Error(`Invalid evidenceType: ${evidenceType}`);
  }
  if (!Object.values(RelationshipType).includes(relationshipType)) {
    throw new Error(`Invalid relationshipType: ${relationshipType}`);
  }

  const verification = maxVerificationForEvidence(evidenceType);

  return {
    evidenceId:       nextEvidenceId(),
    sourceArtifactId: sourceArtifactId || null,
    targetArtifactId: targetArtifactId || null,
    exactLocation:    exactLocation || null,
    extractedValue:   extractedValue != null ? String(extractedValue) : null,
    evidenceType,
    relationshipType,
    verification,       // max achievable for this evidence type
    detail:             detail || '',
    analysisVersion:    analysisVersion || null,
    createdAt:          new Date().toISOString()
  };
}

// ---------------------------------------------------------------------------
// EvidenceEdge — lightweight lineage graph edge with evidence backing
// ---------------------------------------------------------------------------

/**
 * Create an EvidenceEdge — a directed edge in the bipartite lineage graph.
 * Each edge is backed by one or more Evidence records.
 *
 * @param {object} opts
 * @param {string} opts.sourceLabel       - Display label for source (code symbol)
 * @param {string} opts.targetLabel       - Display label for target (paper section)
 * @param {string} opts.sourceArtifactId
 * @param {string} opts.targetArtifactId
 * @param {string[]} opts.evidenceIds     - Evidence record IDs backing this edge
 * @param {string} opts.verification      - VerificationStatus for this edge
 * @param {string} opts.relationshipType  - RelationshipType
 * @param {string} opts.detail            - Human-readable description
 */
export function makeEvidenceEdge({
  sourceLabel,
  targetLabel,
  sourceArtifactId,
  targetArtifactId,
  evidenceIds = [],
  verification,
  relationshipType,
  detail
}) {
  if (verification && !Object.values(VerificationStatus).includes(verification)) {
    throw new Error(`Invalid verification: ${verification}`);
  }

  return {
    edgeId:           `edge_${createHash('sha1')
                        .update(`${sourceArtifactId}:${targetArtifactId}`)
                        .digest('hex').slice(0, 10)}`,
    sourceLabel:      sourceLabel || '',
    targetLabel:      targetLabel || '',
    sourceArtifactId: sourceArtifactId || null,
    targetArtifactId: targetArtifactId || null,
    evidenceIds:      evidenceIds,
    verification:     verification || VerificationStatus.UNABLE_TO_VERIFY,
    relationshipType: relationshipType || RelationshipType.UNKNOWN,
    detail:           detail || ''
  };
}

// ---------------------------------------------------------------------------
// Evidence from existing impactEngine static matches
// ---------------------------------------------------------------------------

/**
 * Convert impactEngine staticMatch records to Evidence + EvidenceEdge pairs.
 * Static matches use SEMANTIC evidence type (keyword/symbol text overlap).
 *
 * @param {Array} staticMatches - From matchSymbolsToPaper()
 * @param {Map<string,string>} sectionIdToArtifactId - sectionId → artifactId
 * @param {Map<string,string>} symbolKeyToArtifactId - "file:line:symbol" → artifactId
 * @param {string} analysisVersion
 */
export function evidenceFromStaticMatches(
  staticMatches,
  sectionIdToArtifactId,
  symbolKeyToArtifactId,
  analysisVersion
) {
  const evidenceRecords = [];
  const edges = [];

  for (const match of (staticMatches || [])) {
    const sourceArtifactId = symbolKeyToArtifactId
      ? symbolKeyToArtifactId.get(match.symbol) || null
      : null;
    const targetArtifactId = sectionIdToArtifactId
      ? sectionIdToArtifactId.get(match.targetId) || null
      : null;

    const isKeyword = match.evidenceBasis === 'keyword_match';
    const evidenceType = isKeyword ? EvidenceType.SEMANTIC : EvidenceType.SEMANTIC;
    const relType = isKeyword
      ? RelationshipType.KEYWORD_OVERLAP
      : RelationshipType.SYMBOL_APPEARS_IN;

    const ev = makeEvidence({
      sourceArtifactId,
      targetArtifactId,
      exactLocation:  match.symbol,
      extractedValue: isKeyword ? match.symbol.replace('Query Keyword (', '').replace(')', '') : null,
      evidenceType,
      relationshipType: relType,
      detail:          match.reason || '',
      analysisVersion
    });

    evidenceRecords.push(ev);

    const edge = makeEvidenceEdge({
      sourceLabel:      match.symbol,
      targetLabel:      match.target,
      sourceArtifactId,
      targetArtifactId,
      evidenceIds:      [ev.evidenceId],
      verification:     ev.verification,
      relationshipType: relType,
      detail:           match.reason || ''
    });

    edges.push(edge);
  }

  return { evidenceRecords, edges };
}

// ---------------------------------------------------------------------------
// Evidence from AI-synthesized affected sections
// ---------------------------------------------------------------------------

/**
 * Create INFERRED evidence records for AI-synthesized section findings.
 * These are hypotheses, not facts. Max verification: NEEDS_REVIEW.
 */
export function evidenceFromAISections(
  validSections,
  sectionArtifactMap,
  query,
  analysisVersion
) {
  const evidenceRecords = [];

  for (const sec of (validSections || [])) {
    const targetArtifactId = sectionArtifactMap
      ? sectionArtifactMap.get(sec.section_id) || null
      : null;

    const ev = makeEvidence({
      sourceArtifactId: null,   // AI has no specific source artifact
      targetArtifactId,
      exactLocation:    sec.section_id,
      extractedValue:   null,
      evidenceType:     EvidenceType.INFERRED,
      relationshipType: RelationshipType.AI_SUGGESTED,
      detail:           sec.reason || '(AI assertion without specific source)',
      analysisVersion
    });

    evidenceRecords.push(ev);
  }

  return evidenceRecords;
}

// ---------------------------------------------------------------------------
// Validate Evidence
// ---------------------------------------------------------------------------

/**
 * Validate an Evidence object. Returns { valid: bool, errors: string[] }
 */
export function validateEvidence(ev) {
  const errors = [];
  if (!ev || typeof ev !== 'object') return { valid: false, errors: ['evidence must be an object'] };
  if (!ev.evidenceId || typeof ev.evidenceId !== 'string') errors.push('evidenceId required');
  if (!ev.evidenceType || !Object.values(EvidenceType).includes(ev.evidenceType)) {
    errors.push(`evidenceType must be one of: ${Object.values(EvidenceType).join(', ')}`);
  }
  if (!ev.relationshipType || !Object.values(RelationshipType).includes(ev.relationshipType)) {
    errors.push(`relationshipType must be one of: ${Object.values(RelationshipType).join(', ')}`);
  }
  if (!ev.verification || !Object.values(VerificationStatus).includes(ev.verification)) {
    errors.push(`verification must be a valid VerificationStatus`);
  }
  // Epistemic invariant: verification must not exceed evidence type max
  const maxAllowed = maxVerificationForEvidence(ev.evidenceType);
  const ordering = [
    VerificationStatus.UNABLE_TO_VERIFY,
    VerificationStatus.ANALYSIS_FAILED,
    VerificationStatus.NO_DEPENDENCY_FOUND,
    VerificationStatus.NEEDS_REVIEW,
    VerificationStatus.LIKELY,
    VerificationStatus.VERIFIED
  ];
  const maxIdx = ordering.indexOf(maxAllowed);
  const actualIdx = ordering.indexOf(ev.verification);
  if (actualIdx > maxIdx) {
    errors.push(
      `verification ${ev.verification} exceeds max allowed (${maxAllowed}) for evidenceType ${ev.evidenceType}`
    );
  }
  return { valid: errors.length === 0, errors };
}
