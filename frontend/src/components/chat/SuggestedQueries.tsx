import React, { useState } from 'react';
import { Terminal, X, ChevronDown, ChevronRight } from 'lucide-react';

interface SuggestedQueriesProps {
  queries: string[];
  onSelect: (query: string) => void;
  disabled?: boolean;
}

export const SuggestedQueries: React.FC<SuggestedQueriesProps> = ({ queries, onSelect, disabled = false }) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [isClosed, setIsClosed] = useState<boolean>(false);

  if (!queries || queries.length === 0 || isClosed) return null;

  return (
    <div className="flex flex-col gap-2 pt-1">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          title={isOpen ? 'Collapse suggestions' : 'Expand suggestions'}
          className="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-[#737373] hover:text-[#171717] transition-colors cursor-pointer select-none"
        >
          {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          <Terminal className="w-3.5 h-3.5 text-[#171717]" />
          <span>Suggested queries</span>
        </button>
        <button
          type="button"
          onClick={() => setIsClosed(true)}
          title="Close suggestions"
          className="text-[#a3a3a3] hover:text-[#171717] transition-colors cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      {isOpen && (
        <div className="flex flex-wrap gap-2">
          {queries.map((q, idx) => (
            <button
              key={idx}
              disabled={disabled}
              onClick={() => onSelect(q)}
              className="text-left text-xs bg-[#ffffff] hover:bg-[#fafafa] text-[#4d4d4d] hover:text-[#171717] border border-[#ebebeb] hover:border-[#171717] px-3 py-1.5 rounded-full transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_1px_2px_rgba(0,0,0,0.02)] flex items-center gap-1.5 group"
            >
              <span className="text-[#a3a3a3] group-hover:text-[#171717] font-mono text-[11px]">›</span>
              <span>{q}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
