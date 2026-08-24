import React from 'react';

export default function CodeGraphViewer({ symbols }) {
  if (!symbols || symbols.length === 0) {
    return (
      <div className="p-4 text-center text-slate-700 font-mono text-xs font-bold">
        No code AST symbols indexed. Input a GitHub URL or code files.
      </div>
    );
  }

  return (
    <div className="space-y-4 w-full overflow-hidden h-fit">
      <div className="flex flex-col items-start border-b border-[var(--border-color)] pb-2 gap-0.5">
        <div className="flex items-center justify-between w-full">
          <h3 className="text-xs font-semibold text-[var(--box-text)] uppercase tracking-wider font-mono">
            Indexed Code AST Symbols ({symbols.length})
          </h3>
          <span className="text-[11px] font-medium text-gray-500">AST Index</span>
        </div>
        <p className="text-[11px] font-medium text-gray-500">
          Variables, hyperparameters, and AST symbols indexed by source file line.
        </p>
      </div>

      <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1 w-full">
        {symbols.map((sym, idx) => (
          <div
            key={idx}
            className="neo-box p-3 w-full flex flex-col space-y-1.5 overflow-hidden"
          >
            {/* Row 1: Symbol Name & Type Badge */}
            <div className="flex items-center justify-between gap-2 w-full">
              <span className="text-[var(--box-text)] font-semibold text-xs truncate break-all" title={sym.symbol}>
                {sym.symbol}
              </span>
              <span className="text-[10px] uppercase bg-sky-500/10 border border-sky-500/20 text-sky-600 font-semibold px-1.5 py-0.5 rounded whitespace-nowrap">
                {sym.type}
              </span>
            </div>

            {/* Row 2: File Anchor & Line Number */}
            <div className="flex items-center justify-between text-gray-500 font-medium text-[11px] w-full pt-0.5 border-t border-[var(--border-color)]">
              <span className="truncate max-w-[180px]" title={sym.file}>
                {sym.file}
              </span>
              <span className="text-[var(--box-text)] font-semibold whitespace-nowrap">Line {sym.line}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
