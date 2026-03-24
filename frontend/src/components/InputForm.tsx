'use client';
import { useState, FormEvent } from 'react';
import type { AnalyzeRequest } from '@/types/api';

interface Props {
  onSubmit: (req: AnalyzeRequest) => void;
  disabled?: boolean;
}

export default function InputForm({ onSubmit, disabled }: Props) {
  const [ticker, setTicker] = useState('');
  const [targetCagr, setTargetCagr] = useState('10');
  const [holdingPeriod, setHoldingPeriod] = useState('5');

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;
    onSubmit({
      ticker: ticker.trim().toUpperCase(),
      target_cagr: parseFloat(targetCagr) / 100,
      horizons: [1, parseInt(holdingPeriod), 5, 10].filter((v, i, a) => a.indexOf(v) === i).sort(),
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-md w-full">
      {/* Ticker */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-300">Ticker</label>
        <input
          type="text"
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="AAPL"
          maxLength={10}
          required
          disabled={disabled}
          className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 text-white text-lg font-mono tracking-wider placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />
      </div>

      {/* Target return */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-300">
          Target annual return <span className="text-gray-500">(default 10%)</span>
        </label>
        <div className="relative">
          <input
            type="number"
            value={targetCagr}
            onChange={e => setTargetCagr(e.target.value)}
            min="1" max="50" step="0.5"
            disabled={disabled}
            className="bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 text-white w-full focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400">%</span>
        </div>
      </div>

      {/* Holding period */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-300">
          Holding period <span className="text-gray-500">(default 5 years)</span>
        </label>
        <div className="flex gap-2">
          {[1, 3, 5, 10].map(y => (
            <button
              key={y}
              type="button"
              onClick={() => setHoldingPeriod(String(y))}
              disabled={disabled}
              className={`flex-1 py-3 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                holdingPeriod === String(y)
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 border border-gray-600 text-gray-300 hover:border-blue-500'
              }`}
            >
              {y}yr
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={disabled || !ticker.trim()}
        className="mt-2 w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-4 rounded-lg transition-colors text-base"
      >
        Analyze
      </button>
    </form>
  );
}
