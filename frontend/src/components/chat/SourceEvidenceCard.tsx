import React, { useState } from 'react';
import { ExternalLink, GitCommit, FileCode, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { SourceEvidence } from '../../types/chat';
import { StatusBadge } from '../common/StatusBadge';

interface SourceEvidenceCardProps {
  evidence: SourceEvidence;
}

export const SourceEvidenceCard: React.FC<SourceEvidenceCardProps> = ({ evidence }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [copied, setCopied] = useState<boolean>(false);

  const directGithubUrl = `${evidence.repoUrl}/blob/${evidence.commitSha}/${evidence.filePath}${
    evidence.startLine ? `#L${evidence.startLine}${evidence.endLine ? `-L${evidence.endLine}` : ''}` : ''
  }`;

  const copyPath = () => {
    navigator.clipboard.writeText(`${evidence.filePath}:${evidence.startLine || 1}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-[#ebebeb] bg-[#ffffff] rounded-[6px] overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all hover:border-[#d4d4d4]">
      {/* Header bar */}
      <div className="px-3.5 py-2.5 bg-[#fafafa] flex flex-wrap items-center justify-between gap-2 border-b border-[#ebebeb]">
        <div className="flex items-center gap-2 min-w-0">
          <FileCode className="w-4 h-4 text-[#737373] shrink-0" />
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1.5 font-mono text-xs text-[#171717] hover:text-[#000000] font-medium truncate text-left"
            title={evidence.filePath}
          >
            {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-[#a3a3a3]" /> : <ChevronRight className="w-3.5 h-3.5 text-[#a3a3a3]" />}
            <span className="truncate">{evidence.filePath}</span>
            {evidence.startLine && (
              <span className="text-[#0969da] font-mono font-semibold shrink-0">
                :L{evidence.startLine}{evidence.endLine ? `-L${evidence.endLine}` : ''}
              </span>
            )}
          </button>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <StatusBadge status={evidence.status} size="sm" />
          <button
            onClick={copyPath}
            title="Copy path and line"
            className="p-1 text-[#737373] hover:text-[#171717] hover:bg-[#ebebeb] rounded-[4px] transition-colors"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#059669]" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          <a
            href={directGithubUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="Open on GitHub"
            className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-[#171717] hover:bg-[#171717] hover:text-[#ffffff] px-2 py-0.5 rounded-[4px] border border-[#d4d4d4] transition-colors"
          >
            <span>GitHub</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* Content description & metadata */}
      <div className="p-3.5 text-xs space-y-2.5">
        <p className="text-[#4d4d4d] leading-relaxed font-sans">{evidence.description}</p>

        <div className="flex items-center gap-3 text-[11px] font-mono text-[#737373] pt-0.5 border-t border-[#f5f5f5]">
          <span className="inline-flex items-center gap-1">
            <span className="text-[#a3a3a3]">Repo:</span>
            <code className="text-[#171717] bg-[#f5f5f5] border border-[#ebebeb] px-1.5 py-0.5 rounded-[3px]">
              {evidence.repoId}
            </code>
          </span>
          <span className="inline-flex items-center gap-1">
            <GitCommit className="w-3 h-3 text-[#a3a3a3]" />
            <span className="text-[#171717]">{evidence.commitSha.slice(0, 8)}</span>
          </span>
        </div>

        {/* Terminal code snippet */}
        {isExpanded && evidence.snippet && (
          <div className="mt-2 pt-1">
            <pre className="p-3 bg-[#0a0a0a] text-[#f5f5f5] rounded-[4px] border border-[#262626] font-mono text-[11px] leading-relaxed overflow-x-auto">
              <code>{evidence.snippet}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
