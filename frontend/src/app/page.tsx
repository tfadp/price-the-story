'use client';
import { useState } from 'react';
import InputForm from '@/components/InputForm';
import ProgressRail from '@/components/ProgressRail';
import VerdictCard from '@/components/VerdictCard';
import DetailPanels from '@/components/DetailPanels';
import { useAnalysis } from '@/hooks/useAnalysis';
import type { AnalyzeRequest } from '@/types/api';

export default function Home() {
  const { state, run, reset } = useAnalysis();
  const [lastRequest, setLastRequest] = useState<AnalyzeRequest | null>(null);

  function handleSubmit(req: AnalyzeRequest) {
    setLastRequest(req);
    run(req);
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
          {state.status !== 'idle' && (
            <button
              onClick={reset}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              ← New analysis
            </button>
          )}
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-12 flex flex-col items-center gap-10">

        {/* Idle state — show the pitch + input form */}
        {state.status === 'idle' && (
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
        {state.status === 'loading' && (
          <div className="flex flex-col items-center gap-8 w-full">
            <div className="text-center">
              <h2 className="text-xl font-semibold text-white mb-1">
                Analyzing {lastRequest?.ticker}
              </h2>
              <p className="text-gray-500 text-sm">
                {(lastRequest?.target_cagr ?? 0.10) * 100}% target · {lastRequest?.horizons?.includes(5) ? 5 : lastRequest?.horizons?.[1] ?? 5}yr horizon
              </p>
            </div>
            <ProgressRail stage={state.stage} progress_pct={state.progress_pct} />
          </div>
        )}

        {/* Error state */}
        {state.status === 'error' && (
          <div className="flex flex-col items-center gap-6 w-full">
            <div className="bg-red-950 border border-red-800 rounded-xl p-6 max-w-md w-full text-center">
              <p className="text-red-300 font-medium mb-2">Analysis failed</p>
              <p className="text-red-400 text-sm">{state.message}</p>
              <p className="text-gray-500 text-xs mt-3">
                Make sure the backend is running: <code className="bg-gray-900 px-1 rounded">uvicorn app.main:app --port 8000</code>
              </p>
            </div>
            <InputForm onSubmit={handleSubmit} disabled={false} />
          </div>
        )}

        {/* Success state — verdict card + detail panels */}
        {state.status === 'success' && (
          <div className="flex flex-col items-center gap-4 w-full">
            <VerdictCard
              data={state.data}
              targetCagr={lastRequest?.target_cagr ?? 0.10}
              holdingPeriod={lastRequest?.horizons?.includes(5) ? 5 : lastRequest?.horizons?.[1] ?? 5}
            />
            <DetailPanels data={state.data} />
          </div>
        )}

      </div>
    </main>
  );
}
