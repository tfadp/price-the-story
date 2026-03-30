'use client';
import { useEffect, useState } from 'react';
import type { LeaderboardRow, ScoreRequest } from '@/types/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—';
  return (n * 100).toFixed(decimals) + '%';
}

function fmtPrice(n: number | null | undefined): string {
  if (n == null) return '—';
  return '$' + n.toFixed(2);
}

function daysLabel(days: number | null | undefined): string {
  if (days == null) return '—';
  if (days === 0) return 'Due';
  return `${days}d`;
}

const STATUS_STYLES: Record<string, string> = {
  on_track: 'bg-green-900 text-green-300',
  at_risk: 'bg-yellow-900 text-yellow-300',
  off_track: 'bg-red-900 text-red-300',
  hit: 'bg-green-800 text-green-200',
  miss: 'bg-red-800 text-red-200',
};

const CONFIDENCE_STYLES: Record<string, string> = {
  high_confidence: 'bg-green-900 text-green-300',
  moderate_confidence: 'bg-yellow-900 text-yellow-300',
  low_confidence: 'bg-orange-900 text-orange-300',
  insufficient_data: 'bg-gray-800 text-gray-400',
};

function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-gray-600">—</span>;
  const label = status.replace('_', ' ');
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status] ?? 'bg-gray-800 text-gray-400'}`}>
      {label}
    </span>
  );
}

function ConfidenceBadge({ verdict }: { verdict: string | null | undefined }) {
  if (!verdict) return <span className="text-gray-600">—</span>;
  const label = verdict.replace(/_/g, ' ').replace('confidence', '').trim();
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${CONFIDENCE_STYLES[verdict] ?? 'bg-gray-800 text-gray-400'}`}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Score modal
// ---------------------------------------------------------------------------

interface ScoreModalProps {
  row: LeaderboardRow;
  onClose: () => void;
  onScored: () => void;
}

function ScoreModal({ row, onClose, onScored }: ScoreModalProps) {
  const [realizedPrice, setRealizedPrice] = useState(
    row.current_price ? String(row.current_price.toFixed(2)) : ''
  );
  const [thesis, setThesis] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const realized = parseFloat(realizedPrice);
  const realizedCagr = !isNaN(realized) && row.entry_price > 0
    ? (realized / row.entry_price) ** (1 / Math.max(row.holding_period_years, 0.01)) - 1
    : null;

  async function submit() {
    if (isNaN(realized) || realized <= 0) {
      setError('Enter a valid price');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: ScoreRequest = {
        realized_price: realized,
        thesis_played_out: thesis || null,
        notes: notes || null,
      };
      const res = await fetch(`${API_BASE}/predictions/${row.prediction_id}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onScored();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit');
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md p-6 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold">Score {row.ticker}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">×</button>
        </div>

        <div className="text-sm text-gray-400 space-y-1">
          <p>Entry price: <span className="text-white">{fmtPrice(row.entry_price)}</span></p>
          <p>Target: <span className="text-white">{fmt(row.target_cagr)} / {row.holding_period_years}yr</span></p>
          {realizedCagr != null && (
            <p>
              Realized CAGR:{' '}
              <span className={realizedCagr >= row.target_cagr ? 'text-green-400' : 'text-red-400'}>
                {fmt(realizedCagr)}
              </span>
              {' '}— {realizedCagr >= row.target_cagr ? '✓ Hit' : '✗ Miss'}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Realized price *</label>
            <input
              type="number"
              step="0.01"
              value={realizedPrice}
              onChange={e => setRealizedPrice(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              placeholder="e.g. 310.00"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Did the thesis play out?</label>
            <textarea
              value={thesis}
              onChange={e => setThesis(e.target.value)}
              rows={2}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
              placeholder="What happened vs. your original thesis?"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 resize-none"
              placeholder="Anything else worth noting"
            />
          </div>
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm rounded-lg font-medium transition-colors"
          >
            {submitting ? 'Saving…' : 'Submit Score'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main leaderboard table
// ---------------------------------------------------------------------------

export default function PredictionsTab() {
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scoring, setScoring] = useState<LeaderboardRow | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/predictions/leaderboard`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: LeaderboardRow[] = await res.json();
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load predictions');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function handleScored() {
    setScoring(null);
    load();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-500 text-sm">Loading predictions…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <p className="text-red-400 text-sm">{error}</p>
        <button onClick={load} className="text-sm text-blue-400 hover:text-blue-300">Retry</button>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <p className="text-gray-400 text-sm font-medium">No predictions yet</p>
        <p className="text-gray-600 text-xs max-w-xs">
          Every analysis you run is automatically logged here. Run your first analysis to start building your track record.
        </p>
      </div>
    );
  }

  const dueCount = rows.filter(r => !r.outcome_1yr && (r.days_remaining ?? 999) <= 14).length;

  return (
    <div className="w-full flex flex-col gap-4">

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-white font-semibold">My Predictions</h2>
          <p className="text-gray-500 text-xs mt-0.5">{rows.length} logged · live prices from market</p>
        </div>
        {dueCount > 0 && (
          <span className="bg-yellow-900 text-yellow-300 text-xs font-medium px-2.5 py-1 rounded-full">
            {dueCount} due for scoring
          </span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-500 text-xs">
              <th className="text-left px-4 py-3 font-medium">Ticker</th>
              <th className="text-right px-4 py-3 font-medium">Entry</th>
              <th className="text-right px-4 py-3 font-medium">Target</th>
              <th className="text-right px-4 py-3 font-medium">YTD</th>
              <th className="text-right px-4 py-3 font-medium">Still needed</th>
              <th className="text-center px-4 py-3 font-medium">Confidence</th>
              <th className="text-center px-4 py-3 font-medium">Status</th>
              <th className="text-right px-4 py-3 font-medium">Days left</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isDue = !row.outcome_1yr && (row.days_remaining ?? 999) <= 14;
              const ytdPositive = (row.ytd_growth ?? 0) >= 0;
              return (
                <tr key={row.prediction_id} className="border-b border-gray-800/60 hover:bg-gray-900/40 transition-colors">
                  <td className="px-4 py-3">
                    <span className="text-white font-semibold">{row.ticker}</span>
                    <span className="text-gray-600 text-xs ml-2">{row.holding_period_years}yr</span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300">{fmtPrice(row.entry_price)}</td>
                  <td className="px-4 py-3 text-right text-gray-400">{fmt(row.target_cagr)}</td>
                  <td className={`px-4 py-3 text-right font-medium ${row.ytd_growth == null ? 'text-gray-600' : ytdPositive ? 'text-green-400' : 'text-red-400'}`}>
                    {row.ytd_growth != null ? (ytdPositive ? '+' : '') + fmt(row.ytd_growth) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400 text-xs">
                    {row.required_by_year_end != null ? fmt(row.required_by_year_end) : '—'}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <ConfidenceBadge verdict={row.confidence_verdict} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className={`px-4 py-3 text-right text-xs ${isDue ? 'text-yellow-400 font-medium' : 'text-gray-500'}`}>
                    {daysLabel(row.days_remaining)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isDue && !row.outcome_1yr && (
                      <button
                        onClick={() => setScoring(row)}
                        className="text-xs bg-blue-900 hover:bg-blue-800 text-blue-300 px-2.5 py-1 rounded transition-colors"
                      >
                        Score
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {scoring && (
        <ScoreModal row={scoring} onClose={() => setScoring(null)} onScored={handleScored} />
      )}
    </div>
  );
}
