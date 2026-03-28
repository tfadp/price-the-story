import type { AnalyzeResponse } from '@/types/api';
import ConfidenceBadge from './ConfidenceBadge';
import StressBadge from './StressBadge';
import PriceEfficiencyBadge from './PriceEfficiencyBadge';

interface Props {
  data: AnalyzeResponse;
  targetCagr: number;
  holdingPeriod: number;
}

function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null) return 'N/A';
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return 'N/A';
  return `${fmt(n * 100, 0)}%`;
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return 'N/A';
  return `$${fmt(n, 2)}`;
}

function formatSectionName(name: string): string {
  return name.replace(/_/g, ' ');
}

export default function VerdictCard({ data, targetCagr, holdingPeriod }: Props) {
  const prob = data.probability_engine;
  const val = data.valuation;
  const stress = data.stress_test;
  const efficiency = val?.price_efficiency_assessment;
  const sectionStatuses = Object.entries(data.section_statuses ?? {});
  const failedSections = sectionStatuses.filter(([, status]) => status.status === 'failed').map(([name]) => name);
  const partialSections = sectionStatuses.filter(([, status]) => status.status === 'partial').map(([name]) => name);
  const warningStatus = data.hallucination_check?.overall_status;
  const trustMode = prob?.enabled === false || data.confidence_verdict === 'insufficient_data'
    ? 'insufficient'
    : 'heuristic';

  // Find probability for user's holding period
  const horizonProb = prob?.horizons?.find(h => h.years === holdingPeriod)
    ?? prob?.horizons?.[prob.horizons.length - 1];

  // Top 2 red flags
  const topRisks = data.red_flags_and_failure_modes.slice(0, 2);

  return (
    <div className="w-full max-w-3xl bg-gray-900 border border-gray-700 rounded-2xl p-8 shadow-2xl">
      {/* Header row */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">
            {data.ticker}
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            {data.segment?.replace(/_/g, ' ')} · {data.data_quality} data quality
          </p>
        </div>
        <ConfidenceBadge verdict={data.confidence_verdict} />
      </div>

      {/* Trust / data health */}
      <div className="bg-gray-800/80 border border-gray-700 rounded-xl p-4 mb-6">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${
            trustMode === 'insufficient'
              ? 'bg-yellow-950 text-yellow-300 border-yellow-800'
              : 'bg-gray-950 text-gray-300 border-gray-700'
          }`}>
            {trustMode === 'insufficient' ? 'Insufficient data mode' : 'Heuristic model'}
          </span>
          {warningStatus && warningStatus !== 'clean' && (
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border ${
              warningStatus === 'blocked'
                ? 'bg-red-950 text-red-300 border-red-800'
                : 'bg-yellow-950 text-yellow-300 border-yellow-800'
            }`}>
              Hallucination check: {warningStatus}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-300 leading-relaxed">
          {prob?.enabled === false
            ? `Probability engine disabled: ${prob.reason_disabled ?? 'no reason provided'}.`
            : data.confidence_verdict === 'insufficient_data'
              ? 'The model is deliberately withholding precision because the inputs are incomplete or low quality.'
              : 'This is a heuristic estimate, not a calibrated forecast. Use it as a directional screen and inspect the assumptions below.'}
        </p>
        <div className="flex flex-wrap gap-3 mt-3 text-xs text-gray-400">
          <span>Sections: {sectionStatuses.length}</span>
          {failedSections.length > 0 && <span>Failed: {failedSections.map(formatSectionName).join(', ')}</span>}
          {partialSections.length > 0 && <span>Partial: {partialSections.map(formatSectionName).join(', ')}</span>}
        </div>
      </div>

      {/* Probability statement */}
      {prob?.enabled !== false && horizonProb && (
        <div className="bg-gray-800 rounded-xl p-4 mb-6">
          <p className="text-gray-300 text-sm mb-1">
            Probability of reaching {fmtPct(targetCagr)} annual return over {holdingPeriod} years
          </p>
          <p className="text-3xl font-bold text-white">
            {fmtPct(horizonProb.prob_ge_target_low)} – {fmtPct(horizonProb.prob_ge_target_high)}
          </p>
          <p className="text-xs text-gray-500 mt-1">at today&apos;s price of {fmtUsd(val?.current_price)}</p>
          <p className="text-xs text-gray-500 mt-2">
            Scenario vote, not a calibrated frequency. Small input changes can move the range.
          </p>
        </div>
      )}

      {prob?.enabled === false && (
        <div className="bg-gray-800 rounded-xl p-4 mb-6">
          <p className="text-yellow-400 text-sm">
            Probability engine disabled: {prob.reason_disabled}
          </p>
          <p className="text-xs text-gray-500 mt-2">
            No numeric probability is shown because the model decided the inputs are too weak or noisy for this ticker.
          </p>
        </div>
      )}

      {/* Suggested entry price — only shown when relevant */}
      {prob?.suggested_entry_price && (
        <div className="bg-blue-950 border border-blue-800 rounded-xl p-4 mb-6">
          <p className="text-blue-300 text-sm font-medium">Suggested entry price</p>
          <p className="text-2xl font-bold text-white mt-1">
            {fmtUsd(prob.suggested_entry_price.price)}
          </p>
          <p className="text-sm text-blue-300 mt-1">
            Probability rises to {fmtPct(prob.suggested_entry_price.prob_ge_target_low)}–{fmtPct(prob.suggested_entry_price.prob_ge_target_high)} at this price
          </p>
          {prob.suggested_entry_price.note && (
            <p className="text-xs text-blue-400 mt-1">{prob.suggested_entry_price.note}</p>
          )}
        </div>
      )}

      {/* Price efficiency + stress verdict row */}
      <div className="flex flex-wrap gap-4 mb-6">
        {efficiency?.efficiency_verdict && (
          <div>
            <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Price</p>
            <PriceEfficiencyBadge
              verdict={efficiency.efficiency_verdict}
              notes={efficiency.efficiency_notes}
            />
          </div>
        )}
        {stress?.stress_verdict && (
          <div>
            <p className="text-xs text-gray-500 mb-1 uppercase tracking-wider">Thesis strength</p>
            <StressBadge
              verdict={stress.stress_verdict}
              notes={stress.stress_verdict_notes}
            />
          </div>
        )}
      </div>

      {/* Verdict paragraph — THE HERO */}
      {data.verdict_paragraph && (
        <div className="mb-6">
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Verdict</p>
          <p className="text-gray-100 text-base leading-relaxed font-light">
            {data.verdict_paragraph}
          </p>
        </div>
      )}

      {/* Top 2 risks */}
      {topRisks.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-gray-500 mb-3 uppercase tracking-wider">Top risks</p>
          <div className="flex flex-col gap-2">
            {topRisks.map((flag, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                  flag.impact === 'high' ? 'bg-red-500' :
                  flag.impact === 'medium' ? 'bg-yellow-500' : 'bg-gray-500'
                }`} />
                <div>
                  <span className="text-xs text-gray-500 uppercase tracking-wider mr-2">
                    {flag.category}
                  </span>
                  <span className="text-sm text-gray-300">{flag.description}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fair value band */}
      {val?.fair_value_low && val?.fair_value_high && (
        <div className="bg-gray-800 rounded-xl p-4 mb-6">
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Fair value range</p>
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm">{fmtUsd(val.fair_value_low)}</span>
            <div className="flex-1 h-2 bg-gray-700 rounded-full relative">
              {val.current_price && val.fair_value_low && val.fair_value_high && (
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-gray-900"
                  style={{
                    left: `${Math.max(0, Math.min(100,
                      ((val.current_price - val.fair_value_low) /
                      (val.fair_value_high - val.fair_value_low)) * 100
                    ))}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                  title={`Current price: ${fmtUsd(val.current_price)}`}
                />
              )}
            </div>
            <span className="text-gray-400 text-sm">{fmtUsd(val.fair_value_high)}</span>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center">
            Current: {fmtUsd(val.current_price)} · Base: {fmtUsd(val.fair_value_base)}
          </p>
        </div>
      )}

      {/* Calibration note — small, always present */}
      {prob?.calibration_notes && (
        <p className="text-xs text-gray-600 mb-4">{prob.calibration_notes}</p>
      )}

      {data.debug && (
        <div className="bg-gray-800 rounded-xl p-4 mb-4">
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Debug metadata</p>
          <pre className="text-[11px] leading-relaxed text-gray-400 whitespace-pre-wrap break-words">
            {JSON.stringify(data.debug, null, 2)}
          </pre>
        </div>
      )}

      {/* Disclaimers */}
      {data.disclaimers?.length > 0 && (
        <div className="pt-4 border-t border-gray-800">
          {data.disclaimers.map((d, i) => (
            <p key={i} className="text-xs text-gray-600 leading-relaxed">{d}</p>
          ))}
        </div>
      )}
    </div>
  );
}
