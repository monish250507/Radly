import React from 'react';

export default function WhatIfConsole({
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
  selectedFileName
}) {
  return (
    <div className="neo-box p-6 space-y-6 max-w-4xl mx-auto w-full text-center">
      {/* Inputs Stepped Setup Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-b border-[var(--border-color)] pb-6">
        
        {/* Step 1: Code Repository Input */}
        <div className="space-y-3 flex flex-col items-center">
          <div className="flex flex-col items-start w-full gap-0.5">
            <div className="flex items-center justify-between w-full">
              <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono text-left">
                1. Code Repository Input
              </h3>
              {symbolsCount > 0 && (
                <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded shadow-sm">
                  Indexed {symbolsCount} AST Symbols ({ingestedFilesCount} file)
                </span>
              )}
            </div>
            <p className="text-[11px] font-medium text-gray-500 text-left">
              Indexes functions, variables, parameters, and AST symbols from Python or JS code.
            </p>
          </div>

          <div className="space-y-2 w-full pt-1">
            <div className="flex gap-2 w-full">
              <input
                type="text"
                className="neo-input flex-1"
                placeholder="Paste GitHub Repository URL (e.g. https://github.com/openai/CLIP)..."
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
              />
              <button
                className="neo-btn whitespace-nowrap"
                onClick={onIngestRepo}
                disabled={isIngesting || !repoUrl.trim()}
              >
                {isIngesting ? 'Ingesting...' : 'Ingest Repo'}
              </button>
            </div>

            <div className="flex items-center justify-between text-[11px] font-medium text-gray-500 pt-1 w-full">
              <span>Or Upload Code Files (.py, .js, .json):</span>
              <label className="neo-btn-white py-1 px-2.5 cursor-pointer whitespace-nowrap">
                Choose Code Files
                <input
                  type="file"
                  multiple
                  accept=".py,.js,.ts,.json"
                  className="hidden"
                  onChange={onCodeFileUpload}
                />
              </label>
            </div>
          </div>
        </div>

        {/* Step 2: Research Paper Manuscript Input */}
        <div className="space-y-3 flex flex-col items-center">
          <div className="flex flex-col items-start w-full gap-0.5">
            <div className="flex items-center justify-between w-full">
              <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono text-left">
                2. Research Paper Manuscript Input
              </h3>
              {sectionsCount > 0 && (
                <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded shadow-sm">
                  Parsed {sectionsCount} Structural Sections
                </span>
              )}
            </div>
            <p className="text-[11px] font-medium text-gray-500 text-left">
              Extracts section hierarchies, LaTeX equations, and numerical claims from PDF or DOCX.
            </p>
          </div>

          <div className="space-y-2 w-full pt-1">
            <div className="flex gap-2 w-full">
              <textarea
                className="neo-input flex-1 h-12 resize-none py-1.5"
                placeholder="Paste LaTeX manuscript or text excerpt here..."
                value={paperText}
                onChange={(e) => setPaperText(e.target.value)}
              />
              <button
                className="neo-btn h-12 whitespace-nowrap"
                onClick={onParsePaper}
                disabled={isParsingPaper || !paperText.trim()}
              >
                {isParsingPaper ? 'Parsing...' : 'Parse Text'}
              </button>
            </div>

            <div className="flex items-center justify-between text-[11px] font-medium text-gray-500 pt-1 w-full">
              <span>Upload Document (.pdf, .docx, .tex):</span>
              <label className="neo-btn-white py-1 px-2.5 cursor-pointer whitespace-nowrap">
                {isParsingPaper ? 'Parsing PDF...' : selectedFileName ? selectedFileName : 'Upload PDF/Docx'}
                <input
                  type="file"
                  accept=".pdf,.docx,.tex,.txt"
                  className="hidden"
                  onChange={onPaperFileUpload}
                />
              </label>
            </div>
          </div>
        </div>

      </div>

      {/* Step 3: Change Query & Blast Radius Launcher */}
      <div className="space-y-3 flex flex-col items-center max-w-2xl mx-auto w-full">
        <div className="flex flex-col items-center justify-center w-full gap-0.5">
          <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono text-center">
            3. Code Logic & Parameter Change Query
          </h3>
          <p className="text-[11px] font-medium text-gray-500 text-center">
            Define a proposed parameter mutation to evaluate its blast radius impact across paper sections.
          </p>
        </div>

        <div className="space-y-3 w-full pt-1">
          <textarea
            className="neo-input h-16 resize-none leading-relaxed w-full text-center"
            placeholder="What happens if I change the temperature scaling parameter tau from 0.07 to 0.01 in the contrastive loss?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          <div className="flex justify-center pt-1 w-full">
            <button
              className="neo-btn py-3 px-10 text-xs font-extrabold tracking-wide font-mono text-sm"
              onClick={onCalculate}
              disabled={isAnalyzing || !query.trim()}
            >
              {isAnalyzing ? 'Calculating Blast Radius...' : 'Calculate Blast Radius'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
