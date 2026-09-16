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
    <div className="min-h-screen flex bg-[#faf9f6] text-black font-sans antialiased">
      
      {/* Neo-Brutalist Purple Rail Sidebar - Reference Design */}
      <aside className="w-16 md:w-64 bg-[#6355d8] text-white flex flex-col justify-between shrink-0 border-r-2 border-black">
        <div>
          {/* Logo & Brand */}
          <div className="h-16 flex items-center px-4 md:px-6 gap-3 border-b-2 border-black bg-[#5345c7]">
            <div className="w-9 h-9 rounded-lg bg-[#fde047] text-black font-black text-lg flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_#000]">
              R
            </div>
            <div className="hidden md:block">
              <span className="font-black text-lg tracking-tight font-mono">Radly</span>
              <span className="text-[10px] block text-[#fde047] font-bold uppercase tracking-wider">Impact Studio</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-2 mt-3">
            <button
              onClick={() => setActiveSidebarNav('analysis')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-black uppercase tracking-wider transition-all border-2 border-black ${
                activeSidebarNav === 'analysis'
                  ? 'bg-white text-black shadow-[3px_3px_0px_#000]'
                  : 'bg-[#6355d8] text-white hover:bg-[#5345c7] shadow-[2px_2px_0px_#000]'
              }`}
            >
              <span className="text-base leading-none">⚡</span>
              <span className="hidden md:inline">Analysis</span>
            </button>

            <button
              onClick={() => setActiveSidebarNav('workspace')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-black uppercase tracking-wider transition-all border-2 border-black ${
                activeSidebarNav === 'workspace'
                  ? 'bg-white text-black shadow-[3px_3px_0px_#000]'
                  : 'bg-[#6355d8] text-white hover:bg-[#5345c7] shadow-[2px_2px_0px_#000]'
              }`}
            >
              <span className="text-base leading-none">📂</span>
              <span className="hidden md:inline">Workspace</span>
            </button>

            <a
              href="/api/docs"
              target="_blank"
              rel="noreferrer"
              className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-black uppercase tracking-wider bg-[#6355d8] text-white hover:bg-[#5345c7] transition-all border-2 border-black shadow-[2px_2px_0px_#000]"
            >
              <span className="text-base leading-none">📖</span>
              <span className="hidden md:inline">API Docs</span>
            </a>
          </nav>
        </div>

        {/* Sidebar Status Box */}
        <div className="p-3.5 m-3 bg-[#fffef0] text-black border-2 border-black rounded-xl hidden md:block shadow-[3px_3px_0px_#000] text-xs">
          <p className="font-black uppercase tracking-wide font-mono">Groq 120B Connected</p>
          <div className="flex items-center gap-1.5 text-gray-700 text-[11px] font-bold mt-1">
            <span className="w-2 h-2 rounded-full bg-[#86efac] border border-black" />
            Stateless · Zero-DB
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        
        {/* Top Header Bar */}
        <header className="h-16 bg-white border-b-2 border-black px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3 font-mono text-xs font-bold">
            <span className="text-gray-500 uppercase">STUDIO</span>
            <span>/</span>
            <span className="text-black uppercase">RESEARCH BLAST RADIUS</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="neo-badge neo-badge-verified">
              ● READY FOR DEPLOYMENT
            </span>
          </div>
        </header>

        {/* Workspace Canvas */}
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
            <div className="p-4 bg-[#fca5a5] border-2 border-black text-black text-xs font-bold rounded-xl flex items-center justify-between shadow-[3px_3px_0px_#000]">
              <div className="flex items-center gap-2">
                <span>⚠</span>
                <span>{errorMsg}</span>
              </div>
              <button
                className="neo-brutal-btn-white text-xs py-1 px-2"
                onClick={() => setErrorMsg('')}
              >
                Dismiss
              </button>
            </div>
          )}

          {/* 3 Neo-Brutalist Stat Cards (Matching Reference Grid) */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            <div className="neo-brutal-card p-5 bg-white">
              <div className="flex items-center justify-between text-xs font-extrabold uppercase font-mono text-gray-700">
                <span>Code Symbols</span>
                <span className="neo-badge neo-badge-neutral">
                  AST Tree
                </span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black font-mono text-black">{codeSymbols.length}</span>
                <span className="text-xs font-bold text-gray-600">from {ingestedFilesCount} files</span>
              </div>
            </div>

            <div className="neo-brutal-card p-5 bg-white">
              <div className="flex items-center justify-between text-xs font-extrabold uppercase font-mono text-gray-700">
                <span>Paper Sections</span>
                <span className="neo-badge neo-badge-neutral">
                  Structure
                </span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black font-mono text-black">{paperAST.sections.length}</span>
                <span className="text-xs font-bold text-gray-600">parsed sections</span>
              </div>
            </div>

            <div className="neo-brutal-card p-5 bg-white">
              <div className="flex items-center justify-between text-xs font-extrabold uppercase font-mono text-gray-700">
                <span>Risk Status</span>
                <span className={`neo-badge ${
                  riskLevel === 'CRITICAL' ? 'neo-badge-critical' :
                  riskLevel === 'HIGH'     ? 'neo-badge-high' :
                  riskLevel === 'MAJOR'    ? 'neo-badge-major' :
                  riskLevel === 'MINOR'    ? 'neo-badge-minor' :
                                             'neo-badge-neutral'
                }`}>
                  {riskLevel}
                </span>
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black font-mono text-black">
                  {analysis ? `${affectedSectionsCount} Affected` : 'Ready'}
                </span>
                <span className="text-xs font-bold text-gray-600">
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
          <div className="pt-2 border-t-2 border-black">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2">
              <button
                className={`neo-brutal-tab ${activeTab === 'overview' ? 'neo-brutal-tab-active' : ''}`}
                onClick={() => setActiveTab('overview')}
              >
                Overview ({affectedSectionsCount})
              </button>
              <button
                className={`neo-brutal-tab ${activeTab === 'paper' ? 'neo-brutal-tab-active' : ''}`}
                onClick={() => setActiveTab('paper')}
              >
                Manuscript ({paperAST.sections.length})
              </button>
              <button
                className={`neo-brutal-tab ${activeTab === 'experiments' ? 'neo-brutal-tab-active' : ''}`}
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
                    <div className="neo-brutal-card p-12 text-center space-y-2 bg-white">
                      <div className="w-12 h-12 rounded-xl bg-[#fde047] text-black font-black text-2xl mx-auto flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_#000]">
                        ⚡
                      </div>
                      <h4 className="text-sm font-black uppercase font-mono text-black">Ready to Analyze Impact</h4>
                      <p className="text-xs text-gray-700 max-w-md mx-auto font-medium">
                        Load your repository, upload your paper, and enter a proposed change query to generate the blast radius report.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {analysis.affected_sections?.length > 0 ? (
                        <div className="neo-brutal-card p-6 space-y-4 bg-white">
                          <div className="flex items-center justify-between pb-2 border-b-2 border-black">
                            <h3 className="text-sm font-extrabold uppercase font-mono text-black">
                              Identified Affected Sections ({analysis.affected_sections.length})
                            </h3>
                            <span className="text-xs font-bold text-gray-600">
                              Blast Radius Summary
                            </span>
                          </div>

                          <div className="space-y-3">
                            {analysis.affected_sections.map((sec, i) => (
                              <div
                                key={i}
                                className="p-4 rounded-xl border-2 border-black bg-white shadow-[3px_3px_0px_#000] flex items-start gap-4"
                              >
                                <span className={`neo-badge shrink-0 ${
                                  sec.risk === 'CRITICAL' ? 'neo-badge-critical' :
                                  sec.risk === 'HIGH'     ? 'neo-badge-high' :
                                  sec.risk === 'MAJOR'    ? 'neo-badge-major' :
                                                            'neo-badge-minor'
                                }`}>
                                  {sec.risk || 'MINOR'}
                                </span>
                                <div className="space-y-1">
                                  <p className="text-xs font-bold text-black">{sec.title}</p>
                                  <p className="text-xs text-gray-700 font-medium leading-relaxed">{sec.reason}</p>
                                  {sec.suggested_text && (
                                    <div className="mt-2 p-2.5 bg-[#fffef0] border-2 border-black rounded-lg text-xs font-mono text-black shadow-[2px_2px_0px_#000]">
                                      <span className="text-[10px] font-extrabold uppercase text-gray-600 block mb-1">Suggested Revision:</span>
                                      {sec.suggested_text}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="neo-brutal-card p-8 text-center text-xs font-bold bg-[#86efac] text-black">
                          ✓ No paper sections appear to be adversely impacted by this code modification.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: MANUSCRIPT DETAILS */}
              {activeTab === 'paper' && (
                <div className="neo-brutal-card p-6 bg-white">
                  <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
                </div>
              )}

              {/* TAB 3: EQUATIONS & TABLES */}
              {activeTab === 'experiments' && (
                <div className="space-y-4">
                  {analysis?.affected_equations?.length > 0 && (
                    <div className="neo-brutal-card p-6 space-y-3 bg-white">
                      <h4 className="text-xs font-black uppercase tracking-wider font-mono text-black">
                        Affected Equations ({analysis.affected_equations.length})
                      </h4>
                      {analysis.affected_equations.map((eq, i) => (
                        <div key={i} className="p-3 border-2 border-black rounded-lg flex items-start gap-3 text-xs bg-[#fffef0] shadow-[2px_2px_0px_#000]">
                          <span className="neo-badge neo-badge-major">
                            {eq.risk}
                          </span>
                          <div>
                            <p className="font-bold text-black">{eq.label}</p>
                            <p className="text-gray-700 font-medium">{eq.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {analysis?.affected_tables?.length > 0 && (
                    <div className="neo-brutal-card p-6 space-y-3 bg-white">
                      <h4 className="text-xs font-black uppercase tracking-wider font-mono text-black">
                        Affected Tables ({analysis.affected_tables.length})
                      </h4>
                      {analysis.affected_tables.map((tbl, i) => (
                        <div key={i} className="p-3 border-2 border-black rounded-lg flex items-start gap-3 text-xs bg-[#fffef0] shadow-[2px_2px_0px_#000]">
                          <span className="neo-badge neo-badge-major">
                            {tbl.risk}
                          </span>
                          <div>
                            <p className="font-bold text-black">{tbl.label}</p>
                            <p className="text-gray-700 font-medium">{tbl.explanation}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {!analysis?.affected_equations?.length && !analysis?.affected_tables?.length && (
                    <div className="neo-brutal-card p-10 text-center text-xs font-bold text-gray-700 bg-white">
                      No mathematical equations or experimental tables affected by this change.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </main>

        <footer className="py-6 text-center text-xs font-bold text-gray-600 border-t-2 border-black mt-12 bg-white">
          Radly — Research Code &amp; Paper Impact Analyzer · Neo-Brutalist Edition
        </footer>
      </div>
    </div>
  );
}
