import React, { useState } from 'react';

export default function CodeGraphViewer({ symbols }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  if (!symbols || symbols.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 font-mono text-xs">
        No code AST symbols indexed. Input a GitHub URL or upload code files.
      </div>
    );
  }

  const filtered = symbols.filter(s => 
    !searchTerm || 
    (s.symbol || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (s.file || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const displayed = filtered.slice(0, page * PAGE_SIZE);

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight - scrollTop - clientHeight < 80) {
      if (displayed.length < filtered.length) {
        setPage(p => p + 1);
      }
    }
  };

  return (
    <div className="space-y-3 w-full">
      <div className="flex items-center justify-between gap-2">
        <input
          type="text"
          className="neo-brutal-input text-xs py-1.5 px-2.5 w-full max-w-xs"
          placeholder="Search symbols (e.g. lora, rank, train)..."
          value={searchTerm}
          onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
        />
        <span className="text-[11px] font-mono text-gray-600 shrink-0">
          {displayed.length} of {filtered.length} visible
        </span>
      </div>

      <div
        onScroll={handleScroll}
        className="space-y-2 max-h-[400px] overflow-y-auto pr-1 w-full"
      >
        {displayed.map((sym, idx) => (
          <div
            key={idx}
            className="p-2.5 border-2 border-black rounded-lg bg-white shadow-[2px_2px_0px_#000] flex flex-col gap-1"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-bold text-xs font-mono text-black truncate" title={sym.symbol}>
                {sym.symbol}
              </span>
              <span className="neo-badge neo-badge-minor text-[9px] py-0.5 px-1.5 shrink-0">
                {sym.type || 'SYMBOL'}
              </span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono text-gray-600 pt-1 border-t border-gray-200">
              <span className="truncate max-w-[200px]" title={sym.file}>{sym.file}</span>
              <span className="font-bold shrink-0">Line {sym.line}</span>
            </div>
          </div>
        ))}

        {displayed.length < filtered.length && (
          <div className="text-center py-2 text-xs font-mono text-gray-500 font-bold">
            Scroll down to load more ({filtered.length - displayed.length} remaining)...
          </div>
        )}
      </div>
    </div>
  );
}
