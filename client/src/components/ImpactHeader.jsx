import React from 'react';

export default function ImpactHeader({
  analysis,
  hasCode,
  hasPaper,
  isIngesting,
  isParsingPaper,
  isAnalyzing,
  onExportReport
}) {
  const status = analysis?.status;
  const risk = (analysis?.risk_level || 'NONE').toUpperCase();

  const getRiskBadge = (level) => {
    switch (level) {
      case 'CRITICAL': return 'bg-red-50 text-red-700 border-red-200';
      case 'HIGH': return 'bg-orange-50 text-orange-700 border-orange-200';
      case 'MAJOR': return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'MINOR': return 'bg-sky-50 text-sky-700 border-sky-200';
      default: return 'bg-slate-50 text-slate-600 border-slate-200';
    }
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[var(--border-color)] w-full">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-[var(--text-main)] tracking-tight">
            Impact Analysis
          </h1>
          {status && (
            <span className={`text-[11px] font-bold uppercase px-2.5 py-0.5 rounded-full border ${getRiskBadge(risk)}`}>
              {risk} RISK
            </span>
          )}
        </div>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Automated blast radius and bipartite verification between code repositories and scientific papers.
        </p>
      </div>

      <div className="flex items-center gap-2">
        {analysis && (
          <button
            onClick={onExportReport}
            className="btn-secondary text-xs"
          >
            <svg className="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export JSON
          </button>
        )}
      </div>
    </div>
  );
}
