import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Loader2, AlertCircle, Square } from 'lucide-react';
import { ChatMessage as ChatMessageType } from '../../types/chat';
import { ChatMessage } from './ChatMessage';
import { SuggestedQueries } from './SuggestedQueries';
import { submitMigrationQuery } from '../../services/api';
import { INITIAL_SUGGESTIONS } from '../../services/mockData';

interface ChatInterfaceProps {
  selectedStep: string;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ selectedStep }) => {
  const [messages, setMessages] = useState<ChatMessageType[]>([
    {
      id: 'welcome-1',
      role: 'assistant',
      content: `Welcome to **SunsetTracker** · Legacy Migration Knowledge Base.\n\nThis system indexes deterministic code facts across **legacy-example-monolith** and target repositories without running untrusted code. Every analysis answer connects directly to GitHub AST observations, commit provenance, and coupling boundaries.\n\nSelect a verified inquiry below or submit a custom question.`,
      timestamp: 'Just now',
      suggestedNextQueries: INITIAL_SUGGESTIONS
    }
  ]);
  const [input, setInput] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText || input).trim();
    if (!textToSend || isLoading) return;

    setError(null);
    setInput('');

    const userMessage: ChatMessageType = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const assistantId = `asst-${Date.now()}`;
    const streamingMessage: ChatMessageType = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'streaming',
    };

    setMessages((prev) => [...prev, userMessage, streamingMessage]);
    setIsLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await submitMigrationQuery(
        { query: textToSend, stepId: selectedStep },
        {
          onDelta: (text) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + text } : m
              )
            );
          },
          onSources: () => {
            // Sources arrive before content; evidence is attached on completion.
          },
        },
        controller.signal,
      );

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: response.answer,
                evidence: response.evidence,
                executionTimeMs: response.executionTimeMs,
                suggestedNextQueries: response.suggestedNextQueries,
                status: 'done',
              }
            : m
        )
      );
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled: keep the partial answer, mark as done.
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, status: 'done' } : m))
        );
      } else {
        const msg = err instanceof Error ? err.message : 'Query execution failed';
        setError(msg);
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      }
    } finally {
      abortControllerRef.current = null;
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: 'assistant',
        content: `Session reset for milestone **${selectedStep}**. What migration question would you like to investigate?`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        suggestedNextQueries: INITIAL_SUGGESTIONS
      }
    ]);
    setError(null);
  };

  const latestSuggestions = messages[messages.length - 1]?.suggestedNextQueries || INITIAL_SUGGESTIONS;

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto w-full bg-[#ffffff] border border-[#ebebeb] rounded-[6px] shadow-[0_1px_3px_rgba(0,0,0,0.03)] overflow-hidden">
      {/* Session Breadcrumb Header */}
      <div className="flex items-center justify-between px-5 py-2.5 border-b border-[#ebebeb] bg-[#fafafa]">
        <div className="flex items-center gap-2 text-xs font-mono text-[#737373]">
          <span className="text-[#171717] font-semibold">sunset-tracker</span>
          <span>/</span>
          <span>query-session</span>
          <span>/</span>
          <span className="text-[#0969da] font-medium bg-[#eff6ff] border border-[#bfdbfe] px-1.5 py-0.5 rounded-[3px]">
            {selectedStep}
          </span>
        </div>

        <button
          onClick={clearChat}
          title="Reset session history"
          className="flex items-center gap-1.5 text-xs font-mono text-[#737373] hover:text-[#171717] px-2 py-1 rounded-[4px] hover:bg-[#ebebeb] transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Reset Session</span>
        </button>
      </div>

      {/* Messages Scroll Container */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2 bg-[#fafafa]">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {isLoading && messages[messages.length - 1]?.content === '' && (
          <div className="flex gap-3 py-3">
            <div className="bg-[#ffffff] border border-[#ebebeb] rounded-[6px] p-4 text-[#737373] text-xs font-mono shadow-[0_1px_2px_rgba(0,0,0,0.02)] flex items-center gap-2.5">
              <Loader2 className="w-4 h-4 animate-spin text-[#171717]" />
              <span>Waiting for the LLM to start answering...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2.5 p-3 bg-[#fef2f2] border border-[#fecaca] rounded-[6px] text-xs font-mono text-[#991b1b] my-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-[#dc2626]" />
            <span>{error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Docked Query Input Area */}
      <div className="p-4 border-t border-[#ebebeb] bg-[#ffffff] space-y-3">
        <SuggestedQueries
          queries={latestSuggestions}
          onSelect={(q) => handleSend(q)}
          disabled={isLoading}
        />

        <div className="border border-[#ebebeb] focus-within:border-[#171717] focus-within:ring-1 focus-within:ring-[#171717] rounded-[6px] p-2 bg-[#ffffff] transition-all shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about legacy decommissioning, target service implementation, or database table coupling..."
            className="w-full bg-transparent px-2 py-1 text-sm text-[#171717] placeholder:text-[#a3a3a3] outline-none resize-none min-h-[44px] max-h-32 font-sans"
          />

          <div className="flex items-center justify-between pt-1 border-t border-[#f5f5f5] px-1">
            <div className="flex items-center gap-2 text-[11px] font-mono text-[#8f8f8f]">
              <span><kbd className="bg-[#f5f5f5] border border-[#ebebeb] px-1 py-0.5 rounded-[3px] text-[#4d4d4d]">Enter</kbd> to query</span>
              <span>·</span>
              <span><kbd className="bg-[#f5f5f5] border border-[#ebebeb] px-1 py-0.5 rounded-[3px] text-[#4d4d4d]">Shift+Enter</kbd> new line</span>
            </div>

            <button
              onClick={() => (isLoading ? handleStop() : handleSend())}
              disabled={!isLoading && !input.trim()}
              className={`h-8 px-4 font-medium text-xs font-sans rounded-[6px] flex items-center justify-center gap-1.5 transition-all disabled:opacity-30 disabled:cursor-not-allowed shrink-0 ${
                isLoading
                  ? 'bg-[#dc2626] hover:bg-[#b91c1c] text-[#ffffff]'
                  : 'bg-[#171717] hover:bg-[#333333] text-[#ffffff]'
              }`}
            >
              {isLoading ? (
                <>
                  <Square className="w-3 h-3 text-[#ffffff]" />
                  <span>Stop</span>
                </>
              ) : (
                <>
                  <Send className="w-3 h-3 text-[#ffffff]" />
                  <span>Query Graph</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
