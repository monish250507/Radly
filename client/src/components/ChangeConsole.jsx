import React from 'react';

/**
 * Modern SaaS ChangeConsole — Clean stepped cards with zero clutter.
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
      {/* 2-Column Clean Ingestion Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Card 1: Code Repository */}
        <div className="radly-card p-6 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-indigo-50 text-indigo-600 font-semibold text-xs flex items-center justify-center border border-indigo-100">
                  1
                </span>
                <h3 className="text-sm font-semibold text-[var(--text-main)]">
                  Code Repository
                </h3>
              </div>
              {symbolsCount > 0 && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {symbolsCount} symbols · {ingestedFilesCount} file{ingestedFilesCount !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Index AST symbols, hyperparameters, and functions directly from a public repository or uploaded files.
            </p>

            <div className="space-y-3 pt-2">
              <div className="flex gap-2">
                <input
                  id="repo-url-input"
                  type="text"
                  className="radly-input text-xs"
                  placeholder="https://github.com/owner/repository"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !isIngesting && repoUrl.trim() && onIngestRepo()}
                />
                <button
                  id="ingest-repo-btn"
                  className="btn-primary text-xs shrink-0"
                  onClick={onIngestRepo}
                  disabled={isIngesting || !repoUrl.trim()}
                >
                  {isIngesting ? (
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                      Loading…
                    </span>
                  ) : 'Load Repo'}
                </button>
              </div>

              <div className="flex items-center justify-between text-xs text-[var(--text-muted)] pt-1 border-t border-[var(--border-color)]">
                <span>Or upload source files:</span>
                <label id="code-upload-label" className="btn-secondary text-xs cursor-pointer">
                  Choose Files (.py, .js)
                  <input type="file" multiple accept=".py,.js,.ts,.json" className="hidden" onChange={onCodeFileUpload} />
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Research Paper */}
        <div className="radly-card p-6 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-indigo-50 text-indigo-600 font-semibold text-xs flex items-center justify-center border border-indigo-100">
                  2
                </span>
                <h3 className="text-sm font-semibold text-[var(--text-main)]">
                  Research Manuscript
                </h3>
              </div>
              {sectionsCount > 0 && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {sectionsCount} section{sectionsCount !== 1 ? 's' : ''} parsed
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">
              Upload a scientific paper (PDF, DOCX) or paste LaTeX to extract section hierarchy, equations, and tables.
            </p>

            <div className="space-y-3 pt-2">
              <div className="flex gap-2">
                <textarea
                  id="paper-text-input"
                  className="radly-input text-xs h-10 resize-none py-2"
                  placeholder="Paste LaTeX source or manuscript excerpt…"
                  value={paperText}
                  onChange={(e) => setPaperText(e.target.value)}
                />
                <button
                  id="parse-paper-btn"
                  className="btn-primary text-xs shrink-0"
                  onClick={onParsePaper}
                  disabled={isParsingPaper || !paperText.trim()}
                >
                  {isParsingPaper ? (
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                      Parsing…
                    </span>
                  ) : 'Parse Text'}
                </button>
              </div>

              <div className="flex items-center justify-between text-xs text-[var(--text-muted)] pt-1 border-t border-[var(--border-color)]">
                <span>Upload document:</span>
                <label id="paper-upload-label" className="btn-secondary text-xs cursor-pointer">
                  {isParsingPaper ? (
                    <span className="flex items-center gap-1.5 text-indigo-600">
                      <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
                      Reading Document…
                    </span>
                  ) : (
                    selectedFileName || 'Upload PDF / DOCX'
                  )}
                  <input type="file" accept=".pdf,.docx,.tex,.txt" className="hidden" onChange={onPaperFileUpload} />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Banner: Step 3 Change Query */}
      <div className="radly-card p-6 bg-gradient-to-r from-white via-white to-indigo-50/40 border border-[var(--border-color)]">
        <div className="space-y-3 max-w-3xl">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-indigo-600 text-white font-semibold text-xs flex items-center justify-center">
              3
            </span>
            <h3 className="text-sm font-semibold text-[var(--text-main)]">
              Specify Code Change or PR Diff
            </h3>
          </div>
          <p className="text-xs text-[var(--text-muted)]">
            Describe your modification (e.g., hyperparameter tuning, function refactor, or paste a Git diff snippet) to analyze impact across manuscript claims.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-3 pt-1">
            <input
              id="change-query-input"
              type="text"
              className="radly-input text-xs flex-1 py-3"
              placeholder="e.g. Changed learning_rate from 0.01 to 0.001 in train.py line 42, or updated batch size"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && canAnalyse && onCalculate()}
            />
            <button
              id="analyse-impact-btn"
              className="btn-primary text-xs px-6 py-3 shrink-0 whitespace-nowrap shadow-md"
              onClick={onCalculate}
              disabled={!canAnalyse}
            >
              {isAnalyzing ? (
                <span className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-white animate-pulse" />
                  Analyzing Impact…
                </span>
              ) : (
                <span className="flex items-center gap-2 font-semibold">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Analyze Impact
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
