/**
 * ImpactFinding domain object
 *
 * An ImpactFinding records that a proposed change to one artifact
 * is believed or known to affect another artifact, and WHY.
 *
 * Every finding MUST reference at least one Evidence record.
 * A finding without evidence is not a finding — it is speculation.
 *
 * All objects are serializable. No class instances.
 */

import { createHash } from 'node:crypto';
import { VerificationStatus } from './constants.js';

// ---------------------------------------------------------------------------
// ID generation
// ---------------------------------------------------------------------------

let _findingSeq = 0;
function nextFindingId() {
  _findingSeq++;
  return `find_${Date.now().toString(36)}_${_findingSeq.toString(36).padStart(4, '0')}`;
}

// ---------------------------------------------------------------------------
// ImpactFinding factory
// ---------------------------------------------------------------------------

/**
 * Create an ImpactFinding.
 *
 * @param {object} opts
 * @param {string} opts.changeReference      - Description of the proposed change (the query)
 * @param {string} opts.affectedArtifactId   - Artifact ID of the affected manuscript element
 * @param {string} opts.affectedArtifactType - ArtifactType of the affected element
 * @param {string} opts.affectedTitle        - Human-readable name (section title, eq label, etc.)
 * @param {string} opts.status               - VerificationStatus for this finding
 * @param {string} opts.risk                 - CRITICAL|HIGH|MAJOR|MINOR|NONE
 * @param {string} opts.reason               - Explanation of why this is affected
 * @param {string[]} opts.evidenceIds        - IDs of Evidence records backing this finding
 * @param {string} opts.analysisVersionId    - ID of the AnalysisVersion that produced this
 * @param {string|null} opts.currentText     - Current text snippet from the artifact
 * @param {string|null} opts.suggestedText   - Proposed revised text (may be null)
 */
export function makeImpactFinding({
  changeReference,
  affectedArtifactId,
  affectedArtifactType,
  affectedTitle,
  status,
  risk,
  reason,
  evidenceIds = [],
  analysisVersionId,
  currentText = null,
  suggestedText = null
}) {
  if (!Object.values(VerificationStatus).includes(status)) {
    throw new Error(`Invalid status for ImpactFinding: ${status}`);
  }
  const VALID_RISKS = new Set(['CRITICAL', 'HIGH', 'MAJOR', 'MINOR', 'NONE']);
  if (!VALID_RISKS.has((risk || '').toUpperCase())) {
    throw new Error(`Invalid risk for ImpactFinding: ${risk}`);
  }

  return {
    findingId:            nextFindingId(),
    changeReference:      changeReference || '',
    affectedArtifactId:   affectedArtifactId || null,
    affectedArtifactType: affectedArtifactType || null,
    affectedTitle:        affectedTitle || '',
    status,
    risk:                 risk.toUpperCase(),
    reason:               reason || '',
    evidenceIds:          evidenceIds,
    hasEvidence:          evidenceIds.length > 0,
    analysisVersionId:    analysisVersionId || null,
    currentText:          currentText || null,
    suggestedText:        suggestedText || null,
    createdAt:            new Date().toISOString()
  };
}

// ---------------------------------------------------------------------------
// Build findings from impactEngine output
// ---------------------------------------------------------------------------

/**
 * Convert validated AI-synthesized affected_sections into ImpactFindings.
 * Each section gets an ImpactFinding backed by its INFERRED evidence record.
 *
 * @param {Array}  validSections        - From validateAISections() in impactEngine
 * @param {Map}    sectionArtifactMap   - sectionId → artifactId
 * @param {Array}  aiEvidenceRecords    - Evidence records from evidenceFromAISections()
 * @param {string} changeReference      - The user's query string
 * @param {string} analysisVersionId
 */
export function findingsFromAISections(
  validSections,
  sectionArtifactMap,
  aiEvidenceRecords,
  changeReference,
  analysisVersionId
) {
  const evidenceBySection = new Map();
  for (const ev of (aiEvidenceRecords || [])) {
    if (ev.targetArtifactId) {
      if (!evidenceBySection.has(ev.targetArtifactId)) {
        evidenceBySection.set(ev.targetArtifactId, []);
      }
      evidenceBySection.get(ev.targetArtifactId).push(ev.evidenceId);
    }
  }

  return (validSections || []).map(sec => {
    const artId = sectionArtifactMap ? sectionArtifactMap.get(sec.section_id) : null;
    const evIds = artId ? (evidenceBySection.get(artId) || []) : [];

    return makeImpactFinding({
      changeReference,
      affectedArtifactId:   artId || null,
      affectedArtifactType: 'SECTION',
      affectedTitle:        sec.title || sec.section_id,
      status:               sec.verification || VerificationStatus.NEEDS_REVIEW,
      risk:                 sec.risk || 'MINOR',
      reason:               sec.reason || '',
      evidenceIds:          evIds,
      analysisVersionId,
      currentText:          sec.current_text || null,
      suggestedText:        sec.suggested_text || null
    });
  });
}

/**
 * Convert static-match affected sections into ImpactFindings.
 * These are NEEDS_REVIEW at most (keyword/symbol overlap only).
 */
export function findingsFromStaticSections(
  staticAffectedSections,
  sectionArtifactMap,
  staticEvidenceRecords,
  changeReference,
  analysisVersionId
) {
  // Build edge lookup: targetArtifactId → evidence IDs
  const evidenceByArtifact = new Map();
  for (const ev of (staticEvidenceRecords || [])) {
    if (ev.targetArtifactId) {
      if (!evidenceByArtifact.has(ev.targetArtifactId)) {
        evidenceByArtifact.set(ev.targetArtifactId, []);
      }
      evidenceByArtifact.get(ev.targetArtifactId).push(ev.evidenceId);
    }
  }

  return (staticAffectedSections || []).map(sec => {
    const artId = sectionArtifactMap ? sectionArtifactMap.get(sec.section_id) : null;
    const evIds = artId ? (evidenceByArtifact.get(artId) || []) : [];

    return makeImpactFinding({
      changeReference,
      affectedArtifactId:   artId || null,
      affectedArtifactType: 'SECTION',
      affectedTitle:        sec.title || sec.section_id,
      status:               VerificationStatus.NEEDS_REVIEW,
      risk:                 sec.risk || 'MINOR',
      reason:               sec.reason || '',
      evidenceIds:          evIds,
      analysisVersionId,
      currentText:          sec.current_text || null,
      suggestedText:        null
    });
  });
}

// ---------------------------------------------------------------------------
// Validate ImpactFinding
// ---------------------------------------------------------------------------

/**
 * Validate an ImpactFinding. Returns { valid: bool, errors: string[] }
 */
export function validateFinding(finding) {
  const errors = [];
  if (!finding || typeof finding !== 'object') {
    return { valid: false, errors: ['finding must be an object'] };
  }
  if (!finding.findingId) errors.push('findingId required');
  if (!Object.values(VerificationStatus).includes(finding.status)) {
    errors.push(`status must be a valid VerificationStatus`);
  }
  const VALID_RISKS = new Set(['CRITICAL', 'HIGH', 'MAJOR', 'MINOR', 'NONE']);
  if (!VALID_RISKS.has(finding.risk || '')) errors.push('risk must be CRITICAL|HIGH|MAJOR|MINOR|NONE');
  if (!Array.isArray(finding.evidenceIds)) errors.push('evidenceIds must be an array');
  if (!finding.createdAt) errors.push('createdAt required');
  return { valid: errors.length === 0, errors };
}
