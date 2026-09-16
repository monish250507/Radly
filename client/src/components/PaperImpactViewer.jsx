import React, { useState } from 'react';
import VerificationBadge from './VerificationBadge.jsx';
import EvidencePanel from './EvidencePanel.jsx';

export default function PaperImpactViewer({ paperAST, analysis }) {
  const [activeDiffSection, setActiveDiffSection] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  if (!paperAST || !paperAST.sections || paperAST.sections.length === 0) {
    return (
      <div className="p-8 text-center text-[var(--text-muted)] text-xs">
        No manuscript loaded. Upload a PDF or paste LaTeX in the workspace to view impact mapping.
      </div>
    );
  }

  const findSectionImpact = (section) => {
    const affected = analysis?.affected_sections;
    if (!affected || !Array.isArray(affected) || affected.length === 0) return null;

    let match = affected.find(sec => sec.section_id === section.id);
    if (match) return match;

    match = affected.find(sec => (sec.title || '').toLowerCase() === (section.title || '').toLowerCase());
    if (match) return match;

    const secIdLower = (section.id || '').toLowerCase();
    const secTitleLower = (section.title || '').toLowerCase();

    match = affected.find(sec => {
      const affIdLower = (sec.section_id || '').toLowerCase();
      const affTitleLower = (sec.title || '').toLowerCase();
      return (
        (affIdLower && secIdLower && (secIdLower.includes(affIdLower) || affIdLower.includes(secIdLower))) ||
        (affTitleLower && secTitleLower && (secTitleLower.includes(affTitleLower) || affTitleLower.includes(secTitleLower)))
      );
    });

    return match || null;
  };

  const getRiskClass = (risk) => {
    switch ((risk || '').toUpperCase()) {
      case 'CRITICAL': return 'badge-risk-critical';
      case 'HIGH': return 'badge-risk-high';
      case 'MAJOR': return 'badge-risk-major';
      case 'MINOR': return 'badge-risk-minor';
      default: return 'badge-risk-none';
    }
  };

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-[var(--border-color)]">
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-main)]">
            Manuscript Section Impact Mapping
          </h3>
          <p className="text-xs text-[var(--text-muted)]">
            {paperAST.sections.length} total sections analyzed against code changes
          </p>
        </div>
      </div>

      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {paperAST.sections.map((section) => {
          const impact = findSectionImpact(section);
          const isAffected = !!impact;
          const isDiffOpen = activeDiffSection === section.id;

          return (
            <div
              key={section.id}
              className={`radly-card p-4 transition-all ${
                isAffected
                  ? 'border-indigo-200 bg-white ring-1 ring-indigo-50/50'
                  : 'bg-white opacity-85'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[var(--text-main)]">
                      {section.title || section.id}
                    </span>
                    <span className="text-[10px] text-[var(--text-subtle)] font-mono">
                      #{section.id}
                    </span>
                  </div>
                  {isAffected && impact.reason && (
                    <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                      {impact.reason}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isAffected ? (
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${getRiskClass(impact.risk)}`}>
                      {impact.risk || 'AFFECTED'}
                    </span>
                  ) : (
                    <span className="text-[10px] font-medium text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full border border-slate-200">
                      Unaffected
                    </span>
                  )}

                  {isAffected && impact.suggested_text && (
                    <button
                      className="btn-secondary text-xs py-1 px-2.5"
                      onClick={() => setActiveDiffSection(isDiffOpen ? null : section.id)}
                    >
                      {isDiffOpen ? 'Hide Revision' : 'View Revision'}
                    </button>
                  )}
                </div>
              </div>

              {/* Proposed Revision View */}
              {isAffected && isDiffOpen && impact.suggested_text && (
                <div className="mt-3 pt-3 border-t border-[var(--border-color)] space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-emerald-700">Proposed Manuscript Update:</span>
                    <button
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                      onClick={() => handleCopy(impact.suggested_text, section.id)}
                    >
                      {copiedId === section.id ? '✓ Copied' : 'Copy LaTeX'}
                    </button>
                  </div>
                  <pre className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-800 overflow-x-auto whitespace-pre-wrap">
                    {impact.suggested_text}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
