import React, { useState, useEffect } from 'react';
import VerificationBadge from './VerificationBadge.jsx';

export default function BlastRadiusHeader({ analysis, hasCode, hasPaper, isIngesting, isParsingPaper, isAnalyzing, onExportReport }) {
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme');
    // Default to dark mode unless explicitly set to 'light'
    if (savedTheme === 'light') {
      document.documentElement.classList.remove('dark');
      setIsDarkMode(false);
    } else {
      document.documentElement.classList.add('dark');
      setIsDarkMode(true);
      if (!savedTheme) {
        localStorage.setItem('theme', 'dark');
      }
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

  const score = analysis?.overall_impact_score ?? null;
  const risk = analysis?.risk_level || 'NONE';
  const analysisStatus = analysis?.status || null;
  const domainVersion = analysis?.domain?.analysisVersion || null;
  const summary = analysis?.impact_summary || { sections_affected: 0, equations_affected: 0, tables_affected: 0 };
  const executionTimeMs = analysis?.execution_time_ms || 0;
  const costEst = analysis?.cost_efficiency?.estimated_cost_usd ?? 0.00;

  const getRiskClass = (r) => {
    switch ((r || '').toUpperCase()) {
      case 'CRITICAL': return 'badge-critical';
      case 'HIGH': return 'badge-high';
      case 'MAJOR': return 'badge-major';
      case 'MINOR': return 'badge-minor';
      default: return 'badge-none';
    }
  };

  const getStatusText = () => {
    if (isIngesting) return 'Ingesting Repository Source Code...';
    if (isParsingPaper) return 'Parsing Research Paper Document...';
    if (isAnalyzing) return 'Calculating Blast Radius Across 3 Agents...';
    return 'Awaiting Data Input to Begin Multi-Agent Analysis';
  };

  return (
    <header className="relative border-b border-[var(--border-color)] bg-[var(--box-bg)] px-6 py-5 shadow-sm text-center w-full transition-colors duration-300">
      <div className="absolute top-5 right-6 flex items-center gap-2">
        <button onClick={toggleTheme} className="neo-btn flex items-center justify-center p-2 bg-[var(--box-bg)] text-[var(--box-text)] hover:bg-[var(--tab-hover)] border border-[var(--border-color)]" aria-label="Toggle Dark Mode" title="Toggle Dark Mode">
          {isDarkMode ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
          )}
        </button>
        <a href="https://github.com/monish250507/Research_Blast_Radius" target="_blank" rel="noopener noreferrer" className="neo-btn flex items-center gap-2 text-xs bg-[var(--box-bg)] text-[var(--box-text)] hover:bg-[var(--tab-hover)] border border-[var(--border-color)] hidden sm:flex">
          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
          GitHub
        </a>
      </div>
      <div className="max-w-4xl mx-auto space-y-3 flex flex-col items-center justify-center">
        
        {/* Title & Multi-Agent Subtitle */}
        <div className="flex flex-col items-center justify-center gap-1">
          <div className="flex items-center justify-center gap-2.5">
            <h1 className="text-xl font-extrabold tracking-tight text-[var(--box-text)] uppercase font-mono text-center">
              Research Code & Paper Impact Analyzer
            </h1>
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></span>
          </div>
          <p className="text-xs font-mono font-medium text-gray-500 text-center max-w-xl">
            Multi-Agent AI Architecture: Code AST Traversal Agent + Manuscript Impact Analyst + Skeptic Verification Arbiter.
          </p>
        </div>

        {/* Stepped Progress & Multi-Agent Tracker */}
        <div className="flex flex-col items-center gap-1.5 pt-1">
          <div className="flex flex-wrap items-center justify-center gap-3 font-mono text-[11px] font-bold">
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${hasCode ? 'bg-emerald-300 text-black' : 'bg-white text-slate-500'}`}>
              <span>1. Code AST Agent</span>
            </div>
            <span className="text-black font-extrabold">→</span>
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${hasPaper ? 'bg-emerald-300 text-black' : 'bg-white text-slate-500'}`}>
              <span>2. Manuscript Analyst Agent</span>
            </div>
            <span className="text-black font-extrabold">→</span>
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] ${analysis ? 'bg-sky-300 text-black' : 'bg-white text-slate-500'}`}>
              <span>3. Skeptic Verification Arbiter</span>
            </div>
          </div>
          <span className="text-[10px] font-mono font-semibold text-slate-500">
            Workflow: Extract AST Symbols → Cross-Reference Paper Structure → Audit & Synthesize Revisions
          </span>
        </div>

        {/* Metrics & Cost Audit Badges */}
        {analysis ? (
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <div className="flex items-center justify-center gap-5 bg-white border-2 border-black px-6 py-2.5 rounded-md font-mono text-xs shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]">
              {/* Score */}
              <div className="flex flex-col items-center border-r-2 border-black pr-5">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">Blast Radius Score</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xl font-extrabold text-black">{score !== null ? `${score}%` : '—'}</span>
                  <span className={`badge ${getRiskClass(risk)}`}>{risk}</span>
                </div>
              </div>

              {/* Analysis Status */}
              <div className="flex flex-col items-center border-r-2 border-black pr-5">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">Verification</span>
                <div className="mt-0.5">
                  {analysisStatus ? (
                    <VerificationBadge status={analysisStatus} size="sm" />
                  ) : (
                    <span className="text-black font-extrabold text-sm">—</span>
                  )}
                </div>
              </div>

              {/* Cost Efficiency */}
              <div className="flex flex-col items-center border-r-2 border-black pr-5">
                <span className="text-slate-700 font-bold uppercase text-[10px] tracking-wider">Cost Audit</span>
                <span className="text-emerald-700 font-extrabold text-xs mt-0.5">${costEst.toFixed(2)} (Groq LPU)</span>
              </div>

              {/* Counts */}
              <div className="flex items-center justify-center gap-4 text-black font-bold">
                <div className="text-center">
                  <span className="text-slate-700 block text-[10px] uppercase tracking-wider">Sections</span>
                  <span className="font-extrabold text-black mt-0.5 block">{summary.sections_affected}</span>
                </div>
                <div className="text-center">
                  <span className="text-slate-700 block text-[10px] uppercase tracking-wider">Equations</span>
                  <span className="font-extrabold text-black mt-0.5 block">{summary.equations_affected}</span>
                </div>
                <div className="text-center">
                  <span className="text-slate-700 block text-[10px] uppercase tracking-wider">Time</span>
                  <span className="font-extrabold text-black mt-0.5 block">{(executionTimeMs / 1000).toFixed(2)}s</span>
                </div>
              </div>
            </div>

            {/* Analysis version watermark */}
            {domainVersion && (
              <div className="text-[9px] font-mono text-slate-400 text-center">
                Analysis {domainVersion.versionId} · Schema v{domainVersion.schemaVersion} · {domainVersion.symbolCount} symbols · {domainVersion.sectionCount} sections
              </div>
            )}

            {/* Export Audit Report Button */}
            {onExportReport && (
              <button
                className="neo-btn text-xs"
                onClick={onExportReport}
              >
                Export Audit Report (.json)
              </button>
            )}
          </div>
        ) : (
          <div className="text-xs font-mono font-bold text-black bg-white border-2 border-black px-4 py-1.5 rounded-md shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] text-center">
            {getStatusText()}
          </div>
        )}
      </div>
    </header>
  );
}
