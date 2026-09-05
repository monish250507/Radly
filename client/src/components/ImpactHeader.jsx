import React, { useState, useEffect } from 'react';
import VerificationBadge from './VerificationBadge.jsx';

// Status → display config
const STATUS_CONFIG = {
  VERIFIED:            { label: 'Verified',             color: 'bg-emerald-100 text-emerald-800 border-emerald-300', dot: 'bg-emerald-500' },
  LIKELY:              { label: 'Likely Affected',       color: 'bg-blue-100 text-blue-800 border-blue-300',        dot: 'bg-blue-500' },
  NEEDS_REVIEW:        { label: 'Needs Review',          color: 'bg-amber-100 text-amber-800 border-amber-300',     dot: 'bg-amber-500' },
  NO_DEPENDENCY_FOUND: { label: 'No Dependency Found',  color: 'bg-slate-100 text-slate-600 border-slate-300',    dot: 'bg-slate-400' },
  UNABLE_TO_VERIFY:    { label: 'Unable to Verify',     color: 'bg-orange-100 text-orange-800 border-orange-300', dot: 'bg-orange-500' },
  ANALYSIS_FAILED:     { label: 'Analysis Failed',      color: 'bg-red-100 text-red-800 border-red-300',          dot: 'bg-red-500' },
};

const RISK_CONFIG = {
  CRITICAL: 'text-red-700 bg-red-50 border-red-200',
  HIGH:     'text-orange-700 bg-orange-50 border-orange-200',
  MAJOR:    'text-amber-700 bg-amber-50 border-amber-200',
  MINOR:    'text-blue-700 bg-blue-50 border-blue-200',
  NONE:     'text-slate-500 bg-slate-50 border-slate-200',
};

/**
 * ImpactStatusBadge — replaces the removed Blast Radius Score.
 * Shows explicit status category + risk level — no uncalibrated 0-100 score.
 */
function ImpactStatusBadge({ status, risk }) {
  const s = STATUS_CONFIG[status] || STATUS_CONFIG['UNABLE_TO_VERIFY'];
  const r = risk?.toUpperCase() || 'NONE';
  const rStyle = RISK_CONFIG[r] || RISK_CONFIG['NONE'];
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold ${s.color}`}>
        <span className={`w-2 h-2 rounded-full ${s.dot}`} />
        {s.label}
      </div>
      <span className={`px-2 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wide ${rStyle}`}>
        Risk: {r}
      </span>
    </div>
  );
}

export default function ImpactHeader({
  analysis, hasCode, hasPaper, isIngesting, isParsingPaper, isAnalyzing, onExportReport, devMode, setDevMode
}) {
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
      document.documentElement.classList.remove('dark');
      setIsDarkMode(false);
    } else {
      document.documentElement.classList.add('dark');
      setIsDarkMode(true);
      if (!saved) localStorage.setItem('theme', 'dark');
    }
  }, []);

  const toggleTheme = () => {
    if (isDarkMode) {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
      setIsDarkMode(false);
    } else {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
      setIsDarkMode(true);
    }
  };

  const analysisStatus = analysis?.status || null;
  const risk = analysis?.risk_level || 'NONE';
  const summary = analysis?.impact_summary || { sections_affected: 0, equations_affected: 0, tables_affected: 0 };
  const executionTimeMs = analysis?.execution_time_ms || 0;
  const domainVersion = analysis?.domain?.analysisVersion || null;

  const getStatusText = () => {
    if (isIngesting)    return 'Ingesting repository source code…';
    if (isParsingPaper) return 'Parsing research paper…';
    if (isAnalyzing)    return 'Running impact analysis…';
    return null;
  };

  const statusText = getStatusText();

  return (
    <header className="relative border-b border-[var(--border-color)] bg-[var(--box-bg)] px-6 py-5 shadow-sm text-center w-full transition-colors duration-300">
      {/* Top-right controls */}
      <div className="absolute top-5 right-6 flex items-center gap-2 z-10">
        {/* Dev mode toggle */}
        <button
          id="dev-mode-toggle"
          onClick={() => setDevMode?.(d => !d)}
          title={devMode ? 'Exit Developer Mode' : 'Developer Mode (AST/Agent diagnostics)'}
          className={`neo-btn flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 border ${
            devMode
              ? 'bg-amber-100 border-amber-400 text-amber-800'
              : 'bg-[var(--box-bg)] text-[var(--box-text)] border-[var(--border-color)]'
          }`}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
            <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
          </svg>
          {devMode ? 'Exit Dev' : 'Dev Mode'}
        </button>

        <button
          id="theme-toggle"
          onClick={toggleTheme}
          className="neo-btn flex items-center justify-center p-2 bg-[var(--box-bg)] text-[var(--box-text)] hover:bg-[var(--tab-hover)] border border-[var(--border-color)]"
          aria-label="Toggle Dark Mode"
        >
          {isDarkMode ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>

        <a
          href="https://github.com/monish250507/Research_Blast_Radius"
          target="_blank" rel="noopener noreferrer"
          className="neo-btn hidden sm:flex items-center gap-2 text-xs bg-[var(--box-bg)] text-[var(--box-text)] hover:bg-[var(--tab-hover)] border border-[var(--border-color)]"
        >
          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
          </svg>
          GitHub
        </a>
      </div>

      {/* Title */}
      <div className="max-w-4xl mx-auto space-y-3 flex flex-col items-center justify-center">
        <div className="flex flex-col items-center justify-center gap-1">
          <div className="flex items-center justify-center gap-2.5">
            <h1 className="text-xl font-extrabold tracking-tight text-[var(--box-text)] uppercase font-mono text-center">
              PaperBlast — Research Impact Analyzer
            </h1>
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
          </div>
          <p className="text-xs font-mono font-medium text-gray-500 text-center max-w-xl">
            Trace how code &amp; parameter changes affect your research paper's claims, sections, and experiments.
          </p>
        </div>

        {/* Progress steps — researcher-friendly labels */}
        <div className="flex flex-wrap items-center justify-center gap-3 font-mono text-[11px] font-bold">
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${hasCode ? 'bg-emerald-300 text-black' : 'bg-white text-slate-500'}`}>
            {hasCode ? '✓' : '1.'} Code Loaded
          </div>
          <span className="text-black font-extrabold">→</span>
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${hasPaper ? 'bg-emerald-300 text-black' : 'bg-white text-slate-500'}`}>
            {hasPaper ? '✓' : '2.'} Paper Parsed
          </div>
          <span className="text-black font-extrabold">→</span>
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${analysis ? 'bg-sky-300 text-black' : 'bg-white text-slate-500'}`}>
            {analysis ? '✓' : '3.'} Analysis Ready
          </div>
        </div>

        {/* Analysis result summary */}
        {analysis ? (
          <div className="flex flex-wrap items-center justify-center gap-4 pt-1">
            {/* P1 FIX: ImpactStatusBadge replaces Blast Radius Score */}
            <ImpactStatusBadge status={analysisStatus} risk={risk} />

            <div className="flex items-center justify-center gap-4 bg-white border-2 border-black px-5 py-2 rounded-md font-mono text-xs shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
              <div className="text-center">
                <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Sections</span>
                <span className="font-extrabold text-black mt-0.5 block">{summary.sections_affected}</span>
              </div>
              <div className="text-center">
                <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Equations</span>
                <span className="font-extrabold text-black mt-0.5 block">{summary.equations_affected}</span>
              </div>
              <div className="text-center">
                <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Tables</span>
                <span className="font-extrabold text-black mt-0.5 block">{summary.tables_affected}</span>
              </div>
              <div className="text-center">
                <span className="text-slate-500 block text-[10px] uppercase tracking-wider">Time</span>
                <span className="font-extrabold text-black mt-0.5 block">{(executionTimeMs / 1000).toFixed(2)}s</span>
              </div>
            </div>

            {onExportReport && (
              <button id="export-report-btn" className="neo-btn text-xs" onClick={onExportReport}>
                Export Report (.json)
              </button>
            )}

            {domainVersion && (
              <div className="text-[9px] font-mono text-slate-400 text-center w-full">
                Analysis {domainVersion.versionId} · Schema v{domainVersion.schemaVersion} · {domainVersion.symbolCount} symbols · {domainVersion.sectionCount} sections
              </div>
            )}
          </div>
        ) : statusText ? (
          <div className="text-xs font-mono font-bold text-black bg-white border-2 border-black px-4 py-1.5 rounded-md shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            {statusText}
          </div>
        ) : null}
      </div>
    </header>
  );
}
