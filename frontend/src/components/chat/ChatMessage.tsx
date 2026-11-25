import React, { useState } from 'react';
import { Clock, FileCheck2, ChevronDown, ChevronUp, ChevronRight, BrainCircuit } from 'lucide-react';
import { ChatMessage as ChatMessageType } from '../../types/chat';
import { SourceEvidenceCard } from './SourceEvidenceCard';

interface ChatMessageProps {
  message: ChatMessageType;
  onToggleThinking: (id: string) => void;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, onToggleThinking }) => {
  const isUser = message.role === 'user';
  const [showEvidence, setShowEvidence] = useState<boolean>(true);

  // Markdown renderer respecting Vercel typography tokens
  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      if (line.startsWith('### ')) {
        return (
          <h3 key={idx} className="text-sm font-semibold text-[#171717] tracking-tight mt-3 mb-1.5 flex items-center gap-1.5">
            <span className="text-[#a3a3a3] font-mono text-xs">#</span>
            {line.replace('### ', '')}
          </h3>
        );
      }
      if (line.startsWith('## ')) {
        return (
          <h2 key={idx} className="text-base font-semibold text-[#171717] tracking-tight mt-3.5 mb-1.5">
            {line.replace('## ', '')}
          </h2>
        );
      }
      if (line.startsWith('* ') || line.startsWith('- ')) {
        return (
          <li key={idx} className="ml-4 list-disc text-[#333333] my-1 leading-relaxed text-sm">
            {formatInlineText(line.substring(2))}
          </li>
        );
      }
      if (/^\d+\.\s/.test(line)) {
        const itemText = line.replace(/^\d+\.\s/, '');
        return (
          <div key={idx} className="ml-2 my-1.5 text-[#333333] text-sm leading-relaxed flex gap-2">
            <span className="font-mono text-[#737373] text-xs font-semibold">{line.match(/^\d+\./)?.[0]}</span>
            <div>{formatInlineText(itemText)}</div>
          </div>
        );
      }
      if (line.trim() === '') {
        return <div key={idx} className="h-2" />;
      }
      return (
        <p key={idx} className="leading-relaxed text-[#333333] text-sm my-1 font-sans">
          {formatInlineText(line)}
        </p>
      );
    });
  };

  const formatInlineText = (text: string) => {
    const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={i} className="px-1.5 py-0.5 bg-[#f5f5f5] text-[#171717] border border-[#ebebeb] rounded-[3px] font-mono text-[12px]">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} className="text-[#171717] font-semibold">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div className={`flex gap-3 py-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[88%] rounded-[6px] p-4 transition-all ${
          isUser
            ? 'bg-[#171717] text-[#ffffff] shadow-[0_1px_2px_rgba(0,0,0,0.06)]'
            : 'bg-[#ffffff] border border-[#ebebeb] text-[#171717] shadow-[0_1px_3px_rgba(0,0,0,0.02)]'
        }`}
      >
        {/* Message metadata bar */}
        <div
          className={`flex items-center justify-between gap-4 mb-1.5 pb-1 border-b text-[11px] font-mono ${
            isUser ? 'border-[#333333] text-[#a3a3a3]' : 'border-[#f5f5f5] text-[#737373]'
          }`}
        >
          <span className="font-medium tracking-wide flex items-center gap-1.5">
            {!isUser && <span className="text-[#000000] font-sans font-bold text-xs">▲</span>}
            {isUser ? 'DEVELOPER INQUIRY' : 'SUNSET TRACKER ORCHESTRATOR'}
          </span>
          <div className="flex items-center gap-2.5">
            {message.executionTimeMs && (
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3 text-[#a3a3a3]" />
                {message.executionTimeMs}ms
              </span>
            )}
            <span>{message.timestamp}</span>
          </div>
        </div>

        {/* Thinking process (collapsible) */}
        {!isUser && message.thinking && (
          <div className="mt-2 text-xs">
            <button
              type="button"
              onClick={() => onToggleThinking(message.id)}
              className="flex cursor-pointer select-none items-center gap-1.5 font-medium text-[#737373] transition-colors hover:text-[#171717]"
              title={message.isThinkingOpen ? 'Collapse thought process' : 'Expand thought process'}
            >
              {message.isThinkingOpen ? (
                <ChevronDown className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 shrink-0" />
              )}
              <BrainCircuit className="h-3.5 w-3.5 shrink-0" />
              {message.status === 'streaming' && !message.content ? 'Thinking...' : 'Thought process'}
            </button>

            {message.isThinkingOpen && (
              <div className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap border-l-2 border-[#d4d4d4] pl-3 leading-relaxed text-[#737373]">
                {message.thinking}
              </div>
            )}
          </div>
        )}

        {/* Content */}
        {(message.content || isUser || !message.thinking) && (
          <div className="text-sm font-sans">
            {isUser ? (
              <p className="leading-relaxed whitespace-pre-wrap text-sm text-[#f5f5f5] font-sans">{message.content}</p>
            ) : (
              renderFormattedContent(message.content)
            )}
          </div>
        )}

        {/* Source Code Evidence Section (Wolfgang's requirement) */}
        {!isUser && message.evidence && message.evidence.length > 0 && (
          <div className="mt-4 pt-3 border-t border-[#f0f0f0]">
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="flex items-center justify-between w-full text-xs font-mono font-medium text-[#171717] hover:text-[#000000] py-1 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <FileCheck2 className="w-3.5 h-3.5 text-[#297a3a]" />
                <span className="uppercase tracking-wider">
                  Verified AST Evidence ({message.evidence.length} trace points)
                </span>
              </div>
              {showEvidence ? <ChevronUp className="w-3.5 h-3.5 text-[#737373]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#737373]" />}
            </button>

            {showEvidence && (
              <div className="mt-2.5 space-y-2">
                {message.evidence.map((ev) => (
                  <SourceEvidenceCard key={ev.id} evidence={ev} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
