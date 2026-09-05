import React, { useState } from 'react';
import ImpactHeader from './components/ImpactHeader';
import ChangeConsole from './components/ChangeConsole';
import CodeGraphViewer from './components/CodeGraphViewer';
import PaperImpactViewer from './components/PaperImpactViewer';
import DependencyFlow from './components/DependencyFlow';

/**
 * Robust JSON response handler. Handles Vercel 413 HTML responses safely.
 */
async function safeFetchJson(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = {};

  try {
    data = JSON.parse(text);
  } catch (e) {
    if (res.status === 413 || text.includes('Request Entity Too Large')) {
      throw new Error(
        'PDF payload exceeds the 4.5 MB Vercel limit. Use a smaller file or paste the text excerpt.'
      );
    }
    throw new Error(text.slice(0, 100) || `Server returned HTTP ${res.status}`);
  }

  if (!res.ok) {
    throw new Error(data.error || data.detail || `Request failed with HTTP ${res.status}`);
  }
  return data;
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------
const RESEARCHER_TABS = [
  { id: 'overview',     label: () => 'Overview' },
  { id: 'changes',      label: (a) => `Changes (${a?.affected_sections?.length ?? 0})` },
  { id: 'paper',        label: (_, p) => `Paper Impact (${p?.sections?.length ?? 0})` },
  { id: 'experiments',  label: (a) => `Experiments (${(a?.affected_equations?.length ?? 0) + (a?.affected_tables?.length ?? 0)})` },
];

const DEV_TABS = [
  { id: 'lineage',  label: (a) => `Lineage Graph (${a?.lineage_graph?.length ?? 0})` },
  { id: 'agents',   label: (a) => `Agent Trace (${a?.agent_collaboration_trace?.length ?? 0})` },
  { id: 'code_ast', label: (_, __, c) => `Code AST (${c?.length ?? 0})` },
];

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------
export default function App() {
  const [repoUrl, setRepoUrl]                 = useState('');
  const [query, setQuery]                     = useState('');
  const [paperText, setPaperText]             = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');

  const [codeSymbols, setCodeSymbols]         = useState([]);
  const [ingestedFilesCount, setIngestedFilesCount] = useState(0);
  const [paperAST, setPaperAST]               = useState({ sections: [], equations: [], tables: [], numbers: [] });
  const [analysis, setAnalysis]               = useState(null);

  const [isIngestingCode, setIsIngestingCode] = useState(false);
  const [isParsingPaper, setIsParsingPaper]   = useState(false);
  const [isAnalyzing, setIsAnalyzing]         = useState(false);
  const [errorMsg, setErrorMsg]               = useState('');

  const [activeTab, setActiveTab]             = useState('overview');
  const [devMode, setDevMode]                 = useState(false);

  // -------------------------------------------------------------------------
  // Data handlers
  // -------------------------------------------------------------------------
  const handleIngestRepo = async () => {
    if (!repoUrl.trim()) return;
    setIsIngestingCode(true);
    setErrorMsg('');
    try {
      const data = await safeFetchJson('/api/ingest-github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repoUrl })
      });
      setCodeSymbols(data.symbols || []);
      setIngestedFilesCount(data.fileCount || 1);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsIngestingCode(false);
    }
  };

  const handleCodeFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;
    setIsIngestingCode(true);
    setErrorMsg('');
    try {
      const codeFiles = await Promise.all(
        files.map(file => new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve({ name: file.name, content: reader.result });
          reader.onerror = reject;
          reader.readAsText(file);
        }))
      );
      const data = await safeFetchJson('/api/ingest-github', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codeFiles })
      });
      setCodeSymbols(data.symbols || []);
      setIngestedFilesCount(codeFiles.length);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsIngestingCode(false);
    }
  };

  const handleParsePaper = async () => {
    if (!paperText.trim()) return;
    setIsParsingPaper(true);
    setErrorMsg('');
    try {
      const data = await safeFetchJson('/api/parse-paper', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paperText })
      });
      setPaperAST(data.paperAST || { sections: [], equations: [], tables: [], numbers: [] });
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsParsingPaper(false);
    }
  };

  const handlePaperFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setSelectedFileName(file.name);
    setIsParsingPaper(true);
    setErrorMsg('');
    try {
      const ext = file.name.split('.').pop().toLowerCase();
      const reader = new FileReader();
      reader.onload = async () => {
        const base64Data = reader.result.split(',')[1] || reader.result;
        try {
          const data = await safeFetchJson('/api/parse-paper', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ paperFileBase64: base64Data, fileType: ext })
          });
          setPaperAST(data.paperAST || { sections: [], equations: [], tables: [], numbers: [] });
        } catch (err) {
          setErrorMsg(err.message);
        } finally {
          setIsParsingPaper(false);
        }
      };
      reader.onerror = () => { setErrorMsg('Failed to read file.'); setIsParsingPaper(false); };
      reader.readAsDataURL(file);
    } catch (err) {
      setErrorMsg(err.message);
      setIsParsingPaper(false);
    }
  };

  // P1 FIX: renamed from handleCalculateBlastRadius
  const handleAnalyseImpact = async () => {
    if (!query.trim()) return;
    setIsAnalyzing(true);
    setErrorMsg('');
    try {
      const data = await safeFetchJson('/api/analyze-impact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codeSymbols, paperAST, queryOrCodeChange: query })
      });
      setAnalysis(data.analysis || null);
      setActiveTab('overview');
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleExportReport = () => {
    if (!analysis) return;
    const report = {
      timestamp: new Date().toISOString(),
      query,
      repository: repoUrl,
      symbolsIndexedCount: codeSymbols.length,
      sectionsCount: paperAST.sections.length,
      analysis
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `paperblast-impact-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // -------------------------------------------------------------------------
  // Tab switching — guard dev-only tabs when not in dev mode
  // -------------------------------------------------------------------------
  const allTabs = devMode ? [...RESEARCHER_TABS, ...DEV_TABS] : RESEARCHER_TABS;
  const safeActiveTab = allTabs.find(t => t.id === activeTab) ? activeTab : 'overview';

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-[var(--bg-color)] text-[var(--text-color)] flex flex-col items-center w-full font-sans transition-colors duration-300">
      <div className="app-wrapper space-y-6 flex flex-col items-center w-full">

        {/* Header — P1 FIX: ImpactHeader replaces BlastRadiusHeader */}
        <ImpactHeader
          analysis={analysis}
          hasCode={codeSymbols.length > 0}
          hasPaper={paperAST.sections.length > 0}
          isIngesting={isIngestingCode}
          isParsingPaper={isParsingPaper}
          isAnalyzing={isAnalyzing}
          onExportReport={handleExportReport}
          devMode={devMode}
          setDevMode={setDevMode}
        />

        <main className="w-full space-y-6 flex flex-col items-center px-4">
          {/* Error Alert */}
          {errorMsg && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-600 px-4 py-3 rounded-lg font-mono text-xs flex items-center justify-between w-full max-w-4xl">
              <span className="font-semibold">⚠ {errorMsg}</span>
              <button className="neo-btn-white py-1 px-3 text-xs ml-4" onClick={() => setErrorMsg('')}>Dismiss</button>
            </div>
          )}

          {/* Input Console — P1 FIX: ChangeConsole replaces WhatIfConsole */}
          <ChangeConsole
            query={query}
            setQuery={setQuery}
            onCalculate={handleAnalyseImpact}
            repoUrl={repoUrl}
            setRepoUrl={setRepoUrl}
            onIngestRepo={handleIngestRepo}
            onCodeFileUpload={handleCodeFileUpload}
            onPaperFileUpload={handlePaperFileUpload}
            paperText={paperText}
            setPaperText={setPaperText}
            onParsePaper={handleParsePaper}
            isIngesting={isIngestingCode}
            isParsingPaper={isParsingPaper}
            isAnalyzing={isAnalyzing}
            ingestedFilesCount={ingestedFilesCount}
            symbolsCount={codeSymbols.length}
            sectionsCount={paperAST.sections.length}
            selectedFileName={selectedFileName}
          />

          {/* Navigation Tabs
              P1 FIX: Researcher-first tabs always visible.
              Dev-mode tabs (Lineage Graph, Agent Trace, Code AST) only visible in Dev Mode.
          */}
          <div className="flex flex-wrap items-center justify-center gap-2 py-2 w-full max-w-4xl">
            {RESEARCHER_TABS.map(tab => (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                className={`neo-tab ${safeActiveTab === tab.id ? 'neo-tab-active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label(analysis, paperAST, codeSymbols)}
              </button>
            ))}

            {/* Dev Mode separator + tabs */}
            {devMode && (
              <>
                <span className="text-[10px] font-mono text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                  DEV
                </span>
                {DEV_TABS.map(tab => (
                  <button
                    key={tab.id}
                    id={`tab-${tab.id}`}
                    className={`neo-tab text-amber-800 ${safeActiveTab === tab.id ? 'neo-tab-active border-amber-400' : ''}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    {tab.label(analysis, paperAST, codeSymbols)}
                  </button>
                ))}
              </>
            )}
          </div>

          {/* Tab Contents */}
          <div className="w-full max-w-5xl">

            {/* OVERVIEW — Researcher-first summary */}
            {safeActiveTab === 'overview' && (
              <div className="space-y-5 w-full">
                {!analysis ? (
                  <div className="neo-box p-10 text-center space-y-3">
                    <p className="text-sm font-semibold text-[var(--box-text)]">No analysis yet</p>
                    <p className="text-xs text-gray-500">Load a code repository and research paper, then click <strong>Analyse Impact</strong>.</p>
                  </div>
                ) : (
                  <>
                    {/* Affected sections summary */}
                    {analysis.affected_sections?.length > 0 && (
                      <div className="neo-box p-5">
                        <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono mb-3">
                          Sections Affected by This Change
                        </h2>
                        <div className="space-y-2">
                          {analysis.affected_sections.map((sec, i) => (
                            <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-[var(--input-bg)] border border-[var(--border-color)]">
                              <span className={`shrink-0 text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                                sec.risk === 'CRITICAL' ? 'text-red-700 bg-red-50 border-red-200' :
                                sec.risk === 'HIGH'     ? 'text-orange-700 bg-orange-50 border-orange-200' :
                                sec.risk === 'MAJOR'    ? 'text-amber-700 bg-amber-50 border-amber-200' :
                                                          'text-blue-700 bg-blue-50 border-blue-200'
                              }`}>{sec.risk || 'MINOR'}</span>
                              <div>
                                <p className="text-xs font-semibold text-[var(--box-text)]">{sec.title}</p>
                                <p className="text-[11px] text-gray-500 mt-0.5">{sec.reason}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {analysis.affected_sections?.length === 0 && (
                      <div className="neo-box p-6 text-center">
                        <p className="text-xs text-emerald-700 font-semibold">✓ No paper sections appear to be affected by this change.</p>
                      </div>
                    )}
                    {/* Error diagnostics (only shown on ANALYSIS_FAILED) */}
                    {analysis.status === 'ANALYSIS_FAILED' && analysis.error_diagnostics && (
                      <div className="neo-box p-5 border-red-300 bg-red-50/30">
                        <h2 className="text-xs font-semibold text-red-700 uppercase tracking-wider font-mono mb-2">Analysis Failed</h2>
                        <p className="text-xs text-red-600">{analysis.engine?.error_summary}</p>
                        <p className="text-[11px] text-gray-500 mt-1">{analysis.engine?.note}</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {/* CHANGES — List of affected sections with suggest text */}
            {safeActiveTab === 'changes' && (
              <div className="neo-box p-5 w-full">
                <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono mb-4">
                  Change Impact Detail
                </h2>
                {!analysis?.affected_sections?.length ? (
                  <p className="text-xs text-gray-500 text-center py-6">No affected sections identified.</p>
                ) : (
                  <div className="space-y-4">
                    {analysis.affected_sections.map((sec, i) => (
                      <div key={i} className="border border-[var(--border-color)] rounded-lg p-4 space-y-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[var(--box-text)]">{sec.title}</span>
                          <span className="text-[10px] font-mono text-gray-400">{sec.section_id}</span>
                          <span className={`ml-auto text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                            sec.risk === 'CRITICAL' ? 'text-red-700 bg-red-50 border-red-200' :
                            sec.risk === 'HIGH'     ? 'text-orange-700 bg-orange-50 border-orange-200' :
                            sec.risk === 'MAJOR'    ? 'text-amber-700 bg-amber-50 border-amber-200' :
                                                      'text-blue-700 bg-blue-50 border-blue-200'
                          }`}>{sec.risk || 'MINOR'}</span>
                        </div>
                        <p className="text-[11px] text-gray-500">{sec.reason}</p>
                        {sec.suggested_text && (
                          <div className="bg-emerald-50 border border-emerald-200 rounded p-2">
                            <p className="text-[10px] font-semibold text-emerald-700 uppercase mb-1">Suggested revision:</p>
                            <p className="text-[11px] text-emerald-800 font-mono">{sec.suggested_text}</p>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* PAPER IMPACT — full PaperImpactViewer */}
            {safeActiveTab === 'paper' && (
              <div className="neo-box p-5 w-full">
                <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
              </div>
            )}

            {/* EXPERIMENTS — equations + tables */}
            {safeActiveTab === 'experiments' && (
              <div className="space-y-5 w-full">
                {analysis?.affected_equations?.length > 0 && (
                  <div className="neo-box p-5">
                    <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono mb-3">
                      Affected Equations ({analysis.affected_equations.length})
                    </h2>
                    {analysis.affected_equations.map((eq, i) => (
                      <div key={i} className="p-3 border border-[var(--border-color)] rounded mb-2 flex items-start gap-3">
                        <span className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded shrink-0">{eq.risk}</span>
                        <div>
                          <p className="text-xs font-semibold text-[var(--box-text)]">{eq.label}</p>
                          <p className="text-[11px] text-gray-500">{eq.explanation}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {analysis?.affected_tables?.length > 0 && (
                  <div className="neo-box p-5">
                    <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono mb-3">
                      Affected Tables ({analysis.affected_tables.length})
                    </h2>
                    {analysis.affected_tables.map((tbl, i) => (
                      <div key={i} className="p-3 border border-[var(--border-color)] rounded mb-2 flex items-start gap-3">
                        <span className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded shrink-0">{tbl.risk}</span>
                        <div>
                          <p className="text-xs font-semibold text-[var(--box-text)]">{tbl.label}</p>
                          <p className="text-[11px] text-gray-500">{tbl.explanation}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {!analysis?.affected_equations?.length && !analysis?.affected_tables?.length && (
                  <div className="neo-box p-10 text-center">
                    <p className="text-xs text-gray-500">No affected equations or tables identified.</p>
                  </div>
                )}
              </div>
            )}

            {/* DEV: LINEAGE GRAPH */}
            {safeActiveTab === 'lineage' && devMode && (
              <div className="neo-box p-5 w-full">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
                    Lineage Graph (NEEDS_REVIEW — not shown to researchers)
                  </h2>
                  <span className="text-[10px] bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded font-mono">Dev Only</span>
                </div>
                <p className="text-[11px] text-gray-500 mb-3">
                  These are candidate dependency edges from static analysis. All are tagged NEEDS_REVIEW and are NOT presented as verified findings.
                </p>
                <DependencyFlow lineageGraph={analysis?.lineage_graph || []} />
              </div>
            )}

            {/* DEV: AGENT TRACE */}
            {safeActiveTab === 'agents' && devMode && (
              <div className="neo-box p-5 space-y-4 w-full">
                <div className="flex items-center gap-2 border-b border-[var(--border-color)] pb-2">
                  <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
                    Multi-Agent Trace Log
                  </h2>
                  <span className="text-[10px] bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded font-mono">Dev Only</span>
                  {analysis?.status && (
                    <span className="ml-auto text-[10px] font-semibold text-[var(--box-text)] border border-[var(--border-color)] px-2 py-0.5 rounded">
                      {analysis.status}
                    </span>
                  )}
                </div>
                {!analysis ? (
                  <p className="text-xs font-mono text-slate-500 py-4 text-center">Run an analysis to see the agent trace.</p>
                ) : (
                  <div className="space-y-3">
                    {(analysis.agent_collaboration_trace || []).map((trace, idx) => (
                      <div key={idx} className="neo-box p-4 flex flex-col gap-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[var(--box-text)] uppercase text-xs">{trace.agent}</span>
                          <span className="bg-[var(--input-bg)] border border-[var(--border-color)] px-2 py-0.5 rounded text-[10px] font-semibold">COMPLETED</span>
                        </div>
                        <p className="text-[11px] text-gray-400 font-medium">Role: {trace.role}</p>
                        <p className="text-[11px] text-[var(--box-text)]">Output: {trace.output_summary}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* DEV: CODE AST */}
            {safeActiveTab === 'code_ast' && devMode && (
              <div className="neo-box p-5 w-full">
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
                    Code AST Symbols
                  </h2>
                  <span className="text-[10px] bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded font-mono">Dev Only</span>
                </div>
                <CodeGraphViewer symbols={codeSymbols} />
              </div>
            )}
          </div>
        </main>

        <footer className="w-full py-6 text-center text-xs font-medium text-gray-500 mt-6 border-t border-[var(--border-color)]">
          PaperBlast — Research Code &amp; Paper Impact Analyzer · Open Source
        </footer>
      </div>
    </div>
  );
}
