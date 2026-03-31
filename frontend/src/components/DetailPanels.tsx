'use client';
import { useState } from 'react';
import type { AnalyzeResponse } from '@/types/api';

interface PanelProps {
  label: string;
  children: React.ReactNode;
}

function Panel({ label, children }: PanelProps) {
  const [open, setOpen] = useState(true);
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

function fmtSignedPct(n: number | null | undefined) {
  if (n == null) return 'N/A';
  const value = (n * 100).toFixed(1);
  return `${Number(value) > 0 ? '+' : ''}${value}%`;
}

function formatStatusLabel(status: string) {
  return status.replace(/_/g, ' ');
}

function formatSectionName(name: string) {
  return name.replace(/_/g, ' ');
}

interface Props {
  data: AnalyzeResponse;
}

export default function DetailPanels({ data }: Props) {
  const { thesis, valuation, sentiment, analysts, macro_and_crowd, probability_engine, stress_test } = data;
  const sectionStatuses = Object.entries(data.section_statuses ?? {});
  const failedSections = sectionStatuses.filter(([, status]) => status.status === 'failed');
  const partialSections = sectionStatuses.filter(([, status]) => status.status === 'partial');
  const cachedSections = sectionStatuses.filter(([, status]) => status.cached);
  const scenarioImpacts = macro_and_crowd?.scenario_impacts ?? [];
  const polymarketSignals = macro_and_crowd?.polymarket_signals ?? [];
  const distributionSummary =
    probability_engine?.distribution_summary
    ?? probability_engine?.percentile_summary
    ?? probability_engine?.return_distribution
    ?? null;
  const distributionPercentiles = distributionSummary?.percentiles ?? [];

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
              {valuation.valuation_confidence && (
                <p className="text-xs text-gray-500">
                  Valuation confidence: <span className="font-semibold text-gray-300">{formatStatusLabel(valuation.valuation_confidence)}</span>
                </p>
              )}
              {valuation.valuation_method_summary && (
                <p className="text-xs text-gray-500 italic">{valuation.valuation_method_summary}</p>
              )}
              {valuation.valuation_notes && (
                <p className="text-xs text-gray-500 italic">{valuation.valuation_notes}</p>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Valuation data unavailable.</p>
          )}
        </Panel>

        {/* Options Market */}
        <Panel label="Options Market">
          {sentiment?.options_sentiment ? (
            <div className="flex flex-col gap-3">
              {sentiment.options_sentiment.summary && (
                <p className="text-gray-300">{sentiment.options_sentiment.summary}</p>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-500 mb-1">Expiry</p>
                  <p className="text-sm">{sentiment.options_sentiment.expiry ?? 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Days out</p>
                  <p className="text-sm">{sentiment.options_sentiment.days_to_expiry ?? 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Implied move</p>
                  <p className="text-sm">{fmtPct(sentiment.options_sentiment.implied_move_pct)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Call/put OI ratio</p>
                  <p className="text-sm">
                    {sentiment.options_sentiment.call_put_oi_ratio != null
                      ? `${sentiment.options_sentiment.call_put_oi_ratio.toFixed(2)}:1`
                      : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Lean</p>
                  <p className="text-sm">{sentiment.options_sentiment.lean?.replace(/_/g, ' ') ?? 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 mb-1">Thesis alignment</p>
                  <p className="text-sm">{sentiment.options_sentiment.thesis_alignment?.replace(/_/g, ' ') ?? 'N/A'}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">Options sentiment unavailable for this ticker.</p>
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
              {macro_and_crowd.macro_narrative && (
                <p className="text-sm text-gray-300 mb-3 italic">
                  {macro_and_crowd.macro_narrative}
                </p>
              )}
              <div>
                <p className="text-xs text-gray-500 mb-1">Macro regime</p>
                <p className="text-base font-semibold">
                  {macro_and_crowd.macro_regime?.replace(/_/g, ' ') ?? 'Unknown'}
                  {macro_and_crowd.macro_regime_confidence && (
                    <span className="text-xs text-gray-500 ml-2">({macro_and_crowd.macro_regime_confidence} confidence)</span>
                  )}
                </p>
              </div>
              {scenarioImpacts.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Scenario impacts</p>
                  {scenarioImpacts.map((s, i) => (
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
              {polymarketSignals.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Crowd signals</p>
                  {polymarketSignals.map((signal, i) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <span className="text-xs mt-0.5 text-gray-400">●</span>
                      <div>
                        <p className="text-xs text-gray-500">{signal.market_name}</p>
                        <p className="text-sm text-gray-300">
                          {fmtPct(signal.implied_probability)} implied probability · {signal.direction_for_ticker}
                        </p>
                        {signal.notes && (
                          <p className="text-xs text-gray-500">{signal.notes}</p>
                        )}
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
          {probability_engine ? (
            <div className="flex flex-col gap-4">
              <div className="bg-gray-900 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Model health</p>
                <div className="flex flex-col gap-2 text-sm text-gray-300">
                  <p>Mode: <span className="font-semibold">{probability_engine.enabled === false ? 'disabled' : 'heuristic scenario model'}</span></p>
                  {probability_engine.confidence_tier && (
                    <p>Confidence tier: <span className="font-semibold">{formatStatusLabel(probability_engine.confidence_tier)}</span></p>
                  )}
                  {probability_engine.reason_disabled && (
                    <p className="text-yellow-400">{probability_engine.reason_disabled}</p>
                  )}
                  {probability_engine.methodology_notes && (
                    <p className="text-xs text-gray-500 italic">{probability_engine.methodology_notes}</p>
                  )}
                  {probability_engine.calibration_notes && (
                    <p className="text-xs text-gray-500 italic">{probability_engine.calibration_notes}</p>
                  )}
                  {probability_engine.scenario_weights && (
                    <p className="text-xs text-gray-400">
                      Scenario weights:
                      {' '}
                      bull {fmtPct(probability_engine.scenario_weights.bull)} ·
                      {' '}
                      base {fmtPct(probability_engine.scenario_weights.base)} ·
                      {' '}
                      bear {fmtPct(probability_engine.scenario_weights.bear)}
                    </p>
                  )}
                  {probability_engine.base_growth != null && (
                    <p className="text-xs text-gray-400">Base growth assumption: {fmtPct(probability_engine.base_growth)}</p>
                  )}
                  {probability_engine.current_price != null && (
                    <p className="text-xs text-gray-400">Reference price: {fmtUsd(probability_engine.current_price)}</p>
                  )}
                  {probability_engine.target_cagr != null && (
                    <p className="text-xs text-gray-400">Target CAGR: {fmtPct(probability_engine.target_cagr)}</p>
                  )}
                </div>
              </div>

              {distributionSummary && (
                <div className="bg-gray-900 rounded-lg p-4">
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Distribution summary</p>
                  <div className="grid grid-cols-2 gap-3 text-sm text-gray-300">
                    {distributionSummary.mean_return != null && (
                      <p>Mean return: <span className="font-semibold">{fmtSignedPct(distributionSummary.mean_return)}</span></p>
                    )}
                    {distributionSummary.median_return != null && (
                      <p>Median return: <span className="font-semibold">{fmtSignedPct(distributionSummary.median_return)}</span></p>
                    )}
                    {distributionSummary.probability_ge_target != null && (
                      <p>Hit target: <span className="font-semibold">{fmtPct(distributionSummary.probability_ge_target)}</span></p>
                    )}
                    {distributionSummary.probability_le_zero_cagr != null && (
                      <p>Non-positive CAGR: <span className="font-semibold">{fmtPct(distributionSummary.probability_le_zero_cagr)}</span></p>
                    )}
                  </div>
                  {(distributionSummary.summary || distributionSummary.notes) && (
                    <p className="text-xs text-gray-500 italic mt-3">
                      {distributionSummary.summary ?? distributionSummary.notes}
                    </p>
                  )}
                  {(distributionSummary.p10_return != null || distributionSummary.p25_return != null || distributionSummary.p75_return != null || distributionSummary.p90_return != null) && (
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-400">
                      {distributionSummary.p10_return != null && <p>P10: {fmtSignedPct(distributionSummary.p10_return)}</p>}
                      {distributionSummary.p25_return != null && <p>P25: {fmtSignedPct(distributionSummary.p25_return)}</p>}
                      {distributionSummary.p75_return != null && <p>P75: {fmtSignedPct(distributionSummary.p75_return)}</p>}
                      {distributionSummary.p90_return != null && <p>P90: {fmtSignedPct(distributionSummary.p90_return)}</p>}
                    </div>
                  )}
                  {distributionPercentiles.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Percentile points</p>
                      <div className="flex flex-col gap-1">
                        {distributionPercentiles.map((point, i) => (
                          <div key={`${point.label}-${i}`} className="flex items-center justify-between text-xs text-gray-400">
                            <span>{point.label}</span>
                            <span className="font-mono">{fmtSignedPct(point.value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {probability_engine.enabled !== false && probability_engine.horizons?.length ? (
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
              ) : probability_engine.enabled === false ? (
                <p className="text-yellow-400">{probability_engine.reason_disabled}</p>
              ) : (
                <p className="text-gray-500">Probability data unavailable.</p>
              )}

              {probability_engine.suggested_entry_price && (
                <div className="bg-gray-900 rounded-lg p-3">
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Suggested entry price</p>
                  <p className="text-sm">Price: <span className="font-semibold">{fmtUsd(probability_engine.suggested_entry_price.price)}</span></p>
                  <p className="text-sm">Probability range: <span className="font-semibold">{fmtPct(probability_engine.suggested_entry_price.prob_ge_target_low)} – {fmtPct(probability_engine.suggested_entry_price.prob_ge_target_high)}</span></p>
                  {probability_engine.suggested_entry_price.note && (
                    <p className="text-xs text-gray-500 mt-1">{probability_engine.suggested_entry_price.note}</p>
                  )}
                </div>
              )}

              {probability_engine.downside_risk?.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Downside risk</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 text-xs border-b border-gray-800">
                        <th className="text-left py-2">Horizon</th>
                        <th className="text-right py-2">Probability of non-positive CAGR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {probability_engine.downside_risk.map(r => (
                        <tr key={r.years} className="border-b border-gray-900">
                          <td className="py-2 text-gray-300">{r.years}yr</td>
                          <td className="py-2 text-right font-mono">
                            {fmtPct(r.prob_le_zero_cagr_low)} – {fmtPct(r.prob_le_zero_cagr_high)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {probability_engine.entry_dependence?.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Entry dependence</p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 text-xs border-b border-gray-800">
                        <th className="text-left py-2">Entry</th>
                        <th className="text-right py-2">Probability range</th>
                      </tr>
                    </thead>
                    <tbody>
                      {probability_engine.entry_dependence.map(row => (
                        <tr key={`${row.entry_price}-${row.years}`} className="border-b border-gray-900">
                          <td className="py-2 text-gray-300">{fmtUsd(row.entry_price)} / {row.years}yr</td>
                          <td className="py-2 text-right font-mono">
                            {fmtPct(row.prob_ge_target_low)} – {fmtPct(row.prob_ge_target_high)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Probability data unavailable.</p>
          )}
        </Panel>

        {/* Data Health */}
        <Panel label="Data Health">
          <div className="flex flex-col gap-3">
            <div className="bg-gray-900 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Section statuses</p>
              {sectionStatuses.length > 0 ? (
                <div className="flex flex-col gap-1 text-sm text-gray-300">
                  <p>Total sections: <span className="font-semibold">{sectionStatuses.length}</span></p>
                  {failedSections.length > 0 && (
                    <p className="text-red-400">Failed: {failedSections.map(([name]) => formatSectionName(name)).join(', ')}</p>
                  )}
                  {partialSections.length > 0 && (
                    <p className="text-yellow-400">Partial: {partialSections.map(([name]) => formatSectionName(name)).join(', ')}</p>
                  )}
                  {cachedSections.length > 0 && (
                    <p className="text-gray-400">Cached: {cachedSections.map(([name]) => formatSectionName(name)).join(', ')}</p>
                  )}
                </div>
              ) : (
                <p className="text-gray-500">No section metadata was returned.</p>
              )}
            </div>

            <div className="bg-gray-900 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Hallucination check</p>
              <p className="text-sm text-gray-300">
                Status: <span className="font-semibold">{data.hallucination_check?.overall_status ?? 'unknown'}</span>
              </p>
              <p className="text-sm text-gray-300">
                Checked: <span className="font-semibold">{data.hallucination_check?.numbers_checked ?? 0}</span>
                {' '}| Matched: <span className="font-semibold">{data.hallucination_check?.numbers_matched ?? 0}</span>
                {' '}| Flagged: <span className="font-semibold">{data.hallucination_check?.numbers_flagged ?? 0}</span>
              </p>
              {data.hallucination_check?.validated_at && (
                <p className="text-xs text-gray-500 mt-1">Validated at {data.hallucination_check.validated_at}</p>
              )}
            </div>

            {data.debug && (
              <div className="bg-gray-900 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Debug metadata</p>
                <pre className="text-[11px] leading-relaxed text-gray-400 whitespace-pre-wrap break-words">
                  {JSON.stringify(data.debug, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </Panel>

      </div>
    </div>
  );
}
