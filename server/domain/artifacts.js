/**
 * ResearchArtifact — domain object
 *
 * Represents any discrete, identifiable research object: a code symbol,
 * a paper section, an equation, a table, a config value, etc.
 *
 * All artifacts are plain serializable objects (no class instances).
 * IDs are stable: same source + location → same ID across runs.
 */

import { createHash } from 'node:crypto';
import { ArtifactType, ExtractionStatus } from './constants.js';

// ---------------------------------------------------------------------------
// ID generation
// ---------------------------------------------------------------------------

/**
 * Create a stable, deterministic artifact ID from source + location.
 * Two artifacts with identical source/file/line produce the same ID.
 */
function stableId(type, source, location) {
  const input = `${type}:${source}:${location}`;
  return `art_${createHash('sha1').update(input).digest('hex').slice(0, 12)}`;
}

/**
 * Compute a short content hash for change detection.
 */
export function contentHash(text) {
  if (!text) return null;
  return createHash('sha1').update(String(text)).digest('hex').slice(0, 16);
}

// ---------------------------------------------------------------------------
// Factory functions — one per major artifact category
// ---------------------------------------------------------------------------

/**
 * Create a CODE artifact from a codeParser ASTSymbol.
 *
 * Input shape (codeParser output):
 *   { symbol, type, value, file, line }
 */
export function codeArtifactFromSymbol(sym, repoSource) {
  const location = `${sym.file}:${sym.line}`;
  const id = stableId(ArtifactType.CODE, repoSource || sym.file, location);
  return {
    artifactId:       id,
    artifactType:     ArtifactType.CODE,
    source:           repoSource || sym.file,
    filePath:         sym.file || null,
    exactLocation:    location,
    symbolName:       sym.symbol,
    symbolKind:       sym.type,              // Function|Variable|Class|ConfigKey|...
    extractedValue:   sym.value != null ? String(sym.value) : null,
    version:          null,                  // populated by AnalysisVersion
    contentHash:      contentHash(sym.symbol + ':' + sym.value),
    extractionStatus: ExtractionStatus.OK
  };
}

/**
 * Create a CONFIG artifact from a codeParser ASTSymbol of type ConfigKey.
 */
export function configArtifactFromSymbol(sym, repoSource) {
  const base = codeArtifactFromSymbol(sym, repoSource);
  return { ...base, artifactType: ArtifactType.CONFIG };
}

/**
 * Create a SECTION artifact from a paperParser section object.
 *
 * Input shape (paperParser output):
 *   { id, title, text, startLine, endLine, content }
 */
export function sectionArtifact(sec, manuscriptSource) {
  const id = stableId(ArtifactType.SECTION, manuscriptSource || 'manuscript', sec.id);
  return {
    artifactId:       id,
    artifactType:     ArtifactType.SECTION,
    source:           manuscriptSource || 'manuscript',
    filePath:         null,
    exactLocation:    `lines ${sec.startLine}–${sec.endLine}`,
    sectionId:        sec.id,               // paperParser's stable section ID
    title:            sec.title,
    extractedValue:   sec.text || null,
    version:          null,
    contentHash:      contentHash(sec.text),
    startLine:        sec.startLine,
    endLine:          sec.endLine,
    extractionStatus: ExtractionStatus.OK
  };
}

/**
 * Create an EQUATION artifact from a paperParser equation object.
 *
 * Input shape: { id, label, content, raw, type }
 */
export function equationArtifact(eq, manuscriptSource) {
  const id = stableId(ArtifactType.EQUATION, manuscriptSource || 'manuscript', eq.id);
  return {
    artifactId:       id,
    artifactType:     ArtifactType.EQUATION,
    source:           manuscriptSource || 'manuscript',
    filePath:         null,
    exactLocation:    eq.id,
    equationId:       eq.id,
    label:            eq.label,
    extractedValue:   eq.content || null,
    version:          null,
    contentHash:      contentHash(eq.content),
    equationType:     eq.type,
    extractionStatus: ExtractionStatus.OK
  };
}

/**
 * Create a TABLE artifact from a paperParser table object.
 *
 * Input shape: { id, label, caption, content, type }
 */
export function tableArtifact(tbl, manuscriptSource) {
  const id = stableId(ArtifactType.TABLE, manuscriptSource || 'manuscript', tbl.id);
  return {
    artifactId:       id,
    artifactType:     ArtifactType.TABLE,
    source:           manuscriptSource || 'manuscript',
    filePath:         null,
    exactLocation:    tbl.id,
    tableId:          tbl.id,
    label:            tbl.label,
    caption:          tbl.caption || null,
    extractedValue:   tbl.content || null,
    version:          null,
    contentHash:      contentHash(tbl.content),
    extractionStatus: ExtractionStatus.OK
  };
}

// ---------------------------------------------------------------------------
// Artifact index helpers
// ---------------------------------------------------------------------------

/**
 * Build a full artifact index from existing codeParser and paperParser outputs.
 * Returns { codeArtifacts, sectionArtifacts, equationArtifacts, tableArtifacts, all }
 */
export function buildArtifactIndex(codeSymbols, paperAST, repoSource, manuscriptSource) {
  const codeArtifacts = (codeSymbols || []).map(sym => {
    const isConfig = sym.type === 'ConfigKey';
    return isConfig
      ? configArtifactFromSymbol(sym, repoSource)
      : codeArtifactFromSymbol(sym, repoSource);
  });

  const sectionArtifacts = (paperAST?.sections || []).map(sec =>
    sectionArtifact(sec, manuscriptSource)
  );

  const equationArtifacts = (paperAST?.equations || []).map(eq =>
    equationArtifact(eq, manuscriptSource)
  );

  const tableArtifacts = (paperAST?.tables || []).map(tbl =>
    tableArtifact(tbl, manuscriptSource)
  );

  const all = [
    ...codeArtifacts,
    ...sectionArtifacts,
    ...equationArtifacts,
    ...tableArtifacts
  ];

  return { codeArtifacts, sectionArtifacts, equationArtifacts, tableArtifacts, all };
}

/**
 * Validate a ResearchArtifact object. Returns { valid: bool, errors: string[] }
 */
export function validateArtifact(artifact) {
  const errors = [];
  if (!artifact || typeof artifact !== 'object') {
    return { valid: false, errors: ['artifact must be an object'] };
  }
  if (!artifact.artifactId || typeof artifact.artifactId !== 'string') {
    errors.push('artifactId must be a non-empty string');
  }
  if (!artifact.artifactType || !Object.values(ArtifactType).includes(artifact.artifactType)) {
    errors.push(`artifactType must be one of: ${Object.values(ArtifactType).join(', ')}`);
  }
  if (!artifact.extractionStatus || !['OK', 'PARTIAL', 'FAILED'].includes(artifact.extractionStatus)) {
    errors.push('extractionStatus must be OK, PARTIAL, or FAILED');
  }
  return { valid: errors.length === 0, errors };
}
