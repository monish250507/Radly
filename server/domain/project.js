/**
 * ResearchProject and Persistence Interface
 *
 * ResearchProject is the root domain aggregate. It groups:
 *   - all ResearchArtifacts (code + paper elements)
 *   - all Evidence records
 *   - all ImpactFindings
 *   - the AnalysisVersion that produced them
 *
 * Persistence contract:
 *   - All objects are plain JSON-serializable records.
 *   - No database is instantiated here.
 *   - The persistence interface is defined as a plain object with async methods.
 *   - A development in-memory implementation is provided.
 *   - A Vercel-compatible durable backend (e.g. Vercel KV, PlanetScale)
 *     can be attached by implementing the same interface.
 *
 * Current state: development only. In-memory, no durability across requests.
 */

import { VerificationStatus, AnalysisState } from './constants.js';

// ---------------------------------------------------------------------------
// ResearchProject factory
// ---------------------------------------------------------------------------

/**
 * Create a ResearchProject aggregate.
 *
 * @param {object} opts
 * @param {object} opts.analysisVersion  - AnalysisVersion record
 * @param {object} opts.artifacts        - { codeArtifacts, sectionArtifacts, equationArtifacts, tableArtifacts, all }
 * @param {Array}  opts.evidenceRecords  - All Evidence records
 * @param {Array}  opts.findings         - All ImpactFinding records
 * @param {string} opts.query            - The change query that triggered the analysis
 * @param {string} opts.overallStatus    - VerificationStatus for the whole analysis
 */
export function makeResearchProject({
  analysisVersion,
  artifacts,
  evidenceRecords,
  findings,
  query,
  overallStatus
}) {
  return {
    projectId:       `proj_${analysisVersion.versionId}`,
    analysisVersion,
    query:           query || '',
    overallStatus:   overallStatus || VerificationStatus.UNABLE_TO_VERIFY,
    artifacts: {
      code:      artifacts?.codeArtifacts || [],
      sections:  artifacts?.sectionArtifacts || [],
      equations: artifacts?.equationArtifacts || [],
      tables:    artifacts?.tableArtifacts || [],
      total:     (artifacts?.all || []).length
    },
    evidenceRecords:  evidenceRecords || [],
    findings:         findings || [],
    summary: {
      totalArtifacts:        (artifacts?.all || []).length,
      totalEvidence:         (evidenceRecords || []).length,
      totalFindings:         (findings || []).length,
      findingsWithEvidence:  (findings || []).filter(f => f.hasEvidence).length,
      findingsNeedingReview: (findings || []).filter(
        f => f.status === VerificationStatus.NEEDS_REVIEW
      ).length
    },
    createdAt: new Date().toISOString()
  };
}

// ---------------------------------------------------------------------------
// Persistence Interface Definition
//
// This is the contract any persistence backend must implement.
// It is defined as a plain JS object of async functions.
//
// Vercel-compatible requirements:
//   - Must not use process-global mutable state between serverless invocations
//   - Must not use local filesystem as durable storage
//   - Must serialize/deserialize plain JSON objects
//   - Must be replaceable with Vercel KV, PlanetScale, Supabase, etc.
// ---------------------------------------------------------------------------

/**
 * Creates a persistence interface stub.
 * In production, replace the method implementations with real storage.
 *
 * Current implementation: in-memory Map (dev/test only, not durable).
 * This is explicitly labeled as development state.
 *
 * PRODUCTION NOTE: On Vercel, each serverless invocation may be a different
 * process. This in-memory store does NOT persist across requests in production.
 * Attach a Vercel KV or external DB by replacing these methods.
 */
export function createPersistenceInterface() {
  // Dev-only: in-memory store. Not durable. Not shared across requests.
  const _devStore = new Map();

  return {
    /**
     * Development mode indicator. Consumers can check this before trusting
     * that stored data will survive beyond the current request.
     */
    isDevelopmentMode: true,
    isDurable: false,

    /**
     * Save a ResearchProject. Returns the saved project.
     * In production: write to Vercel KV / external DB.
     */
    async saveProject(project) {
      if (!project?.projectId) throw new Error('project.projectId required');
      _devStore.set(`project:${project.projectId}`, JSON.parse(JSON.stringify(project)));
      return project;
    },

    /**
     * Load a ResearchProject by ID.
     * Returns null if not found.
     */
    async loadProject(projectId) {
      return _devStore.get(`project:${projectId}`) || null;
    },

    /**
     * List all stored project IDs (dev helper only).
     */
    async listProjectIds() {
      return [..._devStore.keys()]
        .filter(k => k.startsWith('project:'))
        .map(k => k.replace('project:', ''));
    },

    /**
     * Check if the persistence layer is available.
     */
    async healthCheck() {
      return {
        available: true,
        mode: 'development-in-memory',
        durable: false,
        note: 'In-memory store. Data is lost on process restart. ' +
              'Attach Vercel KV or external DB for production persistence.'
      };
    }
  };
}

// ---------------------------------------------------------------------------
// Module-level dev store instance
// WARNING: This is development-only. Vercel may re-initialize this between
// invocations. Do not rely on it for user-facing persistence.
// ---------------------------------------------------------------------------
export const devPersistence = createPersistenceInterface();
