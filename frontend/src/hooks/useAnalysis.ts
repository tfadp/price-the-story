'use client';
import { useState, useCallback } from 'react';
import type { AnalysisState, AnalyzeRequest } from '@/types/api';
import { analyzeTickerStream } from '@/lib/api';

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({ status: 'idle' });

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
    );
  }, []);

  const reset = useCallback(() => {
    setState({ status: 'idle' });
  }, []);

  return { state, run, reset };
}
