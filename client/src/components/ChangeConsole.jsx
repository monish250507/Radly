import React from 'react';

/**
 * ChangeConsole — renamed from WhatIfConsole.
 *
 * P1 FIX:
 * - Button renamed from "Calculate Blast Radius" → "Analyse Impact"
 * - Step 3 label updated to "Code Change or Diff Description"
 * - Changed placeholder to be more concrete and actionable
 * - Loading text updated ("Analysing Impact…" not "Calculating Blast Radius…")
 * - File counts display more detail (symbol types)
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
    <div className="neo-box p-6 space-y-6 max-w-4xl mx-auto w-full text-center">
      {/* Stepped Setup Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-b border-[var(--border-color)] pb-6">

        {/* Step 1: Code Repository */}
        <div className="space-y-3 flex flex-col items-start">
          <div className="flex items-center justify-between w-full">
            <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
              1. Code Repository
            </h3>
            {symbolsCount > 0 && (
              <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded shadow-sm">
                {symbolsCount} symbols · {ingestedFilesCount} file{ingestedFilesCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <p className="text-[11px] font-medium text-gray-500 text-left">
            Index functions, variables, and parameters from Python or JavaScript code.
          </p>

          <div className="space-y-2 w-full pt-1">
            <div className="flex gap-2 w-full">
              <input
                id="repo-url-input"
                type="text"
                className="neo-input flex-1"
                placeholder="GitHub URL (e.g. https://github.com/openai/CLIP)"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !isIngesting && repoUrl.trim() && onIngestRepo()}
              />
              <button
                id="ingest-repo-btn"
                className="neo-btn whitespace-nowrap"
                onClick={onIngestRepo}
                disabled={isIngesting || !repoUrl.trim()}
              >
                {isIngesting ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
                    Ingesting…
                  </span>
                ) : 'Load Repo'}
              </button>
            </div>

            <div className="flex items-center justify-between text-[11px] font-medium text-gray-500 pt-1 w-full">
              <span>Or upload files directly (.py, .js, .json):</span>
              <label id="code-upload-label" className="neo-btn-white py-1 px-2.5 cursor-pointer whitespace-nowrap">
                Upload Code Files
                <input type="file" multiple accept=".py,.js,.ts,.json" className="hidden" onChange={onCodeFileUpload} />
              </label>
            </div>
          </div>
        </div>

        {/* Step 2: Research Paper */}
        <div className="space-y-3 flex flex-col items-start">
          <div className="flex items-center justify-between w-full">
            <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
              2. Research Paper
            </h3>
            {sectionsCount > 0 && (
              <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded shadow-sm">
                {sectionsCount} section{sectionsCount !== 1 ? 's' : ''} parsed
              </span>
            )}
          </div>
          <p className="text-[11px] font-medium text-gray-500 text-left">
            Extracts section structure, LaTeX equations, and numerical claims from PDF or DOCX.
          </p>

          <div className="space-y-2 w-full pt-1">
            <div className="flex gap-2 w-full">
              <textarea
                id="paper-text-input"
                className="neo-input flex-1 h-12 resize-none py-1.5"
                placeholder="Paste LaTeX source or text excerpt here…"
                value={paperText}
                onChange={(e) => setPaperText(e.target.value)}
              />
              <button
                id="parse-paper-btn"
                className="neo-btn h-12 whitespace-nowrap"
                onClick={onParsePaper}
                disabled={isParsingPaper || !paperText.trim()}
              >
                {isParsingPaper ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
                    Parsing…
                  </span>
                ) : 'Parse Text'}
              </button>
            </div>

            <div className="flex items-center justify-between text-[11px] font-medium text-gray-500 pt-1 w-full">
              <span>Upload paper (.pdf, .docx, .tex):</span>
              <label id="paper-upload-label" className="neo-btn-white py-1 px-2.5 cursor-pointer whitespace-nowrap">
                {isParsingPaper
                  ? <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />Parsing…</span>
                  : selectedFileName || 'Upload PDF / Docx'}
                <input type="file" accept=".pdf,.docx,.tex,.txt" className="hidden" onChange={onPaperFileUpload} />
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* Step 3: Change Query — P1 FIX: renamed and clearer description */}
      <div className="space-y-3 flex flex-col items-center max-w-2xl mx-auto w-full">
        <div className="flex flex-col items-center justify-center w-full gap-0.5">
          <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono text-center">
            3. Code Change or Diff Description
          </h3>
          <p className="text-[11px] font-medium text-gray-500 text-center">
            Describe the change (e.g. a PR diff, parameter mutation, or refactoring) to trace its impact across the paper.
          </p>
        </div>

        <div className="space-y-3 w-full pt-1">
          <textarea
            id="change-query-input"
            className="neo-input h-16 resize-none leading-relaxed w-full text-center"
            placeholder="e.g. Changed learning_rate from 0.01 to 0.001 in train.py (line 42). Or paste a Git diff."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          {/* P1 FIX: renamed button */}
          <div className="flex justify-center pt-1 w-full">
            <button
              id="analyse-impact-btn"
              className={`neo-btn py-3 px-10 text-sm font-extrabold tracking-wide font-mono transition-opacity ${!canAnalyse ? 'opacity-50 cursor-not-allowed' : ''}`}
              onClick={onCalculate}
              disabled={!canAnalyse}
            >
              {isAnalyzing ? (
                <span className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-current animate-pulse" />
                  Analysing Impact…
                </span>
              ) : 'Analyse Impact'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
