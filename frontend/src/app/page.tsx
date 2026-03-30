'use client';
import { useState } from 'react';
import InputForm from '@/components/InputForm';
import ProgressRail from '@/components/ProgressRail';
import VerdictCard from '@/components/VerdictCard';
import DetailPanels from '@/components/DetailPanels';
import PredictionsTab from '@/components/PredictionsTab';
import { useAnalysis } from '@/hooks/useAnalysis';
import type { AnalyzeRequest } from '@/types/api';

type Tab = 'analysis' | 'predictions';

export default function Home() {
  const { state, run, reset, lastHeartbeat } = useAnalysis();
  const [lastRequest, setLastRequest] = useState<AnalyzeRequest | null>(null);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('analysis');

  function handleSubmit(req: AnalyzeRequest) {
    setLastRequest(req);
    setStartTime(Date.now());
    run(req);
  }

  function handleReset() {
    reset();
    setStartTime(null);
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white">Price the Story</h1>
            <p className="text-xs text-gray-500">Long-horizon equity research</p>
          </div>
          <div className="flex items-center gap-4">
            {/* Tab switcher */}
            <nav className="flex gap-1 bg-gray-900 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('analysis')}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  activeTab === 'analysis'
                    ? 'bg-gray-700 text-white font-medium'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                Analysis
              </button>
              <button
                onClick={() => setActiveTab('predictions')}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  activeTab === 'predictions'
                    ? 'bg-gray-700 text-white font-medium'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                My Predictions
              </button>
            </nav>
            {activeTab === 'analysis' && state.status !== 'idle' && (
              <button
                onClick={handleReset}
                className="text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← New analysis
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-12 flex flex-col items-center gap-10">

        {/* Idle state — show the pitch + input form */}
        {state.status === 'idle' && activeTab === 'analysis' && (
          <div className="flex flex-col items-center gap-8 w-full">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-white mb-3">
                What&apos;s the story worth?
              </h2>
              <p className="text-gray-400 max-w-lg text-sm leading-relaxed">
                Enter a ticker, your target return, and a holding period.
                Get a confidence assessment in under 90 seconds — not a data dump.
              </p>
            </div>
            <InputForm onSubmit={handleSubmit} disabled={false} />
          </div>
        )}

        {/* Loading state — progress rail */}
        {state.status === 'loading' && activeTab === 'analysis' && (
          <div className="flex flex-col items-center gap-8 w-full">
            <div className="text-center">
              <h2 className="text-xl font-semibold text-white mb-1">
                Analyzing {lastRequest?.ticker}
              </h2>
              <p className="text-gray-500 text-sm">
                Pulling data from multiple sources — this takes about 60–90 seconds
              </p>
            </div>
            <ProgressRail
              stage={state.stage ?? ''}
              progress_pct={state.progress_pct ?? 0}
              startTime={startTime}
              lastHeartbeat={lastHeartbeat}
            />
          </div>
        )}

        {/* Error state */}
        {state.status === 'error' && activeTab === 'analysis' && (
          <div className="flex flex-col items-center gap-6 w-full">
            <div className="bg-red-950 border border-red-800 rounded-xl p-6 max-w-md w-full text-center">
              <p className="text-red-300 font-medium mb-2">Analysis didn&apos;t complete</p>
              <p className="text-red-400 text-sm mb-4">{state.message}</p>
              <div className="text-left text-xs text-gray-500 space-y-1">
                <p>Things to check:</p>
                <p>· Is the ticker a US stock? (e.g. AAPL, MSFT, NVDA)</p>
                <p>· Is the backend running?
                  <code className="bg-gray-900 px-1 rounded ml-1">
                    uvicorn app.main:app --port 8000
                  </code>
                </p>
                <p>· Are your API keys set in <code className="bg-gray-900 px-1 rounded">backend/.env</code>?</p>
              </div>
            </div>
            <InputForm onSubmit={handleSubmit} disabled={false} />
          </div>
        )}

        {/* Success state — verdict card + detail panels */}
        {state.status === 'success' && activeTab === 'analysis' && (
          <div className="flex flex-col items-center gap-4 w-full">
            <VerdictCard
              data={state.data}
              targetCagr={lastRequest?.target_cagr ?? 0.10}
              holdingPeriod={lastRequest?.horizons?.includes(5) ? 5 : lastRequest?.horizons?.[1] ?? 5}
            />
            <DetailPanels data={state.data} />
          </div>
        )}

        {/* Predictions tab */}
        {activeTab === 'predictions' && (
          <div className="w-full">
            <PredictionsTab />
          </div>
        )}

      </div>
    </main>
  );
}
