import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { ChatInterface } from './components/chat/ChatInterface';
import { ViewsInterface } from './components/views/ViewsInterface';
import { checkBackendHealth, HealthStatus } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'views'>('chat');
  const [selectedStep, setSelectedStep] = useState<string>('step-06');
  const [health, setHealth] = useState<HealthStatus>({
    backendAvailable: false,
    mcpAvailable: false,
    graphAvailable: false,
    message: 'Checking connection...'
  });

  const refreshHealth = async () => {
    const status = await checkBackendHealth();
    setHealth(status);
  };

  useEffect(() => {
    let isMounted = true;
    checkBackendHealth().then((status) => {
      if (isMounted) {
        setHealth(status);
      }
    });

    const interval = setInterval(() => {
      checkBackendHealth().then((status) => {
        if (isMounted) {
          setHealth(status);
        }
      });
    }, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#fafafa] text-[#171717] flex flex-col font-sans">
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        selectedStep={selectedStep}
        onStepChange={setSelectedStep}
        health={health}
        onRefreshHealth={refreshHealth}
      />

      <main className="flex-1 px-4 sm:px-6 py-5 flex flex-col justify-center">
        {activeTab === 'chat' ? (
          <ChatInterface selectedStep={selectedStep} />
        ) : (
          <ViewsInterface />
        )}
      </main>

      {/* Vercel minimalist footer */}
      <footer className="py-3 px-6 border-t border-[#ebebeb] bg-[#ffffff] text-[11px] font-mono text-[#8f8f8f] flex flex-wrap items-center justify-between gap-2 max-w-7xl mx-auto w-full">
        <span>AMOS Winter Semester 2026/27 · Project 1 (iteratec) · SunsetTracker</span>
        <span>Deterministic Code Ingestion · AST Traceability · Neo4j & PostgreSQL 17</span>
      </footer>
    </div>
  );
};

export default App;
