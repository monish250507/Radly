import React, { useState } from 'react';
import ImpactHeader from './components/ImpactHeader';
import ChangeConsole from './components/ChangeConsole';
import PaperImpactViewer from './components/PaperImpactViewer';

/**
 * Safe JSON fetch utility
 */
async function safeFetchJson(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = {};

  try {
    data = JSON.parse(text);
  } catch (e) {
    if (res.status === 413 || text.includes('Request Entity Too Large')) {
      throw new Error('PDF payload is too large. Use a smaller document or paste text excerpt.');
    }
    throw new Error(text.slice(0, 100) || `Server returned HTTP ${res.status}`);
  }

  if (!res.ok) {
    throw new Error(data.error || data.detail || `Request failed with HTTP ${res.status}`);
  }
  return data;
}

export default function App() {
  const [repoUrl, setRepoUrl] = useState('');
  const [query, setQuery] = useState('');
  const [paperText, setPaperText] = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');

  const [codeSymbols, setCodeSymbols] = useState([]);
  const [ingestedFilesCount, setIngestedFilesCount] = useState(0);
  const [paperAST, setPaperAST] = useState({ sections: [], equations: [], tables: [], numbers: [] });
  const [analysis, setAnalysis] = useState(null);

  const [isIngestingCode, setIsIngestingCode] = useState(false);
  const [isParsingPaper, setIsParsingPaper] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [activeTab, setActiveTab] = useState('overview');
  const [activeSidebarNav, setActiveSidebarNav] = useState('analysis');

  // Ingest GitHub repository
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

  // Upload local code files
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

  // Parse paper text / LaTeX
  const handleParsePaper = async () => {
    if (!paperText.trim()) return;
    setIsParsingPaper(true);
    setErrorMsg('');
    try {
      const data = await safeFetchJson('/api/parse-paper', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ documentBuffer: paperText, fileType: 'txt' })
      });
      setPaperAST(data.paperAST || { sections: [], equations: [], tables: [], numbers: [] });
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsParsingPaper(false);
    }
  };

  // Upload PDF / DOCX
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
            body: JSON.stringify({ documentBuffer: base64Data, fileType: ext })
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

  // Run impact analysis
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
      setAnalysis(data || null);
      setActiveTab('overview');
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Export analysis JSON
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
    a.download = `radly-impact-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const riskLevel = (analysis?.risk_level || 'NONE').toUpperCase();
  const affectedSectionsCount = analysis?.affected_sections?.length || 0;
  const equationsCount = (analysis?.affected_equations?.length || 0) + (analysis?.affected_tables?.length || 0);

  return (
    <div className="min-h-screen flex bg-[#f8fafc] text-[#0f172a] font-sans antialiased">
      
      {/* Left Purple Rail Sidebar - Reference Design */}
      <aside className="w-16 md:w-60 bg-[#5b45e0] text-white flex flex-col justify-between shrink-0 transition-all">
        <div>
          {/* Logo & Brand */}
          <div className="h-16 flex items-center px-4 md:px-6 gap-3 border-b border-indigo-400/20">
            <div className="w-8 h-8 rounded-lg bg-white text-[#5b45e0] font-black text-base flex items-center justify-center shadow-sm">
              R
            </div>
            <div className="hidden md:block">
              <span className="font-bold text-base tracking-tight">Radly</span>
              <span className="text-[10px] block text-indigo-200 uppercase font-medium tracking-wider">Impact Studio</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1.5 mt-2">
            <button
              onClick={() => setActiveSidebarNav('analysis')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all ${
                activeSidebarNav === 'analysis'
                  ? 'bg-white/15 text-white shadow-inner'
                  : 'text-indigo-100 hover:bg-white/10 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <span className="hidden md:inline">Impact Analysis</span>
            </button>

            <button
              onClick={() => setActiveSidebarNav('workspace')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all ${
                activeSidebarNav === 'workspace'
                  ? 'bg-white/15 text-white shadow-inner'
                  : 'text-indigo-100 hover:bg-white/10 hover:text-white'
              }`}
            >
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
              <span className="hidden md:inline">Workspace</span>
            </button>

            <a
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold text-indigo-100 hover:bg-white/10 hover:text-white transition-all"
            >
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <span className="hidden md:inline">API Docs</span>
            </a>
          </nav>
        </div>

        {/* Sidebar Footer Status */}
        <div className="p-3 m-3 bg-indigo-800/40 rounded-xl hidden md:block border border-indigo-400/20 text-xs">
          <p className="font-semibold text-white">Groq gpt-oss-120b</p>
          <div className="flex items-center gap-1.5 text-indigo-200 text-[11px] mt-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Stateless · Zero-DB
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        
        {/* Top Header / Breadcrumb Bar */}
        <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Studio</span>
            <span className="text-slate-300">/</span>
            <span className="text-xs font-semibold text-slate-700">Code & Paper Blast Radius</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              Production Ready
            </span>
          </div>
        </header>

        {/* Body Container */}
        <main className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto w-full">
          
          {/* Header Title Section */}
          <ImpactHeader
            analysis={analysis}
            hasCode={codeSymbols.length > 0}
            hasPaper={paperAST.sections.length > 0}
            isIngesting={isIngestingCode}
            isParsingPaper={isParsingPaper}
            isAnalyzing={isAnalyzing}
            onExportReport={handleExportReport}
          />

          {/* Error Banner */}
          {errorMsg && (
            <div className="p-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-red-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="font-medium">{errorMsg}</span>
              </div>
              <button
                className="text-xs font-semibold text-red-600 hover:text-red-800 ml-4"
                onClick={() => setErrorMsg('')}
              >
                Dismiss
              </button>
            </div>
          )}

          {/* 3 Metric Summary Cards (from Reference Design) */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <div className="radly-card p-5">
              <div className="flex items-center justify-between text-xs text-[var(--text-muted)] font-medium">
                <span>Code Symbols Indexed</span>
                <span className="text-[11px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                  AST Tree
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-[var(--text-main)]">{codeSymbols.length}</span>
                <span className="text-xs text-[var(--text-subtle)]">from {ingestedFilesCount} files</span>
              </div>
            </div>

            <div className="radly-card p-5">
              <div className="flex items-center justify-between text-xs text-[var(--text-muted)] font-medium">
                <span>Manuscript Sections</span>
                <span className="text-[11px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                  Structure
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-[var(--text-main)]">{paperAST.sections.length}</span>
                <span className="text-xs text-[var(--text-subtle)]">parsed sections</span>
              </div>
            </div>

            <div className="radly-card p-5">
              <div className="flex items-center justify-between text-xs text-[var(--text-muted)] font-medium">
                <span>Blast Radius Status</span>
                <span className={`text-[11px] font-bold uppercase px-2 py-0.5 rounded ${
                  riskLevel === 'CRITICAL' ? 'bg-red-50 text-red-700' :
                  riskLevel === 'HIGH'     ? 'bg-orange-50 text-orange-700' :
                  riskLevel === 'MAJOR'    ? 'bg-amber-50 text-amber-700' :
                  riskLevel === 'MINOR'    ? 'bg-sky-50 text-sky-700' :
                                             'bg-slate-50 text-slate-500'
                }`}>
                  {riskLevel}
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-[var(--text-main)]">
                  {analysis ? `${affectedSectionsCount} Affected` : 'Ready'}
                </span>
                <span className="text-xs text-[var(--text-subtle)]">
                  {analysis?.execution_time_ms ? `${analysis.execution_time_ms}ms` : '0ms'}
                </span>
              </div>
            </div>
          </div>

          {/* Stepped Input Workspace */}
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

          {/* Results Navigation Bar */}
          <div className="pt-2 border-t border-slate-200">
            <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
              <button
                className={`nav-tab ${activeTab === 'overview' ? 'nav-tab-active' : ''}`}
                onClick={() => setActiveTab('overview')}
              >
                Overview ({affectedSectionsCount})
              </button>
              <button
                className={`nav-tab ${activeTab === 'paper' ? 'nav-tab-active' : ''}`}
                onClick={() => setActiveTab('paper')}
              >
                Manuscript Details ({paperAST.sections.length})
              </button>
              <button
                className={`nav-tab ${activeTab === 'experiments' ? 'nav-tab-active' : ''}`}
                onClick={() => setActiveTab('experiments')}
              >
                Equations & Tables ({equationsCount})
              </button>
            </div>

            {/* Results Body */}
            <div className="mt-4">
              
              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div>
                  {!analysis ? (
                    <div className="radly-card p-12 text-center space-y-2">
                      <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-500 mx-auto flex items-center justify-center">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                      </div>
                      <h4 className="text-sm font-semibold text-[var(--text-main)]">Ready to Analyze Impact</h4>
                      <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto">
                        Load your repository, upload your paper, and enter a proposed change query to generate an impact report.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {analysis.affected_sections?.length > 0 ? (
                        <div className="radly-card p-6 space-y-4">
                          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                            <h3 className="text-sm font-semibold text-[var(--text-main)]">
                              Identified Affected Sections ({analysis.affected_sections.length})
                            </h3>
                            <span className="text-xs text-[var(--text-muted)]">
                              Impact Blast Radius Summary
                            </span>
                          </div>

                          <div className="space-y-3">
                            {analysis.affected_sections.map((sec, i) => (
                              <div
                                key={i}
                                className="p-4 rounded-xl border border-slate-200 hover:border-slate-300 transition-colors bg-white flex items-start gap-4"
                              >
                                <span className={`text-[10px] font-bold uppercase px-2.5 py-1 rounded-full shrink-0 ${
                                  sec.risk === 'CRITICAL' ? 'bg-red-50 text-red-700 border border-red-200' :
                                  sec.risk === 'HIGH'     ? 'bg-orange-50 text-orange-700 border border-orange-200' :
                                  sec.risk === 'MAJOR'    ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                                                            'bg-sky-50 text-sky-700 border border-sky-200'
                                }`}>
                                  {sec.risk || 'MINOR'}
                                </span>
                                <div className="space-y-1">
                                  <p className="text-xs font-semibold text-[var(--text-main)]">{sec.title}</p>
                                  <p className="text-xs text-[var(--text-muted)] leading-relaxed">{sec.reason}</p>
                                  {sec.suggested_text && (
                                    <div className="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono text-slate-700">
                                      <span className="text-[10px] font-semibold uppercase text-slate-500 block mb-1">Suggested Diff:</span>
                                      {sec.suggested_text}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="radly-card p-8 text-center text-xs text-emerald-700 font-semibold bg-emerald-50/50 border-emerald-200">
                          ✓ No paper sections appear to be adversely impacted by this code modification.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: MANUSCRIPT DETAILS */}
              {activeTab === 'paper' && (
                <div className="radly-card p-6">
                  <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
                </div>
              )}

              {/* TAB 3: EQUATIONS & TABLES */}
              {activeTab === 'experiments' && (
                <div className="space-y-4">
                  {analysis?.affected_equations?.length > 0 && (
                    <div className="radly-card p-6 space-y-3">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        Affected Equations ({analysis.affected_equations.length})
                      </h4>
                      {analysis.affected_equations.map((eq, i) => (
                        <div key={i} className="p-3 border border-slate-200 rounded-lg flex items-start gap-3 text-xs">
                          <span className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                            {eq.risk}
                          </span>
                          <div>
                            <p className="font-semibold text-[var(--text-main)]">{eq.label}</p>
                            <p className="text-[var(--text-muted)]">{eq.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {analysis?.affected_tables?.length > 0 && (
                    <div className="radly-card p-6 space-y-3">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        Affected Tables ({analysis.affected_tables.length})
                      </h4>
                      {analysis.affected_tables.map((tbl, i) => (
                        <div key={i} className="p-3 border border-slate-200 rounded-lg flex items-start gap-3 text-xs">
                          <span className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                            {tbl.risk}
                          </span>
                          <div>
                            <p className="font-semibold text-[var(--text-main)]">{tbl.label}</p>
                            <p className="text-[var(--text-muted)]">{tbl.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {!analysis?.affected_equations?.length && !analysis?.affected_tables?.length && (
                    <div className="radly-card p-10 text-center text-xs text-[var(--text-muted)]">
                      No mathematical equations or experimental tables affected by this change.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </main>

        <footer className="py-6 text-center text-xs text-slate-400 border-t border-slate-200 mt-12">
          Radly — Research Code &amp; Paper Impact Analyzer · Clean SaaS Edition
        </footer>
      </div>
    </div>
  );
}
