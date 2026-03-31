const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Optional: set NEXT_PUBLIC_API_KEY in .env.local to enable auth mode.
// EventSource cannot send headers, so the key is passed as a query param.
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

export function analyzeTickerStream(
  request: import('@/types/api').AnalyzeRequest,
  onProgress: (event: import('@/types/api').ProgressEvent) => void,
  onComplete: (result: import('@/types/api').AnalyzeResponse) => void,
  onError: (message: string) => void,
  onHeartbeat?: () => void,
): () => void {
  const params = new URLSearchParams({
    ticker: request.ticker,
    target_cagr: String(request.target_cagr ?? 0.10),
    holding_period_years: String(request.holding_period_years ?? 5),
    force_refresh: String(request.force_refresh ?? false),
  });
  if (request.entry_price != null) {
    params.set('entry_price', String(request.entry_price));
  }
  if (API_KEY) {
    // x_api_key (underscore) is the query-param name the backend accepts
    params.set('x_api_key', API_KEY);
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

  // Custom 'error' event emitted by the backend when analysis fails
  eventSource.addEventListener('error', (e: MessageEvent) => {
    eventSource.close();
    try {
      const data = JSON.parse(e.data);
      onError(data.detail || 'Analysis failed');
    } catch {
      // Native EventSource onerror fires with no data — backend is unreachable
      onError('Cannot reach the backend. Make sure it is running on port 8000.');
    }
  });

  eventSource.addEventListener('ping', () => {
    onHeartbeat?.();
  });

  // Native onerror fires when the EventSource connection itself fails
  eventSource.onerror = () => {
    if (eventSource.readyState === EventSource.CLOSED) return; // already handled above
    eventSource.close();
    onError('Cannot reach the backend. Make sure it is running on port 8000.');
  };

  // Return a cancel function so callers can close the stream early
  return () => eventSource.close();
}

export async function analyzeTicker(
  request: import('@/types/api').AnalyzeRequest
): Promise<import('@/types/api').AnalyzeResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (API_KEY) headers['x-api-key'] = API_KEY;

  const res = await fetch(`${API_BASE}/analyze-ticker`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
