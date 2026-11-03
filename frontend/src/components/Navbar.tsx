import React from 'react';
import { Terminal, Layers, RefreshCw, GitBranch, GitCompare } from 'lucide-react';
import { HealthStatus } from '../services/api';

interface NavbarProps {
  activeTab: 'chat' | 'views' | 'diff';
  onTabChange: (tab: 'chat' | 'views' | 'diff') => void;
  selectedStep: string;
  onStepChange: (step: string) => void;
  health: HealthStatus;
  onRefreshHealth: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  selectedStep,
  onStepChange,
  health,
  onRefreshHealth,
}) => {
  return (
    <header className="sticky top-0 z-50 border-b border-[#ebebeb] bg-[#fafafa]/90 backdrop-blur-md px-6 py-2.5">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-[6px] bg-[#171717] flex items-center justify-center text-[#ffffff] shadow-[0_1px_2px_rgba(0,0,0,0.1)]">
            <span className="font-bold text-xs select-none">▲</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-[#171717] tracking-tight">SunsetTracker</span>
            <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-[3px] bg-[#f5f5f5] text-[#525252] border border-[#ebebeb]">
              v0.1.0-alpha
            </span>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 bg-[#ebebeb] p-0.5 rounded-[6px]">
          <button
            onClick={() => onTabChange('chat')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-[5px] text-xs font-mono transition-all ${
              activeTab === 'chat'
                ? 'bg-[#ffffff] text-[#171717] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.06)]'
                : 'text-[#737373] hover:text-[#171717]'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Query Terminal</span>
          </button>

          <button
            onClick={() => onTabChange('diff')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-[5px] text-xs font-mono transition-all ${
              activeTab === 'diff'
                ? 'bg-[#ffffff] text-[#171717] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.06)]'
                : 'text-[#737373] hover:text-[#171717]'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Git Comparisons</span>
          </button>

          <button
            onClick={() => onTabChange('views')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-[5px] text-xs font-mono transition-all ${
              activeTab === 'views'
                ? 'bg-[#ffffff] text-[#171717] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.06)]'
                : 'text-[#737373] hover:text-[#171717]'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>arc42 Architecture Views</span>
          </button>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-2.5">
          {/* Step Selector */}
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <span className="text-[#a3a3a3] text-[11px] hidden sm:inline">Milestone:</span>
            <select
              value={selectedStep}
              onChange={(e) => onStepChange(e.target.value)}
              className="bg-[#ffffff] text-[#171717] border border-[#ebebeb] rounded-[5px] px-2 py-1 text-xs focus:ring-1 focus:ring-[#171717] outline-none font-mono"
            >
              <option value="step-06">step-06 (Catalog Migrated)</option>
              <option value="step-05">step-05 (Catalog Strangler Ingress)</option>
              <option value="step-01">step-01 (Legacy Monolith Baseline)</option>
            </select>
          </div>

          {/* Connection Status Indicator */}
          <button
            onClick={onRefreshHealth}
            title={`${health.message} - Click to re-verify`}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-[5px] bg-[#ffffff] border border-[#ebebeb] text-[11px] font-mono text-[#525252] hover:border-[#171717] transition-colors"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${health.backendAvailable ? 'bg-[#059669]' : 'bg-[#d97706]'}`}></span>
            <span>{health.backendAvailable ? 'API Online' : 'Mock Mode'}</span>
            {health.backendAvailable && health.model !== 'none' && (
              <span className="text-[#a3a3a3] hidden md:inline">· {health.model}</span>
            )}
            <RefreshCw className="w-3 h-3 text-[#a3a3a3] hover:text-[#171717]" />
          </button>

          {/* GitHub Repo */}
          <a
            href="https://github.com/amosproj/amos2026ws01-legacy-migrator"
            target="_blank"
            rel="noopener noreferrer"
            title="Open Repository on GitHub"
            className="flex items-center gap-1 px-2 py-1 text-[#737373] hover:text-[#171717] bg-[#ffffff] border border-[#ebebeb] hover:border-[#171717] rounded-[5px] text-xs font-mono transition-colors"
          >
            <GitBranch className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">amosproj</span>
          </a>
        </div>
      </div>
    </header>
  );
};
