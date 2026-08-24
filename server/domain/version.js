/**
 * AnalysisVersion domain object
 *
 * Records the exact provenance of an analysis run:
 * - which repository snapshot was used
 * - which manuscript version was analyzed
 * - which schema version produced the domain objects
 *
 * Used to detect STALE analyses when source versions change.
 * All fields are serializable. No class instances.
 */

import { createHash } from 'node:crypto';
import { SCHEMA_VERSION, AnalysisState } from './constants.js';
import { getVersionInfo } from '../versionInfo.js';

// ---------------------------------------------------------------------------
// Version ID generation
// ---------------------------------------------------------------------------

let _versionSeq = 0;
function nextVersionId() {
  _versionSeq++;
  return `av_${Date.now().toString(36)}_${_versionSeq.toString(36).padStart(4, '0')}`;
}

// ---------------------------------------------------------------------------
// Stable hashes for staleness detection
// ---------------------------------------------------------------------------

/**
 * Compute a stable snapshot hash from an array of code symbols.
 * Depends on symbol names + files + lines, not content values
 * (content changes are tracked via artifact contentHash, not here).
 */
export function repoSnapshotHash(codeSymbols) {
  if (!codeSymbols || codeSymbols.length === 0) return 'empty';
  const canonical = (codeSymbols || [])
    .map(s => `${s.file}:${s.line}:${s.symbol}`)
    .sort()
    .join('|');
  return createHash('sha1').update(canonical).digest('hex').slice(0, 16);
}

/**
 * Compute a stable hash from the raw paper text for change detection.
 */
export function manuscriptHash(rawText) {
  if (!rawText) return 'empty';
  return createHash('sha1').update(String(rawText)).digest('hex').slice(0, 16);
}

// ---------------------------------------------------------------------------
// AnalysisVersion factory
// ---------------------------------------------------------------------------

/**
 * Create an AnalysisVersion record for the current analysis run.
 *
 * @param {object} opts
 * @param {Array}  opts.codeSymbols     - Raw code symbols from codeParser
 * @param {object} opts.paperAST        - Raw paperAST from paperParser
 * @param {string} [opts.repoUrl]       - Repository URL or identifier
 * @param {string} [opts.manuscriptId]  - Manuscript filename or identifier
 */
export function makeAnalysisVersion({ codeSymbols, paperAST, repoUrl, manuscriptId }) {
  const serverVersion = getVersionInfo();
  const repoHash = repoSnapshotHash(codeSymbols);
  const paperHash = manuscriptHash(paperAST?.rawText);

  return {
    versionId:        nextVersionId(),
    schemaVersion:    SCHEMA_VERSION,
    serverVersion:    serverVersion.version,
    nodeVersion:      serverVersion.nodeVersion,
    commitSha:        serverVersion.commitSha || null,
    repoUrl:          repoUrl || null,
    repoSnapshotHash: repoHash,
    manuscriptId:     manuscriptId || null,
    manuscriptHash:   paperHash,
    symbolCount:      (codeSymbols || []).length,
    sectionCount:     (paperAST?.sections || []).length,
    createdAt:        new Date().toISOString(),
    state:            AnalysisState.CURRENT
  };
}

// ---------------------------------------------------------------------------
// Staleness detection
// ---------------------------------------------------------------------------

/**
 * Check whether a previous AnalysisVersion is still current given the
 * current inputs. Returns { stale: bool, reasons: string[] }
 *
 * Rules:
 *   - schemaVersion mismatch → STALE (domain objects incompatible)
 *   - manuscriptHash mismatch → STALE (paper changed)
 *   - repoSnapshotHash mismatch → STALE (code changed)
 */
export function checkStaleness(previousVersion, currentCodeSymbols, currentPaperAST) {
  const reasons = [];

  if (!previousVersion) {
    return { stale: false, reasons: [] };
  }

  if (previousVersion.schemaVersion !== SCHEMA_VERSION) {
    reasons.push(
      `Schema version changed: was ${previousVersion.schemaVersion}, now ${SCHEMA_VERSION}. Re-analysis required.`
    );
  }

  const currentRepoHash = repoSnapshotHash(currentCodeSymbols);
  if (previousVersion.repoSnapshotHash !== currentRepoHash) {
    reasons.push(
      `Repository snapshot changed (was ${previousVersion.repoSnapshotHash}, now ${currentRepoHash}). Code may have been modified.`
    );
  }

  const currentPaperHash = manuscriptHash(currentPaperAST?.rawText);
  if (previousVersion.manuscriptHash !== currentPaperHash) {
    reasons.push(
      `Manuscript changed (was ${previousVersion.manuscriptHash}, now ${currentPaperHash}). Paper may have been updated.`
    );
  }

  return { stale: reasons.length > 0, reasons };
}

/**
 * Mark an AnalysisVersion as stale.
 */
export function markStale(analysisVersion, reasons) {
  return {
    ...analysisVersion,
    state: AnalysisState.STALE,
    staleReasons: reasons
  };
}

// ---------------------------------------------------------------------------
// Validate AnalysisVersion
// ---------------------------------------------------------------------------

export function validateAnalysisVersion(av) {
  const errors = [];
  if (!av || typeof av !== 'object') return { valid: false, errors: ['must be an object'] };
  if (!av.versionId) errors.push('versionId required');
  if (!av.schemaVersion) errors.push('schemaVersion required');
  if (!av.createdAt) errors.push('createdAt required');
  if (!av.state || !Object.values(AnalysisState).includes(av.state)) {
    errors.push(`state must be one of: ${Object.values(AnalysisState).join(', ')}`);
  }
  return { valid: errors.length === 0, errors };
}
