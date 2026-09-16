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
      case 'CRITICAL': return 'neo-badge neo-badge-critical';
      case 'HIGH':     return 'neo-badge neo-badge-high';
      case 'MAJOR':    return 'neo-badge neo-badge-major';
      case 'MINOR':    return 'neo-badge neo-badge-minor';
      default:         return 'neo-badge neo-badge-neutral';
    }
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b-2 border-black w-full">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-black text-black tracking-tight font-mono uppercase">
            Impact Analysis
          </h1>
          {status && (
            <span className={getRiskBadge(risk)}>
              {risk} RISK
            </span>
          )}
        </div>
        <p className="text-xs text-gray-700 font-medium mt-1">
          Automated blast radius and bipartite verification between code repositories and research papers.
        </p>
      </div>

      <div className="flex items-center gap-2">
        {analysis && (
          <button
            onClick={onExportReport}
            className="neo-brutal-btn-white text-xs"
          >
            📥 Export Report (.json)
          </button>
        )}
      </div>
    </div>
  );
}
