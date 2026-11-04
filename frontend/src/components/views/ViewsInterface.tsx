import React, { useState, useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import { Layers, Network, Server, RefreshCw, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';
import { Arc42ViewType } from '../../types/arc42';
import { MOCK_ARC42_VIEWS } from '../../services/mockData';

// Initialize mermaid with Vercel light theme tokens
mermaid.initialize({
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  themeVariables: {
    darkMode: false,
    background: '#ffffff',
    primaryColor: '#fafafa',
    primaryTextColor: '#171717',
    primaryBorderColor: '#ebebeb',
    lineColor: '#737373',
    secondaryColor: '#f5f5f5',
    tertiaryColor: '#ffffff',
    fontFamily: 'Geist, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontSize: '13px',
  },
});

export const ViewsInterface: React.FC = () => {
  const [selectedView, setSelectedView] = useState<Arc42ViewType>('building_block');
  const [zoom, setZoom] = useState<number>(1);
  const [svgContent, setSvgContent] = useState<string>('');
  const [isRendering, setIsRendering] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const currentViewMeta = MOCK_ARC42_VIEWS.find((v) => v.id === selectedView) || MOCK_ARC42_VIEWS[0];

  useEffect(() => {
    let isCancelled = false;
    const renderDiagram = async () => {
      setIsRendering(true);
      try {
        const id = `mermaid-svg-${Date.now()}`;
        const { svg } = await mermaid.render(id, currentViewMeta.mermaidSource);
        if (!isCancelled) {
          setSvgContent(svg);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
      } finally {
        if (!isCancelled) {
          setIsRendering(false);
        }
      }
    };

    renderDiagram();
    return () => {
      isCancelled = true;
    };
  }, [selectedView, currentViewMeta]);

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-6xl mx-auto w-full bg-[#ffffff] border border-[#ebebeb] rounded-[6px] shadow-[0_1px_3px_rgba(0,0,0,0.03)] overflow-hidden">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between px-5 py-2.5 border-b border-[#ebebeb] bg-[#fafafa] gap-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#171717]" />
          <span className="text-xs font-mono uppercase tracking-wider font-semibold text-[#171717]">
            arc42 Architecture Visualizer
          </span>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-1 bg-[#ebebeb] p-0.5 rounded-[6px]">
          <button
            onClick={() => setSelectedView('context')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-[5px] text-xs font-mono transition-all ${
              selectedView === 'context'
                ? 'bg-[#ffffff] text-[#171717] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.05)]'
                : 'text-[#737373] hover:text-[#171717]'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Context (3.0)</span>
          </button>

          <button
            onClick={() => setSelectedView('building_block')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-[5px] text-xs font-mono transition-all ${
              selectedView === 'building_block'
                ? 'bg-[#ffffff] text-[#171717] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.05)]'
                : 'text-[#737373] hover:text-[#171717]'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Building Block (5.0)</span>
          </button>

          <button
            onClick={() => setSelectedView('deployment')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-[5px] text-xs font-mono transition-all ${
              selectedView === 'deployment'
                ? 'bg-[#ffffff] text-[#171717] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.05)]'
                : 'text-[#737373] hover:text-[#171717]'
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            <span>Deployment (7.0)</span>
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom((prev) => Math.min(prev + 0.15, 2.5))}
            title="Zoom In"
            className="p-1.5 text-[#737373] hover:text-[#171717] hover:bg-[#ebebeb] rounded-[4px] transition-colors"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoom((prev) => Math.max(prev - 0.15, 0.5))}
            title="Zoom Out"
            className="p-1.5 text-[#737373] hover:text-[#171717] hover:bg-[#ebebeb] rounded-[4px] transition-colors"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoom(1)}
            title="Reset Zoom"
            className="p-1.5 text-[#737373] hover:text-[#171717] hover:bg-[#ebebeb] rounded-[4px] transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Subheader description & legend */}
      <div className="px-5 py-2.5 bg-[#ffffff] border-b border-[#ebebeb] flex items-center justify-between text-xs text-[#737373]">
        <div>
          <span className="font-mono text-[#171717] font-medium">{currentViewMeta.section}:</span>{' '}
          <span className="text-[#4d4d4d]">{currentViewMeta.description}</span>
        </div>

        {/* Status Legend */}
        {selectedView === 'building_block' && (
          <div className="hidden md:flex items-center gap-3 text-[11px] font-mono">
            <span className="flex items-center gap-1.5 text-[#991b1b]">
              <span className="w-2 h-2 rounded-full bg-[#dc2626]"></span>
              <span>Decommissioned</span>
            </span>
            <span className="flex items-center gap-1.5 text-[#525252]">
              <span className="w-2 h-2 rounded-full bg-[#737373]"></span>
              <span>Legacy Active</span>
            </span>
            <span className="flex items-center gap-1.5 text-[#92400e]">
              <span className="w-2 h-2 rounded-full bg-[#d97706]"></span>
              <span>Coupled</span>
            </span>
            <span className="flex items-center gap-1.5 text-[#065f46]">
              <span className="w-2 h-2 rounded-full bg-[#059669]"></span>
              <span>Migrated</span>
            </span>
          </div>
        )}
      </div>

      {/* Diagram Canvas */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-6 flex items-center justify-center bg-[#fafafa] relative"
      >
        {isRendering ? (
          <div className="flex items-center gap-2 text-[#737373] text-xs font-mono">
            <RefreshCw className="w-4 h-4 animate-spin text-[#171717]" />
            <span>Compiling arc42 SVG model...</span>
          </div>
        ) : (
          <div
            className="transition-transform duration-150 origin-center max-w-full bg-[#ffffff] p-6 rounded-[6px] border border-[#ebebeb] shadow-[0_1px_3px_rgba(0,0,0,0.03)]"
            style={{ transform: `scale(${zoom})` }}
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        )}
      </div>
    </div>
  );
};
