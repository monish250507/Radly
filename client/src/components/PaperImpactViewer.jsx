import React, { useState } from 'react';

export default function PaperImpactViewer({ paperAST, analysis }) {
  const [activeDiffSection, setActiveDiffSection] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  if (!paperAST || !paperAST.sections || paperAST.sections.length === 0) {
    return (
      <div className="p-8 text-center text-gray-600 font-mono text-xs font-semibold">
        No manuscript loaded. Upload a PDF or paste LaTeX to map sections.
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

  const getRiskBadge = (risk) => {
    switch ((risk || '').toUpperCase()) {
      case 'CRITICAL': return 'neo-badge neo-badge-critical';
      case 'HIGH':     return 'neo-badge neo-badge-high';
      case 'MAJOR':    return 'neo-badge neo-badge-major';
      case 'MINOR':    return 'neo-badge neo-badge-minor';
      default:         return 'neo-badge neo-badge-neutral';
    }
  };

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-3 border-b-2 border-black">
        <div>
          <h3 className="text-sm font-extrabold text-black uppercase font-mono tracking-wider">
            Manuscript Section Impact Matrix
          </h3>
          <p className="text-xs text-gray-600 font-medium">
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
              className={`p-4 rounded-xl border-2 border-black transition-all ${
                isAffected
                  ? 'bg-white shadow-[3px_3px_0px_#000]'
                  : 'bg-white/80 shadow-[2px_2px_0px_#000] opacity-90'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-black">
                      {section.title || section.id}
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono">
                      #{section.id}
                    </span>
                  </div>
                  {isAffected && impact.reason && (
                    <p className="text-xs text-gray-700 font-medium leading-relaxed">
                      {impact.reason}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isAffected ? (
                    <span className={getRiskBadge(impact.risk)}>
                      {impact.risk || 'AFFECTED'}
                    </span>
                  ) : (
                    <span className="neo-badge neo-badge-neutral">
                      Unaffected
                    </span>
                  )}

                  {isAffected && impact.suggested_text && (
                    <button
                      className="neo-brutal-btn-white text-xs py-1 px-2.5"
                      onClick={() => setActiveDiffSection(isDiffOpen ? null : section.id)}
                    >
                      {isDiffOpen ? 'Hide Diff' : 'View Diff'}
                    </button>
                  )}
                </div>
              </div>

              {/* Proposed Revision */}
              {isAffected && isDiffOpen && impact.suggested_text && (
                <div className="mt-3 pt-3 border-t-2 border-black space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-extrabold text-black font-mono">Proposed LaTeX Update:</span>
                    <button
                      className="text-xs font-bold text-[#6355d8] hover:underline"
                      onClick={() => handleCopy(impact.suggested_text, section.id)}
                    >
                      {copiedId === section.id ? '✓ Copied' : 'Copy LaTeX'}
                    </button>
                  </div>
                  <pre className="p-3 bg-[#fffef0] border-2 border-black rounded-lg text-xs font-mono text-black overflow-x-auto whitespace-pre-wrap shadow-[2px_2px_0px_#000]">
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
