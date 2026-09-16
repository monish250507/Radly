import React, { useState } from 'react';

export default function PaperImpactViewer({ paperAST, analysis }) {
  const [activeDiffSection, setActiveDiffSection] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [filterMode, setFilterMode] = useState('all'); // 'all' | 'affected' | 'unaffected' | 'grouped'

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

  // Compute lists
  const sectionsWithImpact = paperAST.sections.map(section => ({
    section,
    impact: findSectionImpact(section)
  }));

  const affectedSections = sectionsWithImpact.filter(item => !!item.impact);
  const unaffectedSections = sectionsWithImpact.filter(item => !item.impact);

  const renderSectionCard = ({ section, impact }) => {
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
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b-2 border-black gap-3">
        <div>
          <h3 className="text-sm font-extrabold text-black uppercase font-mono tracking-wider">
            Manuscript Section Impact Matrix
          </h3>
          <p className="text-xs text-gray-600 font-medium">
            {paperAST.sections.length} total sections analyzed ({affectedSections.length} affected, {unaffectedSections.length} unaffected)
          </p>
        </div>

        {/* Filter & Sort Controls */}
        <div className="flex items-center gap-1.5 bg-[#f5f4ef] p-1 border-2 border-black rounded-lg text-xs font-mono font-bold">
          <button
            onClick={() => setFilterMode('grouped')}
            className={`px-2.5 py-1 rounded transition-all ${
              filterMode === 'grouped'
                ? 'bg-[#6355d8] text-white shadow-[2px_2px_0px_#000]'
                : 'text-black hover:bg-black/10'
            }`}
          >
            Grouped
          </button>
          <button
            onClick={() => setFilterMode('all')}
            className={`px-2.5 py-1 rounded transition-all ${
              filterMode === 'all'
                ? 'bg-[#6355d8] text-white shadow-[2px_2px_0px_#000]'
                : 'text-black hover:bg-black/10'
            }`}
          >
            All ({paperAST.sections.length})
          </button>
          <button
            onClick={() => setFilterMode('affected')}
            className={`px-2.5 py-1 rounded transition-all ${
              filterMode === 'affected'
                ? 'bg-[#fca5a5] text-black shadow-[2px_2px_0px_#000]'
                : 'text-black hover:bg-black/10'
            }`}
          >
            Affected ({affectedSections.length})
          </button>
          <button
            onClick={() => setFilterMode('unaffected')}
            className={`px-2.5 py-1 rounded transition-all ${
              filterMode === 'unaffected'
                ? 'bg-[#86efac] text-black shadow-[2px_2px_0px_#000]'
                : 'text-black hover:bg-black/10'
            }`}
          >
            Unaffected ({unaffectedSections.length})
          </button>
        </div>
      </div>

      <div className="space-y-4 max-h-[550px] overflow-y-auto pr-1">
        {filterMode === 'grouped' ? (
          <>
            {/* Group 1: Affected Sections */}
            <div className="space-y-3">
              <div className="flex items-center justify-between pb-1 border-b border-black">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444] border border-black inline-block" />
                  <span className="text-xs font-black uppercase font-mono tracking-wider text-black">
                    Affected Sections ({affectedSections.length})
                  </span>
                </div>
                <span className="text-[10px] font-mono font-bold text-gray-500">Requires Revision</span>
              </div>
              {affectedSections.length === 0 ? (
                <div className="p-4 rounded-xl border-2 border-dashed border-gray-400 text-center text-xs font-mono text-gray-600 bg-white/50">
                  ✓ No affected sections detected in this manuscript.
                </div>
              ) : (
                affectedSections.map(renderSectionCard)
              )}
            </div>

            {/* Group 2: Unaffected Sections */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between pb-1 border-b border-black">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#22c55e] border border-black inline-block" />
                  <span className="text-xs font-black uppercase font-mono tracking-wider text-black">
                    Unaffected Sections ({unaffectedSections.length})
                  </span>
                </div>
                <span className="text-[10px] font-mono font-bold text-gray-500">Intact / Valid</span>
              </div>
              {unaffectedSections.length === 0 ? (
                <div className="p-4 rounded-xl border-2 border-dashed border-gray-400 text-center text-xs font-mono text-gray-600 bg-white/50">
                  All sections in the manuscript are affected.
                </div>
              ) : (
                unaffectedSections.map(renderSectionCard)
              )}
            </div>
          </>
        ) : filterMode === 'affected' ? (
          <div className="space-y-3">
            {affectedSections.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono font-bold text-gray-600 bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_#000]">
                ✓ No affected sections found.
              </div>
            ) : (
              affectedSections.map(renderSectionCard)
            )}
          </div>
        ) : filterMode === 'unaffected' ? (
          <div className="space-y-3">
            {unaffectedSections.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono font-bold text-gray-600 bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_#000]">
                All sections are affected.
              </div>
            ) : (
              unaffectedSections.map(renderSectionCard)
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {sectionsWithImpact.map(renderSectionCard)}
          </div>
        )}
      </div>
    </div>
  );
}
