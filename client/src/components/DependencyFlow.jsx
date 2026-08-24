import React from 'react';
import VerificationBadge from './VerificationBadge.jsx';

export default function DependencyFlow({ lineageGraph }) {
  if (!lineageGraph || lineageGraph.length === 0) {
    return null;
  }

  // Clean target section IDs like "sec-2-abstract" to "Section 2: Abstract"
  const cleanTargetName = (targetStr) => {
    if (!targetStr) return 'Manuscript Section';
    return targetStr
      .replace(/^sec-\d+-/, '')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="neo-box p-5 space-y-4">
      <div className="flex flex-col items-start border-b border-[var(--border-color)] pb-2 gap-0.5">
        <div className="flex items-center justify-between w-full">
          <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
            Bipartite Lineage Graph ({lineageGraph.length} Dependencies)
          </h3>
          <span className="text-[11px] font-medium text-gray-500">
            Code AST Symbol to Manuscript Section Mapping
          </span>
        </div>
        <p className="text-[11px] font-medium text-gray-500">
          Maps 1-to-1 dependency lineage edges from modified Code AST Nodes to target Manuscript Sections.
        </p>
      </div>

      <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
        {lineageGraph.map((edge, idx) => (
          <div
            key={idx}
            className="grid grid-cols-1 md:grid-cols-12 items-center bg-[var(--input-bg)] border border-[var(--border-color)] p-3 rounded-lg font-mono text-xs gap-3 shadow-sm transition-all hover:shadow-md"
          >
            {/* Code Symbol Source (Col 1-4) */}
            <div className="md:col-span-4 flex items-center gap-2">
              <span className="text-gray-500 font-semibold uppercase text-[10px]">Code AST:</span>
              <span className="text-sky-700 font-semibold bg-sky-500/10 px-2 py-1 rounded border border-sky-500/20 truncate">
                {edge.source}
              </span>
            </div>

            {/* Dependency Relationship (Col 5-8) */}
            <div className="md:col-span-4 text-center">
              <span className="inline-block bg-yellow-500/10 text-yellow-700 border border-yellow-500/20 px-3 py-1 rounded-full text-[11px] font-semibold leading-tight">
                → {edge.relationship || 'Direct Dependency'} →
              </span>
            </div>

            {/* Paper Target Section (Col 9-12) */}
            <div className="md:col-span-3 flex items-center justify-end gap-2">
              <span className="text-gray-500 font-semibold uppercase text-[10px]">Paper Target:</span>
              <span className="text-amber-700 font-semibold bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20 truncate">
                {cleanTargetName(edge.target)}
              </span>
            </div>

            {/* Verification badge (Col 12) */}
            <div className="md:col-span-1 flex items-center justify-end">
              <VerificationBadge status={edge.verification} showLabel={false} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
