'use client';
import { useState, useEffect, useRef } from 'react';

interface Props {
  stage: string;
  progress_pct: number;
  startTime: number | null;
  lastHeartbeat?: number;
}

const STAGES = [
  'Pulling financials',
  'Reading filings & transcripts',
  'Analyzing the growth story',
  'Checking the price',
  'Running stress scenarios',
  'Writing verdict',
];

export default function ProgressRail({ stage, progress_pct, startTime, lastHeartbeat }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [heartbeatActive, setHeartbeatActive] = useState(false);
  const heartbeatTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Tick elapsed time every second
  useEffect(() => {
    if (!startTime) { setElapsed(0); return; }
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  // Flash heartbeat dot for 2 seconds after each ping
  useEffect(() => {
    if (!lastHeartbeat) return;
    setHeartbeatActive(true);
    if (heartbeatTimer.current) clearTimeout(heartbeatTimer.current);
    heartbeatTimer.current = setTimeout(() => setHeartbeatActive(false), 2000);
    return () => {
      if (heartbeatTimer.current) clearTimeout(heartbeatTimer.current);
    };
  }, [lastHeartbeat]);

  const currentIdx = STAGES.findIndex(s =>
    stage.toLowerCase().includes(s.toLowerCase().split(' ')[0])
  );

  const fmtElapsed = (s: number) => s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;

  return (
    <div className="w-full max-w-2xl">
      {/* Progress bar + elapsed time */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${progress_pct}%` }}
          />
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Heartbeat dot */}
          <span
            className={`w-2 h-2 rounded-full transition-colors duration-300 ${
              heartbeatActive ? 'bg-green-400' : 'bg-gray-700'
            }`}
          />
          {startTime && (
            <span className="text-xs text-gray-500 font-mono w-12 text-right">
              {fmtElapsed(elapsed)}
            </span>
          )}
        </div>
      </div>

      {/* Stage list */}
      <div className="flex flex-col gap-2">
        {STAGES.map((s, i) => {
          const isDone = currentIdx > i;
          const isActive = currentIdx === i;
          return (
            <div
              key={s}
              className={`flex items-center gap-3 text-sm transition-all ${
                isDone ? 'text-green-400' : isActive ? 'text-white' : 'text-gray-600'
              }`}
            >
              <span className="w-4 h-4 flex-shrink-0">
                {isDone ? '✓' : isActive ? '→' : '○'}
              </span>
              <span className={isActive ? 'font-medium' : ''}>{s}</span>
              {isActive && (
                <span className="text-blue-400 text-xs animate-pulse">running…</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom note */}
      <p className="mt-5 text-xs text-gray-600 text-center">
        Analysis pulls from multiple data sources — typically takes 60–90 seconds
      </p>
    </div>
  );
}
