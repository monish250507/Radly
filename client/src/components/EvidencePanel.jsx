import React, { useState } from 'react';
import VerificationBadge from './VerificationBadge.jsx';

/**
 * EvidencePanel — collapsible panel showing why a finding exists.
 *
 * Shows:
 *   - verification status
 *   - evidence basis (keyword_match | ast_symbol | ai_synthesized)
 *   - reason text
 *   - source location (file:line for code symbols)
 *   - analysis version ID for reproducibility
 *   - what cannot be verified
 *
 * Does NOT show: internal artifact IDs, evidence IDs, domain schema details.
 *
 * Props:
 *   impact          {object}  — affected_sections[i] from analysis
 *   analysisVersion {object}  — analysis.domain.analysisVersion (optional)
 *   defaultOpen     {boolean} — start expanded (default: false)
 */
export default function EvidencePanel({ impact, analysisVersion, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  if (!impact) return null;

  const verification = impact.verification || 'NEEDS_REVIEW';
  const evidenceBasis = impact.evidence_basis || null;
  const reason = impact.reason || null;

  const evidenceBasisLabel = {
    keyword_match: { label: 'Keyword Overlap', desc: 'A keyword from the query or code symbol appeared in the section text. This is heuristic, not deterministic.', color: 'bg-amber-50 border-amber-300' },
    ast_symbol: { label: 'AST Symbol Match', desc: 'A code symbol name was found in the section text. Text presence only — not a call-graph proof.', color: 'bg-sky-50 border-sky-300' },
    ai_synthesized: { label: 'AI-Synthesized', desc: 'An LLM suggested this dependency. LLM output is not evidence — it is a hypothesis requiring human review.', color: 'bg-purple-50 border-purple-300' }
  }[evidenceBasis] || { label: 'Unknown Basis', desc: 'Evidence basis not recorded.', color: 'bg-slate-50 border-slate-300' };

  return (
    <div className="mt-2 border-2 border-black rounded-md overflow-hidden font-mono text-xs">
      {/* Toggle header */}
      <button
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 hover:bg-slate-100 transition-colors"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-label="Toggle evidence details"
      >
        <div className="flex items-center gap-2">
          <span className="font-extrabold text-[10px] uppercase tracking-wider text-slate-700">Evidence Basis</span>
          <VerificationBadge status={verification} />
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${evidenceBasisLabel.color}`}>
            {evidenceBasisLabel.label}
          </span>
        </div>
        <span className="text-slate-400 font-bold text-base leading-none">{open ? '▲' : '▼'}</span>
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="px-3 py-3 bg-white border-t-2 border-black space-y-3">

          {/* Why it matters */}
          {reason && (
            <div>
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-600 mb-1">Why This Section May Be Affected</p>
              <p className="text-[11px] font-semibold text-black leading-relaxed font-sans">{reason}</p>
            </div>
          )}

          {/* Evidence basis explanation */}
          <div className={`border rounded-md px-2 py-1.5 ${evidenceBasisLabel.color}`}>
            <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-600 mb-0.5">How This Was Found</p>
            <p className="text-[11px] font-medium text-slate-700">{evidenceBasisLabel.desc}</p>
          </div>

          {/* What cannot be verified */}
          {(verification === 'NEEDS_REVIEW' || verification === 'UNABLE_TO_VERIFY') && (
            <div className="border-2 border-amber-400 bg-amber-50 rounded-md px-2 py-1.5">
              <p className="text-[10px] font-extrabold uppercase tracking-wider text-amber-800 mb-0.5">What Cannot Be Verified</p>
              <p className="text-[11px] font-medium text-amber-900">
                {verification === 'UNABLE_TO_VERIFY'
                  ? 'The signal found could not be matched to a known section in the parsed document. This finding should not be acted upon without manual inspection.'
                  : 'This finding is based on heuristic signal only. It requires human expert review before being treated as a confirmed dependency.'}
              </p>
            </div>
          )}

          {/* Analysis version watermark */}
          {analysisVersion && (
            <div className="text-[9px] text-slate-400 font-mono pt-1 border-t border-slate-100">
              Analysis: {analysisVersion.versionId} · Schema v{analysisVersion.schemaVersion} · {analysisVersion.createdAt ? new Date(analysisVersion.createdAt).toLocaleTimeString() : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
