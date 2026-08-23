import React, { useState } from 'react';
import BlastRadiusHeader from './components/BlastRadiusHeader';
import WhatIfConsole from './components/WhatIfConsole';
import CodeGraphViewer from './components/CodeGraphViewer';
import PaperImpactViewer from './components/PaperImpactViewer';
import DependencyFlow from './components/DependencyFlow';

/**
 * Robust JSON response handler. Handles Vercel 413 Request Entity Too Large HTML responses safely.
 */
async function safeFetchJson(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = {};

  try {
    data = JSON.parse(text);
  } catch (e) {
    if (res.status === 413 || text.includes('Request Entity Too Large')) {
      throw new Error('PDF document payload exceeds Vercel 4.5MB limit. Please select a smaller PDF file or paste the text excerpt.');
    }
    throw new Error(text.slice(0, 100) || `Server returned HTTP ${res.status}`);
  }

  if (!res.ok) {
    throw new Error(data.error || `Request failed with HTTP ${res.status}`);
  }

  return data;
}

export default function App() {
  // Start with completely blank empty state (0 prefilled mock data)
  const [repoUrl, setRepoUrl] = useState('');
  const [query, setQuery] = useState('');
  const [paperText, setPaperText] = useState('');
  const [selectedFileName, setSelectedFileName] = useState('');

  const [codeSymbols, setCodeSymbols] = useState([]);
  const [ingestedFilesCount, setIngestedFilesCount] = useState(0);
  const [paperAST, setPaperAST] = useState({ sections: [], equations: [], tables: [], numbers: [] });
  const [analysis, setAnalysis] = useState(null);

  // Distinct independent loading states
  const [isIngestingCode, setIsIngestingCode] = useState(false);
  const [isParsingPaper, setIsParsingPaper] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [activeTab, setActiveTab] = useState('overview');

  // Ingest GitHub Repository
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
      console.error('Repo ingestion error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsIngestingCode(false);
    }
  };

  // Upload Code Files Directly
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
      console.error('Code file upload error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsIngestingCode(false);
    }
  };

  // Parse Raw Paper Text Excerpt
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
      console.error('Paper text parse error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsParsingPaper(false);
    }
  };

  // Upload PDF / DOCX / LaTeX Document using native browser FileReader Base64
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
            body: JSON.stringify({
              paperFileBase64: base64Data,
              fileType: ext
            })
          });

          setPaperAST(data.paperAST || { sections: [], equations: [], tables: [], numbers: [] });
        } catch (err) {
          console.error('Document parse error:', err);
          setErrorMsg(err.message);
        } finally {
          setIsParsingPaper(false);
        }
      };

      reader.onerror = () => {
        setErrorMsg('Failed to read document file.');
        setIsParsingPaper(false);
      };

      reader.readAsDataURL(file);
    } catch (err) {
      console.error('File reader error:', err);
      setErrorMsg(err.message);
      setIsParsingPaper(false);
    }
  };

  // Calculate Blast Radius Analysis
  const handleCalculateBlastRadius = async () => {
    if (!query.trim()) return;
    setIsAnalyzing(true);
    setErrorMsg('');
    try {
      const data = await safeFetchJson('/api/analyze-impact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          codeSymbols,
          paperAST,
          query
        })
      });

      setAnalysis(data.analysis || null);
    } catch (err) {
      console.error('Blast radius calculation error:', err);
      setErrorMsg(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Export Audit Report (.json)
  const handleExportReport = () => {
    if (!analysis) return;
    const reportData = {
      timestamp: new Date().toISOString(),
      query,
      repository: repoUrl,
      symbolsIndexedCount: codeSymbols.length,
      sectionsCount: paperAST.sections.length,
      blastRadiusAnalysis: analysis
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `paperblast-audit-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[#dbeafe] text-slate-900 flex flex-col items-center w-full font-sans">
      {/* Centered App Container */}
      <div className="app-wrapper space-y-6 flex flex-col items-center">
        {/* Top Header */}
        <BlastRadiusHeader
          analysis={analysis}
          hasCode={codeSymbols.length > 0}
          hasPaper={paperAST.sections.length > 0}
          isIngesting={isIngestingCode}
          isParsingPaper={isParsingPaper}
          isAnalyzing={isAnalyzing}
          onExportReport={handleExportReport}
        />

        {/* Main Content Area */}
        <main className="w-full space-y-6 flex flex-col items-center">
          {/* Error Alert */}
          {errorMsg && (
            <div className="bg-rose-200 border-2 border-black text-black px-4 py-3 rounded-md font-mono text-xs flex items-center justify-between shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] w-full">
              <span className="font-bold">Error: {errorMsg}</span>
              <button className="neo-btn-white py-0.5 px-2 text-xs" onClick={() => setErrorMsg('')}>Dismiss</button>
            </div>
          )}

          {/* Input Console */}
          <WhatIfConsole
            query={query}
            setQuery={setQuery}
            onCalculate={handleCalculateBlastRadius}
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

          {/* Workspace Navigation Tabs (Centered) */}
          <div className="flex flex-wrap items-center justify-center gap-3 py-2 w-full">
            <button
              className={`neo-tab ${activeTab === 'overview' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('overview')}
            >
              Impact Overview
            </button>
            <button
              className={`neo-tab ${activeTab === 'manuscript' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('manuscript')}
            >
              Manuscript Section Matrix ({paperAST.sections.length})
            </button>
            <button
              className={`neo-tab ${activeTab === 'lineage' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('lineage')}
            >
              Bipartite Lineage Graph ({analysis?.lineage_graph?.length || 0})
            </button>
            <button
              className={`neo-tab ${activeTab === 'agents' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('agents')}
            >
              Agent Trace ({analysis?.agent_collaboration_trace?.length ?? 0})
            </button>
            <button
              className={`neo-tab ${activeTab === 'code' ? 'neo-tab-active' : ''}`}
              onClick={() => setActiveTab('code')}
            >
              Code AST Symbols ({codeSymbols.length})
            </button>
          </div>

          {/* Tab Contents */}
          <div className="w-full">
            {activeTab === 'overview' && (
              <div className="space-y-6 w-full">
                {/* Lineage Graph Flow */}
                {analysis?.lineage_graph && analysis.lineage_graph.length > 0 && (
                  <DependencyFlow lineageGraph={analysis.lineage_graph} />
                )}

                {/* Split Screen Grid: Code AST (Left) vs Paper Matrix (Right) */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 w-full items-start">
                  {/* Left: Code AST Symbols (auto height fit) */}
                  <div className="lg:col-span-4 neo-box p-5 self-start h-fit">
                    <CodeGraphViewer symbols={codeSymbols} />
                  </div>

                  {/* Right: Paper Impact Matrix */}
                  <div className="lg:col-span-8 neo-box p-5 self-start">
                    <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'manuscript' && (
              <div className="neo-box p-5 w-full">
                <PaperImpactViewer paperAST={paperAST} analysis={analysis} />
              </div>
            )}

            {activeTab === 'lineage' && (
              <div className="neo-box p-5 w-full">
                <DependencyFlow lineageGraph={analysis?.lineage_graph || []} />
              </div>
            )}

            {activeTab === 'agents' && (
              <div className="neo-box p-5 space-y-4 w-full">
                <div className="flex flex-col items-start border-b-2 border-black pb-2 gap-0.5">
                  <h3 className="text-xs font-extrabold text-black uppercase tracking-wider font-mono">
                    Multi-Agent Collaboration Trace Log
                  </h3>
                  <p className="text-[11px] font-mono font-semibold text-slate-600">
                    Auditable state log showing roles and outputs performed by each agent during this analysis run.
                  </p>
                  {analysis?.status && (
                    <span className="mt-1 bg-slate-100 border border-black px-2 py-0.5 rounded text-[10px] font-mono font-extrabold">
                      Analysis Status: {analysis.status}
                    </span>
                  )}
                </div>
                {!analysis ? (
                  <p className="text-xs font-mono text-slate-500 py-4 text-center">
                    No analysis run yet. Run a Blast Radius calculation to see the agent trace.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {(analysis.agent_collaboration_trace || []).map((trace, idx) => (
                      <div key={idx} className="bg-white border-2 border-black p-4 rounded-md font-mono text-xs shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-extrabold text-black uppercase text-xs">{trace.agent}</span>
                          <span className="bg-slate-100 border border-black px-2 py-0.5 rounded text-[10px] font-extrabold">COMPLETED</span>
                        </div>
                        <p className="text-[11px] text-slate-700 font-bold">Role: {trace.role}</p>
                        <p className="text-[11px] text-slate-900 font-medium">Output: {trace.output_summary}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'code' && (
              <div className="neo-box p-5 w-full">
                <CodeGraphViewer symbols={codeSymbols} />
              </div>
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="w-full neo-box py-4 px-6 text-center text-xs font-mono font-bold text-black mt-6">
          PaperBlast Program Analysis Engine — Multi-Agent Bipartite Program AST & Manuscript Blast Radius Engine
        </footer>
      </div>
    </div>
  );
}
