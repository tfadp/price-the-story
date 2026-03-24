const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function analyzeTickerStream(
  request: import('@/types/api').AnalyzeRequest,
  onProgress: (event: import('@/types/api').ProgressEvent) => void,
  onComplete: (result: import('@/types/api').AnalyzeResponse) => void,
  onError: (message: string) => void,
): Promise<void> {
  const params = new URLSearchParams({
    ticker: request.ticker,
    target_cagr: String(request.target_cagr ?? 0.10),
    holding_period_years: String(5),
    force_refresh: String(request.force_refresh ?? false),
  });
  if (request.entry_price != null) {
    params.set('entry_price', String(request.entry_price));
  }

  const eventSource = new EventSource(`${API_BASE}/analyze-ticker/stream?${params}`);

  eventSource.addEventListener('progress', (e) => {
    try {
      const data = JSON.parse(e.data) as import('@/types/api').ProgressEvent;
      onProgress(data);
    } catch { /* ignore malformed events */ }
  });

  eventSource.addEventListener('complete', (e) => {
    eventSource.close();
    try {
      const data = JSON.parse(e.data) as import('@/types/api').AnalyzeResponse;
      onComplete(data);
    } catch {
      onError('Failed to parse analysis result');
    }
  });

  eventSource.addEventListener('error', () => {
    eventSource.close();
    onError('Connection to analysis server lost. Is the backend running?');
  });
}

export async function analyzeTicker(
  request: import('@/types/api').AnalyzeRequest
): Promise<import('@/types/api').AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze-ticker`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
