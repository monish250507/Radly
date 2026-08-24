import React, { useState } from 'react';
import VerificationBadge from './VerificationBadge.jsx';
import EvidencePanel from './EvidencePanel.jsx';

export default function PaperImpactViewer({ paperAST, analysis }) {
  const [activeDiffSection, setActiveDiffSection] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  if (!paperAST || !paperAST.sections) {
    return (
      <div className="p-6 text-center text-slate-700 font-mono text-xs font-bold">
        No paper manuscript loaded. Paste LaTeX or upload PDF/Word document to begin.
      </div>
    );
  }

  // Flexible fuzzy lookup helper to match affected sections from analysis
  const findSectionImpact = (section) => {
    const affected = analysis?.affected_sections;
    if (!affected || !Array.isArray(affected) || affected.length === 0) return null;

    // 1. Exact ID match
    let match = affected.find(sec => sec.section_id === section.id);
    if (match) return match;

    // 2. Exact Title match
    match = affected.find(sec => (sec.title || '').toLowerCase() === (section.title || '').toLowerCase());
    if (match) return match;

    // 3. Substring ID or Title match
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
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MAJOR': return 'badge-major';
      case 'MINOR': return 'badge-minor';
      default: return 'badge-none';
    }
  };

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const formatTitle = (titleStr) => {
    if (!titleStr) return 'Section';
    return titleStr
      .replace(/^sec-\d+-/, '')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="space-y-6">
      {/* Paper Header */}
      <div className="flex flex-col items-start border-b border-[var(--border-color)] pb-3 gap-0.5">
        <div className="flex items-center justify-between w-full">
          <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
            Manuscript Section Impact Matrix ({paperAST.sections.length} Sections)
          </h2>
          <span className="text-[11px] font-medium text-gray-500">
            LaTeX / Structural AST View
          </span>
        </div>
        <p className="text-[11px] font-medium text-gray-500">
          Flags affected paper sections, assigns risk ratings, and generates proposed side-by-side LaTeX text diffs.
        </p>
      </div>

      {/* Sections List */}
      <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
        {paperAST.sections.map((section) => {
          const impact = findSectionImpact(section);
          const isAffected = !!impact;
          const isDiffOpen = activeDiffSection === section.id;

          return (
            <div
              key={section.id}
              className={`neo-box p-4 transition-all ${
                isAffected
                  ? 'ring-1 ring-blue-500/20 shadow-md'
                  : 'opacity-70'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="text-sm font-semibold text-[var(--box-text)] font-mono">
                      {formatTitle(section.title)}
                    </h3>
                    {isAffected ? (
                      <span className={`badge ${getRiskClass(impact.risk)}`}>
                        {impact.risk || 'HIGH'} RISK
                      </span>
                    ) : (
                      <span className="badge badge-none">UNAFFECTED</span>
                    )}
                    {isAffected && (
                      <VerificationBadge status={impact.verification} />
                    )}
                  </div>
                  <p className="text-xs font-medium text-gray-500 mt-1">
                    Lines {section.startLine || 1} – {section.endLine || 40}
                  </p>
                </div>

                {isAffected && (
                  <button
                    className="neo-btn-white text-xs py-1 px-3"
                    onClick={() => setActiveDiffSection(isDiffOpen ? null : section.id)}
                  >
                    {isDiffOpen ? 'Close Diff' : 'View Proposed Revision'}
                  </button>
                )}
              </div>

              {/* Impact Reason + Evidence Panel */}
              {isAffected && impact.reason && (
                <div className="mt-3 bg-amber-500/10 border border-amber-500/20 p-3 rounded-lg text-xs font-mono shadow-sm">
                  <span className="text-[var(--box-text)] font-semibold block text-[11px] uppercase tracking-wider mb-1">
                    Impact Analysis
                  </span>
                  <p className="text-[var(--box-text)] font-medium leading-relaxed font-sans text-xs opacity-90">
                    {impact.reason}
                  </p>
                </div>
              )}
              {isAffected && (
                <EvidencePanel
                  impact={impact}
                  analysisVersion={analysis?.domain?.analysisVersion}
                />
              )}

              {/* Side-by-Side Paper Text Diff View */}
              {isDiffOpen && impact && (
                <div className="mt-4 border-t border-[var(--border-color)] pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[var(--box-text)] uppercase font-mono">
                      Manuscript Text Difference (Current vs Proposed)
                    </span>
                    <button
                      className="neo-btn text-xs py-1 px-3"
                      onClick={() => handleCopy(impact.suggested_text || section.text || '', section.id)}
                    >
                      {copiedId === section.id ? 'Copied to Clipboard' : 'Copy Revised LaTeX'}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
                    {/* Current Text */}
                    <div className="bg-red-500/10 border border-red-500/20 p-3.5 rounded-lg shadow-sm">
                      <span className="text-[10px] font-semibold text-red-600 uppercase tracking-wider block mb-2">
                        Current Paper Text
                      </span>
                      <pre className="whitespace-pre-wrap text-[var(--box-text)] opacity-90 font-medium text-[11px] leading-relaxed">
                        {impact.current_text || section.text}
                      </pre>
                    </div>

                    {/* Proposed Revised Text */}
                    <div className="bg-emerald-500/10 border border-emerald-500/20 p-3.5 rounded-lg shadow-sm">
                      <span className="text-[10px] font-semibold text-emerald-600 uppercase tracking-wider block mb-2">
                        Proposed Revised Paper Text
                      </span>
                      <pre className="whitespace-pre-wrap text-[var(--box-text)] opacity-90 font-medium text-[11px] leading-relaxed">
                        {impact.suggested_text || section.text}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
