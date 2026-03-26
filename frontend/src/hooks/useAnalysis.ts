'use client';
import { useState, useCallback } from 'react';
import type { AnalysisState, AnalyzeRequest } from '@/types/api';
import { analyzeTickerStream } from '@/lib/api';

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({ status: 'idle' });
  const [lastHeartbeat, setLastHeartbeat] = useState<number>(0);

  const run = useCallback((request: AnalyzeRequest) => {
    setState({ status: 'loading', stage: 'Starting analysis...', progress_pct: 0 });

    analyzeTickerStream(
      request,
      (progress) => {
        setState({
          status: 'loading',
          stage: progress.stage,
          progress_pct: progress.progress_pct,
        });
      },
      (result) => {
        setState({ status: 'success', data: result });
      },
      (message) => {
        setState({ status: 'error', message });
      },
      () => {
        // heartbeat — update timestamp so ProgressRail knows we're alive
        setLastHeartbeat(Date.now());
      },
    );
  }, []);

  const reset = useCallback(() => {
    setState({ status: 'idle' });
    setLastHeartbeat(0);
  }, []);

  return { state, run, reset, lastHeartbeat };
}
