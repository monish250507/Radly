import { callGroqAPI } from './groqClient.js';
import { logger } from './logger.js';
import {
  VerificationStatus,
  makeEvidence,
  resolveOverallStatus,
  deriveRiskLevel
} from './statusModel.js';

// ---------------------------------------------------------------------------
// Text helpers
// ---------------------------------------------------------------------------

/**
 * Truncate at a sentence boundary. Only used for display snippets.
 */
function truncateAtSentence(text, maxChars = 350) {
  if (!text || typeof text !== 'string') return '';
  const trimmed = text.trim();
  if (trimmed.length <= maxChars) return trimmed;
  const sliced = trimmed.slice(0, maxChars);
  const lastPeriod = sliced.lastIndexOf('.');
  if (lastPeriod > 60) return sliced.slice(0, lastPeriod + 1);
  const lastSpace = sliced.lastIndexOf(' ');
  if (lastSpace > 60) return sliced.slice(0, lastSpace) + '.';
  return sliced + '.';
}

/**
 * Validate that a risk value is one of the allowed strings.
 */
const VALID_RISKS = new Set(['CRITICAL', 'HIGH', 'MAJOR', 'MINOR']);
function isValidRisk(r) {
  return typeof r === 'string' && VALID_RISKS.has(r.toUpperCase());
}

// ---------------------------------------------------------------------------
// Symbol-to-paper matcher (deterministic, returns NEEDS_REVIEW evidence only)
// ---------------------------------------------------------------------------

/**
 * Keyword and symbol overlap matching. This is heuristic, not deterministic
 * proof. All matches receive verification = NEEDS_REVIEW.
 */
function matchSymbolsToPaper(codeSymbols, paperAST, changeQuery) {
  const matches = [];
  const seenEdgeKeys = new Set();
  const queryLower = (changeQuery || '').toLowerCase();
  const sections = paperAST.sections || [];

  // Query keyword ↔ section text overlap
  const words = queryLower.split(/\W+/).filter(w => w.length > 3);
  for (const sec of sections) {
    const secText = (sec.text || '').toLowerCase();
    const secTitle = (sec.title || '').toLowerCase();
    for (const w of words) {
      if (secText.includes(w) || secTitle.includes(w)) {
        const edgeKey = `query:${w}->${sec.id}`;
        if (!seenEdgeKeys.has(edgeKey)) {
          seenEdgeKeys.add(edgeKey);
          matches.push({
            symbol: `Query Keyword (${w})`,
            target: sec.title,
            targetId: sec.id,
            targetType: 'Section',
            evidenceBasis: 'keyword_match',
            verification: VerificationStatus.NEEDS_REVIEW,
            reason: `Query keyword '${w}' appears in section '${sec.title}' (keyword overlap, not deterministic proof)`
          });
        }
      }
    }
  }

  // Code symbol ↔ section/equation text overlap
  for (const sym of (codeSymbols || [])) {
    const symbolStr = sym.symbol;
    if (!symbolStr || symbolStr.length === 0) continue;

    let symbolRegex = null;
    try {
      if (symbolStr.length <= 2) {
        symbolRegex = new RegExp(`\\b${symbolStr}\\b`, 'i');
      } else {
        symbolRegex = new RegExp(symbolStr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
      }
    } catch (e) {
      symbolRegex = null;
    }

    for (const sec of sections) {
      const secText = sec.text || '';
      const hasMatch = symbolRegex
        ? symbolRegex.test(secText)
        : secText.toLowerCase().includes(symbolStr.toLowerCase());

      if (hasMatch) {
        const edgeKey = `${sym.file}:${sym.line}:${sym.symbol}->${sec.id}`;
        if (!seenEdgeKeys.has(edgeKey)) {
          seenEdgeKeys.add(edgeKey);
          matches.push({
            symbol: `${sym.file}:${sym.line} (${sym.symbol})`,
            target: sec.title,
            targetId: sec.id,
            targetType: 'Section',
            evidenceBasis: 'ast_symbol',
            verification: VerificationStatus.NEEDS_REVIEW,
            reason: `Symbol '${sym.symbol}' from ${sym.file}:${sym.line} appears in section '${sec.title}' (text presence, not call-graph proof)`
          });
        }
      }
    }

    for (const eq of (paperAST.equations || [])) {
      if (symbolRegex && symbolRegex.test(eq.content)) {
        const edgeKey = `${sym.file}:${sym.line}:${sym.symbol}->${eq.id}`;
        if (!seenEdgeKeys.has(edgeKey)) {
          seenEdgeKeys.add(edgeKey);
          matches.push({
            symbol: `${sym.file}:${sym.line} (${sym.symbol})`,
            target: eq.label,
            targetId: eq.id,
            targetType: 'Equation',
            evidenceBasis: 'ast_symbol',
            verification: VerificationStatus.NEEDS_REVIEW,
            reason: `Symbol '${sym.symbol}' found in equation content '${eq.label}' (text presence only)`
          });
        }
      }
    }
  }

  return matches;
}

// ---------------------------------------------------------------------------
// AI output validation — guards against malformed or hallucinated content
// ---------------------------------------------------------------------------

/**
 * Validates and filters an AI-returned affected_sections array.
 * Sections whose section_id does not exist in paperAST are marked UNABLE_TO_VERIFY.
 * Sections with invalid risk values are corrected to MINOR or marked UNABLE_TO_VERIFY.
 *
 * EPISTEMIC RULE: LLM output is not evidence. All AI-produced sections receive
 * at most verification = NEEDS_REVIEW even when section_id resolves correctly.
 *
 * @returns {{ valid: Array, invalid: Array }}
 */
function validateAISections(aiSections, paperAST) {
  const sections = paperAST.sections || [];
  const sectionIndex = new Map(sections.map(s => [s.id, s]));
  const valid = [];
  const invalid = [];

  if (!Array.isArray(aiSections)) return { valid, invalid };

  for (const item of aiSections) {
    // Reject non-objects
    if (!item || typeof item !== 'object') {
      invalid.push({ item, reason: 'not_an_object' });
      continue;
    }

    const sectionId = item.section_id;
    const resolvedSection = sectionIndex.get(sectionId);

    if (!resolvedSection) {
      // section_id not found in real paperAST — cannot be trusted
      invalid.push({ item, reason: 'section_id_not_in_paperAST', section_id: sectionId });
      continue;
    }

    const risk = isValidRisk(item.risk) ? item.risk.toUpperCase() : null;
    if (!risk) {
      // Risk field missing or invalid — mark this section unable to verify
      invalid.push({ item, reason: 'invalid_risk_value', value: item.risk });
      valid.push({
        section_id: resolvedSection.id,
        title: resolvedSection.title,
        risk: 'MINOR',
        verification: VerificationStatus.UNABLE_TO_VERIFY,
        evidence_basis: 'ai_synthesized',
        reason: item.reason || '(AI reason not provided)',
        current_text: truncateAtSentence(resolvedSection.text, 350),
        suggested_text: item.suggested_text
          ? truncateAtSentence(String(item.suggested_text), 350)
          : null
      });
      continue;
    }

    // Valid section — LLM says it's affected. Mark NEEDS_REVIEW; LLM is not proof.
    valid.push({
      section_id: resolvedSection.id,
      title: resolvedSection.title,
      risk,
      // confidence_score deliberately omitted — LLM self-reported confidence is not evidence
      verification: VerificationStatus.NEEDS_REVIEW,
      evidence_basis: 'ai_synthesized',
      reason: typeof item.reason === 'string' && item.reason.trim()
        ? item.reason.trim()
        : '(AI did not provide a reason)',
      current_text: truncateAtSentence(resolvedSection.text, 350),
      suggested_text: item.suggested_text
        ? truncateAtSentence(String(item.suggested_text), 350)
        : null
    });
  }

  return { valid, invalid };
}

/**
 * Validates AI-returned equations/tables against real paperAST.
 * Returns only items whose ID exists in the real AST.
 */
function validateAIEquationsOrTables(aiItems, realItems, idPrefix) {
  if (!Array.isArray(aiItems) || !Array.isArray(realItems)) return [];
  const realIds = new Set(realItems.map(x => x.id));
  return aiItems
    .filter(item => item && realIds.has(item.id))
    .map(item => ({
      id: item.id,
      label: item.label || item.id,
      risk: isValidRisk(item.risk) ? item.risk.toUpperCase() : 'MINOR',
      verification: VerificationStatus.NEEDS_REVIEW,
      evidence_basis: 'ai_synthesized',
      explanation: typeof item.explanation === 'string'
        ? item.explanation.trim()
        : '(AI did not provide an explanation)'
    }));
}

// ---------------------------------------------------------------------------
// Assemble honest agent trace from real processing data
// ---------------------------------------------------------------------------

function buildHonestAgentTrace({ codeSymbolsCount, sectionsCount, equationsCount, staticMatchCount, engineMode, aiValidSections, aiInvalidSections }) {
  const trace = [
    {
      agent: 'Code AST Dependency Agent',
      role: 'Program Analysis & Symbol Extraction',
      output_summary: `Indexed ${codeSymbolsCount} AST symbols across source files.`
    },
    {
      agent: 'Manuscript Impact Analyst Agent',
      role: 'Paper AST Parsing & Equation Matching',
      output_summary: `Parsed ${sectionsCount} manuscript sections and ${equationsCount} equations. Found ${staticMatchCount} keyword/symbol overlaps (NEEDS_REVIEW).`
    }
  ];

  if (engineMode === 'ai_synthesized') {
    trace.push({
      agent: 'Skeptic Verification Arbiter Agent',
      role: 'AI Output Validation & Section Reconciliation',
      output_summary: `AI synthesis ran. Validated ${aiValidSections} sections against paperAST; rejected ${aiInvalidSections} sections with unresolvable IDs or invalid fields.`
    });
  } else {
    trace.push({
      agent: 'Skeptic Verification Arbiter Agent',
      role: 'Static AST Reachability (AI Unavailable)',
      output_summary: `AI synthesis did not run. Returning deterministic keyword/symbol overlap findings only. All results are NEEDS_REVIEW at best.`
    });
  }

  return trace;
}

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------

/**
 * Multi-Agent Research Code & Paper Impact Engine.
 *
 * EPISTEMIC CONTRACT:
 *   - LLM output is not evidence. All AI sections → NEEDS_REVIEW max.
 *   - Keyword overlap is not deterministic proof → NEEDS_REVIEW.
 *   - No affected sections found → NO_DEPENDENCY_FOUND (not fabricated sections).
 *   - Groq failure → ANALYSIS_FAILED (not a fake static result).
 *   - Confidence scores are never fabricated. confidence_score is always null.
 *   - overall_impact_score is null when it cannot be computed truthfully.
 */
export async function calculateBlastRadius(codeSymbols, paperAST, queryOrCodeChange) {
  const startTime = Date.now();

  // Agent 1 — Deterministic static keyword/symbol matching
  const staticMatches = matchSymbolsToPaper(codeSymbols, paperAST, queryOrCodeChange);

  const sections = paperAST.sections || [];
  const equations = paperAST.equations || [];
  const tables = paperAST.tables || [];

  // Build LLM prompt — no forced-finding instructions
  const systemPrompt = `You are a Skeptic Verification Arbiter that evaluates whether a proposed code or parameter change affects sections of a research paper.

Your job is to return ONLY the sections you can provide a specific, substantiated reason for. If you cannot identify a clear dependency, return an empty affected_sections array.

STRICT RULES:
- Only include sections whose section_id exactly matches one of the provided section IDs.
- Do not invent section IDs.
- Do not force-include sections just to have results.
- If no section is clearly affected, return affected_sections as [].
- overall_impact_score should reflect genuine concern (0 = no impact found, 100 = catastrophic).
- Do not fabricate. If uncertain, omit.

Output must be a valid JSON object:
{
  "overall_impact_score": <number 0-100 or null if genuinely unknown>,
  "risk_level": "<CRITICAL | HIGH | MAJOR | MINOR | NONE>",
  "affected_sections": [
    {
      "section_id": "<exact id from input sections list>",
      "title": "<string>",
      "risk": "<CRITICAL | HIGH | MAJOR | MINOR>",
      "reason": "<specific, substantiated reason — not generic>",
      "suggested_text": "<optional revised text>"
    }
  ],
  "affected_equations": [
    { "id": "<exact id from input>", "label": "<string>", "risk": "<CRITICAL|HIGH|MAJOR|MINOR>", "explanation": "<string>" }
  ],
  "affected_tables": [
    { "id": "<exact id from input>", "label": "<string>", "risk": "<CRITICAL|HIGH|MAJOR|MINOR>", "explanation": "<string>" }
  ],
  "lineage_graph": [
    { "source": "<Code Symbol / File:Line>", "target": "<Paper Section>", "relationship": "<string>" }
  ]
}`;

  const compactSymbols = (codeSymbols || []).slice(0, 10).map(s => ({
    symbol: s.symbol,
    type: s.type,
    value: String(s.value || '').slice(0, 40),
    file: s.file,
    line: s.line
  }));

  const compactSections = sections.slice(0, 8).map(s => ({
    id: s.id,
    title: s.title,
    textSnippet: truncateAtSentence(s.text, 200)
  }));

  const compactEquations = equations.slice(0, 4).map(eq => ({
    id: eq.id,
    label: eq.label,
    content: (eq.content || '').slice(0, 80)
  }));

  const userPrompt = `[PROPOSED CHANGE]:
"${queryOrCodeChange}"

[CODE AST SYMBOLS]:
${JSON.stringify(compactSymbols, null, 2)}

[PAPER SECTIONS] (use these exact section_id values only):
${JSON.stringify(compactSections, null, 2)}

[PAPER EQUATIONS]:
${JSON.stringify(compactEquations, null, 2)}

[STATIC KEYWORD/SYMBOL OVERLAPS DETECTED]:
${JSON.stringify(staticMatches.slice(0, 6).map(m => ({ symbol: m.symbol, section: m.target, basis: m.evidenceBasis })), null, 2)}

Return a JSON object. Only include sections you can provide a substantiated reason for. Return affected_sections: [] if nothing is clearly affected.`;

  // -------------------------------------------------------------------------
  // Agent 2 — Groq synthesis attempt
  // -------------------------------------------------------------------------
  let aiResult = null;
  let engineMode = 'static_fallback';
  let groqError = null;

  try {
    aiResult = await callGroqAPI([{ role: 'user', content: userPrompt }], systemPrompt, true);
    engineMode = 'ai_synthesized';
  } catch (err) {
    groqError = err;
    logger.warn('Groq synthesis unavailable', { reason: err.message, code: err.code || null });
  }

  // -------------------------------------------------------------------------
  // If Groq failed — honest failure result, no fake static "success"
  // -------------------------------------------------------------------------
  if (groqError !== null) {
    const lineageGraph = staticMatches.slice(0, 8).map(m => ({
      source: m.symbol,
      target: m.target,
      relationship: m.reason,
      verification: m.verification
    }));

    // Static matches that actually resolved a real section
    const staticSectionIds = [...new Set(
      staticMatches
        .filter(m => m.targetType === 'Section' && sections.find(s => s.id === m.targetId))
        .map(m => m.targetId)
    )];

    // Honest static finding: only sections that had a real keyword/symbol hit
    const staticAffectedSections = staticSectionIds.map(id => {
      const sec = sections.find(s => s.id === id);
      const matchesForSec = staticMatches.filter(m => m.targetId === id);
      return {
        section_id: sec.id,
        title: sec.title,
        risk: 'MINOR', // keyword overlap alone justifies at most MINOR flagging
        verification: VerificationStatus.NEEDS_REVIEW,
        evidence_basis: 'keyword_match',
        reason: matchesForSec.map(m => m.reason).join(' | '),
        current_text: truncateAtSentence(sec.text, 350),
        suggested_text: null
      };
    });

    const overallStatus = resolveOverallStatus({
      hadProcessingError: true,
      deterministicEvidenceCount: 0,
      anchoredClaimCount: staticAffectedSections.length,
      unanchoredClaimCount: 0,
      aiSynthesisRan: false
    });

    return {
      status: VerificationStatus.ANALYSIS_FAILED,
      engine: {
        mode: 'static_fallback',
        error_summary: groqError.message || 'Groq API unavailable',
        note: 'AI synthesis failed. The following results are from deterministic keyword/symbol overlap only and require human review.'
      },
      overall_impact_score: null,       // not computable without AI
      risk_level: 'NONE',               // cannot assert impact without AI
      confidence_score: null,           // never fabricated
      execution_time_ms: Date.now() - startTime,
      cost_efficiency: {
        tokens_used_est: null,          // not observable without successful Groq response
        estimated_cost_usd: 0.00,
        hardware_accelerator: 'N/A — AI synthesis failed'
      },
      impact_summary: {
        sections_affected: staticAffectedSections.length,
        equations_affected: 0,          // cannot assess without AI
        tables_affected: 0              // cannot assess without AI
      },
      affected_sections: staticAffectedSections,
      affected_equations: [],
      affected_tables: [],
      lineage_graph: lineageGraph,
      agent_collaboration_trace: buildHonestAgentTrace({
        codeSymbolsCount: (codeSymbols || []).length,
        sectionsCount: sections.length,
        equationsCount: equations.length,
        staticMatchCount: staticMatches.length,
        engineMode: 'static_fallback',
        aiValidSections: 0,
        aiInvalidSections: 0
      })
    };
  }

  // -------------------------------------------------------------------------
  // Agent 3 — Validate and sanitize AI output
  // -------------------------------------------------------------------------

  // Guard: aiResult must be an object
  if (!aiResult || typeof aiResult !== 'object') {
    logger.error('AI returned non-object response', { type: typeof aiResult });
    return buildAnalysisFailedResult(startTime, codeSymbols, paperAST, staticMatches, 'AI returned non-object response');
  }

  const { valid: validSections, invalid: invalidSections } = validateAISections(
    aiResult.affected_sections,
    paperAST
  );

  const validEquations = validateAIEquationsOrTables(
    aiResult.affected_equations,
    equations,
    'eq'
  );

  const validTables = validateAIEquationsOrTables(
    aiResult.affected_tables,
    tables,
    'table'
  );

  if (invalidSections.length > 0) {
    logger.warn('AI returned sections with unresolvable or invalid IDs', {
      count: invalidSections.length,
      details: invalidSections.map(x => ({ id: x.item?.section_id, reason: x.reason }))
    });
  }

  // overall_impact_score: accept AI's value only if it's a real number in 0-100
  const rawScore = aiResult.overall_impact_score;
  const impactScore = (typeof rawScore === 'number' && rawScore >= 0 && rawScore <= 100)
    ? Math.round(rawScore)
    : null;

  // risk_level: accept if valid, else derive from coverage
  let riskLevel = 'NONE';
  if (aiResult.risk_level && VALID_RISKS.has(aiResult.risk_level.toUpperCase())) {
    riskLevel = aiResult.risk_level.toUpperCase();
  } else if (validSections.length > 0) {
    const coverageRatio = validSections.length / Math.max(sections.length, 1);
    const allLikely = validSections.every(s => s.verification === VerificationStatus.NEEDS_REVIEW);
    riskLevel = deriveRiskLevel(coverageRatio, allLikely);
  }

  // Lineage graph: prefer AI's if present, else use static matches
  const lineageGraph = (Array.isArray(aiResult.lineage_graph) && aiResult.lineage_graph.length > 0)
    ? aiResult.lineage_graph.map(e => ({
        source: String(e.source || ''),
        target: String(e.target || ''),
        relationship: String(e.relationship || ''),
        verification: VerificationStatus.NEEDS_REVIEW
      }))
    : staticMatches.slice(0, 8).map(m => ({
        source: m.symbol,
        target: m.target,
        relationship: m.reason,
        verification: m.verification
      }));

  // Overall status
  const overallStatus = resolveOverallStatus({
    hadProcessingError: false,
    deterministicEvidenceCount: 0,         // keyword match is not deterministic
    anchoredClaimCount: validSections.length,
    unanchoredClaimCount: invalidSections.length,
    aiSynthesisRan: true
  });

  return {
    status: overallStatus,
    engine: {
      mode: 'ai_synthesized',
      fallback_reason: null,
      validation_summary: {
        sections_accepted: validSections.length,
        sections_rejected: invalidSections.length,
        equations_accepted: validEquations.length,
        tables_accepted: validTables.length
      }
    },
    overall_impact_score: impactScore,
    risk_level: riskLevel,
    confidence_score: null,   // never fabricated
    execution_time_ms: Date.now() - startTime,
    cost_efficiency: {
      tokens_used_est: null,  // not observable from response body
      estimated_cost_usd: 0.00,
      hardware_accelerator: 'Groq LPU Inference Engine'
    },
    impact_summary: {
      sections_affected: validSections.length,
      equations_affected: validEquations.length,
      tables_affected: validTables.length
    },
    affected_sections: validSections,
    affected_equations: validEquations,
    affected_tables: validTables,
    lineage_graph: lineageGraph,
    agent_collaboration_trace: buildHonestAgentTrace({
      codeSymbolsCount: (codeSymbols || []).length,
      sectionsCount: sections.length,
      equationsCount: equations.length,
      staticMatchCount: staticMatches.length,
      engineMode: 'ai_synthesized',
      aiValidSections: validSections.length,
      aiInvalidSections: invalidSections.length
    })
  };
}

// ---------------------------------------------------------------------------
// Internal helper: build an ANALYSIS_FAILED result (used when AI returns garbage)
// ---------------------------------------------------------------------------
function buildAnalysisFailedResult(startTime, codeSymbols, paperAST, staticMatches, errorSummary) {
  return {
    status: VerificationStatus.ANALYSIS_FAILED,
    engine: {
      mode: 'static_fallback',
      error_summary: errorSummary
    },
    overall_impact_score: null,
    risk_level: 'NONE',
    confidence_score: null,
    execution_time_ms: Date.now() - startTime,
    cost_efficiency: {
      tokens_used_est: null,
      estimated_cost_usd: 0.00,
      hardware_accelerator: 'N/A'
    },
    impact_summary: {
      sections_affected: 0,
      equations_affected: 0,
      tables_affected: 0
    },
    affected_sections: [],
    affected_equations: [],
    affected_tables: [],
    lineage_graph: staticMatches.slice(0, 8).map(m => ({
      source: m.symbol,
      target: m.target,
      relationship: m.reason,
      verification: m.verification
    })),
    agent_collaboration_trace: buildHonestAgentTrace({
      codeSymbolsCount: (codeSymbols || []).length,
      sectionsCount: (paperAST.sections || []).length,
      equationsCount: (paperAST.equations || []).length,
      staticMatchCount: staticMatches.length,
      engineMode: 'static_fallback',
      aiValidSections: 0,
      aiInvalidSections: 0
    })
  };
}
