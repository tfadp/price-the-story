'use client';
import { useState, useCallback, useEffect, useRef } from 'react';
import type { AnalysisState, AnalyzeRequest } from '@/types/api';
import { analyzeTickerStream } from '@/lib/api';

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({ status: 'idle' });
  const [lastHeartbeat, setLastHeartbeat] = useState<number>(0);
  // Holds the cancel function for the currently active SSE stream
  const cancelRef = useRef<(() => void) | null>(null);

  const run = useCallback((request: AnalyzeRequest) => {
    // Cancel any stream still running from a previous call
    cancelRef.current?.();
    cancelRef.current = null;

    setState({ status: 'loading', stage: 'Starting analysis...', progress_pct: 0 });

    cancelRef.current = analyzeTickerStream(
      request,
      (progress) => {
        setState({
          status: 'loading',
          stage: progress.stage,
          progress_pct: progress.progress_pct,
        });
      },
      (result) => {
        cancelRef.current = null;
        setState({ status: 'success', data: result });
      },
      (message) => {
        cancelRef.current = null;
        setState({ status: 'error', message });
      },
      () => {
        // heartbeat — update timestamp so ProgressRail knows we're alive
        setLastHeartbeat(Date.now());
      },
    );
  }, []);

  const reset = useCallback(() => {
    // Close any active SSE stream before clearing state
    cancelRef.current?.();
    cancelRef.current = null;
    setState({ status: 'idle' });
    setLastHeartbeat(0);
  }, []);

  useEffect(() => {
    return () => {
      cancelRef.current?.();
      cancelRef.current = null;
    };
  }, []);

  return { state, run, reset, lastHeartbeat };
}
