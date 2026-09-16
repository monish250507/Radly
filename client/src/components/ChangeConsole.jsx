import React from 'react';

/**
 * Neo-Brutalism ChangeConsole — Crisp black borders, retro offset shadows, and vibrant purple action button.
 */
export default function ChangeConsole({
  query,
  setQuery,
  onCalculate,
  repoUrl,
  setRepoUrl,
  onIngestRepo,
  onCodeFileUpload,
  onPaperFileUpload,
  paperText,
  setPaperText,
  onParsePaper,
  isIngesting,
  isParsingPaper,
  isAnalyzing,
  ingestedFilesCount,
  symbolsCount,
  sectionsCount,
  selectedFileName,
}) {
  const canAnalyse = query.trim().length > 0 && !isAnalyzing;

  return (
    <div className="space-y-6 w-full">
      {/* 2-Column Neo-Brutalist Setup Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Card 1: Code Repository */}
        <div className="neo-brutal-card p-6 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-7 h-7 rounded-lg bg-[#6355d8] text-white font-black text-xs flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_#000]">
                  1
                </span>
                <h3 className="text-sm font-extrabold text-black uppercase tracking-wide font-mono">
                  Code Repository
                </h3>
              </div>
              {symbolsCount > 0 && (
                <span className="neo-badge neo-badge-verified">
                  ✓ {symbolsCount} symbols ({ingestedFilesCount} files)
                </span>
              )}
            </div>
            <p className="text-xs text-gray-700 font-medium leading-relaxed">
              Extract AST definitions, hyperparameters, and functions directly from GitHub or source files.
            </p>

            <div className="space-y-3 pt-2">
              <div className="flex gap-2">
                <input
                  id="repo-url-input"
                  type="text"
                  className="neo-brutal-input text-xs"
                  placeholder="https://github.com/owner/repository"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !isIngesting && repoUrl.trim() && onIngestRepo()}
                />
                <button
                  id="ingest-repo-btn"
                  className="neo-brutal-btn-primary text-xs shrink-0"
                  onClick={onIngestRepo}
                  disabled={isIngesting || !repoUrl.trim()}
                >
                  {isIngesting ? (
                    <span className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      Cloning & Indexing…
                    </span>
                  ) : 'Load Repo'}
                </button>
              </div>

              <div className="flex items-center justify-between text-xs font-semibold text-gray-700 pt-2 border-t-2 border-black">
                <span>Or upload source files:</span>
                <label id="code-upload-label" className="neo-brutal-btn-white text-xs cursor-pointer">
                  📁 Choose .py / .js
                  <input type="file" multiple accept=".py,.js,.ts,.json" className="hidden" onChange={onCodeFileUpload} />
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Research Paper */}
        <div className="neo-brutal-card p-6 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="w-7 h-7 rounded-lg bg-[#6355d8] text-white font-black text-xs flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_#000]">
                  2
                </span>
                <h3 className="text-sm font-extrabold text-black uppercase tracking-wide font-mono">
                  Research Paper
                </h3>
              </div>
              {sectionsCount > 0 && (
                <span className="neo-badge neo-badge-verified">
                  ✓ {sectionsCount} sections parsed
                </span>
              )}
            </div>
            <p className="text-xs text-gray-700 font-medium leading-relaxed">
              Upload a scientific PDF/DOCX or paste LaTeX to map sections, equations, and tables.
            </p>

            <div className="space-y-3 pt-2">
              <div className="flex gap-2">
                <textarea
                  id="paper-text-input"
                  className="neo-brutal-input text-xs h-10 resize-none py-2"
                  placeholder="Paste LaTeX source or text excerpt…"
                  value={paperText}
                  onChange={(e) => setPaperText(e.target.value)}
                />
                <button
                  id="parse-paper-btn"
                  className="neo-brutal-btn-primary text-xs shrink-0"
                  onClick={onParsePaper}
                  disabled={isParsingPaper || !paperText.trim()}
                >
                  {isParsingPaper ? 'Parsing…' : 'Parse Text'}
                </button>
              </div>

              <div className="flex items-center justify-between text-xs font-semibold text-gray-700 pt-2 border-t-2 border-black">
                <span>Upload manuscript:</span>
                <label id="paper-upload-label" className="neo-brutal-btn-white text-xs cursor-pointer">
                  {isParsingPaper ? '⏳ Reading…' : (selectedFileName ? `📄 ${selectedFileName}` : '📄 Upload PDF / DOCX')}
                  <input type="file" accept=".pdf,.docx,.tex,.txt" className="hidden" onChange={onPaperFileUpload} />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Step 3: Change Query Banner */}
      <div className="neo-brutal-card p-6 bg-[#fffef0]">
        <div className="space-y-3 max-w-4xl">
          <div className="flex items-center gap-2.5">
            <span className="w-7 h-7 rounded-lg bg-black text-[#fde047] font-black text-xs flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_#000]">
              3
            </span>
            <h3 className="text-sm font-extrabold text-black uppercase tracking-wide font-mono">
              Describe Code Change or Diff
            </h3>
          </div>
          <p className="text-xs text-gray-700 font-medium">
            Specify the parameter mutation, PR diff, or refactoring to track affected claims across the paper.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-3 pt-1">
            <input
              id="change-query-input"
              type="text"
              className="neo-brutal-input text-xs flex-1 py-3 bg-white"
              placeholder="e.g. Changed learning_rate from 0.01 to 0.001 in train.py line 42"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && canAnalyse && onCalculate()}
            />
            <button
              id="analyse-impact-btn"
              className="neo-brutal-btn-primary text-xs px-8 py-3 shrink-0 whitespace-nowrap text-white font-black"
              onClick={onCalculate}
              disabled={!canAnalyse}
            >
              {isAnalyzing ? (
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                  ANALYSING BLAST RADIUS…
                </span>
              ) : (
                '⚡ ANALYSE IMPACT'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
