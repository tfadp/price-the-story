'use client';
import { useState } from 'react';
import type { AnalyzeResponse } from '@/types/api';

interface PanelProps {
  label: string;
  children: React.ReactNode;
}

function Panel({ label, children }: PanelProps) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-6 py-4 text-left bg-gray-900 hover:bg-gray-800 transition-colors"
      >
        <span className="text-sm font-medium text-gray-300">{label}</span>
        <span className="text-gray-500 text-lg">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="px-6 py-5 bg-gray-950 text-sm text-gray-300">
          {children}
        </div>
      )}
    </div>
  );
}

function fmtUsd(n: number | null | undefined) {
  if (n == null) return 'N/A';
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number | null | undefined) {
  if (n == null) return 'N/A';
  return `${(n * 100).toFixed(0)}%`;
}

interface Props {
  data: AnalyzeResponse;
}

export default function DetailPanels({ data }: Props) {
  const { thesis, valuation, analysts, macro_and_crowd, probability_engine, stress_test } = data;

  return (
    <div className="w-full max-w-3xl mt-4">
      <p className="text-sm text-gray-500 mb-4 text-center">See the evidence behind this verdict</p>
      <div className="flex flex-col gap-3">

        {/* The Bet & The Evidence */}
        <Panel label="The Bet & The Evidence">
          {thesis?.business_summary && (
            <p className="mb-4 text-gray-300">{thesis.business_summary}</p>
          )}
          {thesis?.growth_bet?.stated_bet && (
            <div className="bg-gray-900 rounded-lg p-4 mb-4">
              <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Management&apos;s stated bet</p>
              <p className="text-gray-200 italic">&quot;{thesis.growth_bet.stated_bet}&quot;</p>
              {thesis.growth_bet.words_vs_numbers_alignment && (
                <p className="text-xs mt-2 text-gray-400">
                  Capital alignment: <span className="font-medium">{thesis.growth_bet.words_vs_numbers_alignment.replace(/_/g, ' ')}</span>
                </p>
              )}
            </div>
          )}
          {thesis?.key_drivers && thesis.key_drivers.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Key drivers</p>
              <div className="flex flex-col gap-1">
                {thesis.key_drivers.map((d, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className={`text-xs ${d.direction === 'positive' ? 'text-green-400' : d.direction === 'negative' ? 'text-red-400' : 'text-yellow-400'}`}>
                      {d.direction === 'positive' ? '↑' : d.direction === 'negative' ? '↓' : '↔'}
                    </span>
                    <span className="text-gray-300">{d.driver}</span>
                    <span className="text-xs text-gray-500">({d.importance})</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {!thesis && <p className="text-gray-500">Thesis data unavailable for this ticker.</p>}
        </Panel>

        {/* What Breaks It */}
        <Panel label="What Breaks It">
          {stress_test ? (
            <div>
              {stress_test.base_case_summary && (
                <p className="mb-4 text-gray-300">{stress_test.base_case_summary}</p>
              )}
              {stress_test.shocks?.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Stress scenarios</p>
                  <div className="flex flex-col gap-2">
                    {stress_test.shocks.map((shock, i) => (
                      <div key={i} className="bg-gray-900 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-2">{shock.assumption_tested} — {shock.variable}</p>
                        <div className="flex gap-4 text-xs">
                          {shock.mild_shock && (
                            <span className={`${shock.mild_shock.thesis_survives ? 'text-green-400' : 'text-red-400'}`}>
                              Mild: {shock.mild_shock.thesis_survives ? '✓ survives' : '✗ fails'}
                            </span>
                          )}
                          {shock.severe_shock && (
                            <span className={`${shock.severe_shock.thesis_survives ? 'text-green-400' : 'text-red-400'}`}>
                              Severe: {shock.severe_shock.thesis_survives ? '✓ survives' : '✗ fails'}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {stress_test.fragile_assumptions?.length > 0 && (
                <div>
                  <p className="text-xs text-red-400 mb-1 uppercase tracking-wider">Fragile assumptions</p>
                  {stress_test.fragile_assumptions.map((a, i) => (
                    <p key={i} className="text-sm text-gray-300">• {a}</p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Stress test data unavailable.</p>
          )}
        </Panel>

        {/* The Price */}
        <Panel label="The Price">
          {valuation ? (
            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Current price</p>
                  <p className="text-lg font-semibold">{fmtUsd(valuation.current_price)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Fair value base</p>
                  <p className="text-lg font-semibold">{fmtUsd(valuation.fair_value_base)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Bear case</p>
                  <p className="text-base">{fmtUsd(valuation.fair_value_low)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Bull case</p>
                  <p className="text-base">{fmtUsd(valuation.fair_value_high)}</p>
                </div>
              </div>
              {valuation.suggested_entry_band && (
                <div className="bg-gray-900 rounded-lg p-3">
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Entry band</p>
                  <p className="text-sm">Accumulate below: <span className="font-semibold">{fmtUsd(valuation.suggested_entry_band.accumulate_below)}</span></p>
                  <p className="text-sm">Strong buy below: <span className="font-semibold">{fmtUsd(valuation.suggested_entry_band.strong_buy_below)}</span></p>
                </div>
              )}
              {valuation.valuation_method_summary && (
                <p className="text-xs text-gray-500 italic">{valuation.valuation_method_summary}</p>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Valuation data unavailable.</p>
          )}
        </Panel>

        {/* What the Street Says */}
        <Panel label="What the Street Says">
          {analysts ? (
            <div className="flex flex-col gap-3">
              {analysts.rating_summary && (
                <div className="flex gap-4">
                  <span className="text-green-400">Buy: {analysts.rating_summary.buy ?? 0}</span>
                  <span className="text-gray-400">Hold: {analysts.rating_summary.hold ?? 0}</span>
                  <span className="text-red-400">Sell: {analysts.rating_summary.sell ?? 0}</span>
                </div>
              )}
              {analysts.avg_target_price && (
                <p className="text-sm">Avg price target: <span className="font-semibold">{fmtUsd(analysts.avg_target_price)}</span></p>
              )}
              {analysts.revision_trend && (
                <p className="text-sm">Revision trend: <span className={`font-semibold ${analysts.revision_trend === 'up' ? 'text-green-400' : analysts.revision_trend === 'down' ? 'text-red-400' : 'text-gray-400'}`}>{analysts.revision_trend}</span></p>
              )}
              {analysts.analyst_sentiment_notes && (
                <p className="text-sm text-gray-300 italic">{analysts.analyst_sentiment_notes}</p>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Analyst data unavailable. (Phase 2)</p>
          )}
        </Panel>

        {/* The Environment */}
        <Panel label="The Environment">
          {macro_and_crowd ? (
            <div className="flex flex-col gap-3">
              <div>
                <p className="text-xs text-gray-500 mb-1">Macro regime</p>
                <p className="text-base font-semibold">
                  {macro_and_crowd.macro_regime?.replace(/_/g, ' ') ?? 'Unknown'}
                  {macro_and_crowd.macro_regime_confidence && (
                    <span className="text-xs text-gray-500 ml-2">({macro_and_crowd.macro_regime_confidence} confidence)</span>
                  )}
                </p>
              </div>
              {macro_and_crowd.scenario_impacts?.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Scenario impacts</p>
                  {macro_and_crowd.scenario_impacts.map((s, i) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <span className={`text-xs mt-0.5 ${s.impact_direction === 'positive' ? 'text-green-400' : s.impact_direction === 'negative' ? 'text-red-400' : 'text-gray-400'}`}>●</span>
                      <div>
                        <p className="text-xs text-gray-500">{s.scenario}</p>
                        <p className="text-sm text-gray-300">{s.impact_on_business}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Macro data unavailable.</p>
          )}
        </Panel>

        {/* The Numbers in Detail */}
        <Panel label="The Numbers in Detail">
          {probability_engine?.enabled !== false && probability_engine?.horizons?.length ? (
            <div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-800">
                    <th className="text-left py-2">Horizon</th>
                    <th className="text-right py-2">Probability range</th>
                  </tr>
                </thead>
                <tbody>
                  {probability_engine.horizons.map(h => (
                    <tr key={h.years} className="border-b border-gray-900">
                      <td className="py-2 text-gray-300">{h.years}yr</td>
                      <td className="py-2 text-right font-mono">
                        {fmtPct(h.prob_ge_target_low)} – {fmtPct(h.prob_ge_target_high)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {probability_engine.calibration_notes && (
                <p className="text-xs text-gray-600 mt-3 italic">{probability_engine.calibration_notes}</p>
              )}
            </div>
          ) : probability_engine?.enabled === false ? (
            <p className="text-yellow-400">{probability_engine.reason_disabled}</p>
          ) : (
            <p className="text-gray-500">Probability data unavailable.</p>
          )}
        </Panel>

      </div>
    </div>
  );
}
