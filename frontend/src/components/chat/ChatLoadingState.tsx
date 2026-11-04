import React from 'react';
import { Loader2 } from 'lucide-react';

export const ChatLoadingState: React.FC = () => (
  <div className="flex gap-3 py-3" role="status" aria-live="polite">
    <div className="bg-[#ffffff] border border-[#ebebeb] rounded-[6px] p-4 text-[#737373] text-xs font-mono shadow-[0_1px_2px_rgba(0,0,0,0.02)] flex items-center gap-2.5">
      <Loader2 className="w-4 h-4 animate-spin text-[#171717]" aria-hidden="true" />
      <div>
        <div className="text-[10px] tracking-wide text-[#171717] mb-0.5">
          SUNSET TRACKER ORCHESTRATOR
        </div>
        <span>
          The LLM is warming up. It may take a little while to answer the first
          query.
        </span>
      </div>
    </div>
  </div>
);
