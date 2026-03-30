// frontend/src/types/api.ts

export type Segment = 'large_cap_blue_chip' | 'mid_cap' | 'small_cap_high_vol' | 'other';
export type DataQuality = 'high' | 'medium' | 'low';
export type ConfidenceVerdict = 'high_confidence' | 'moderate_confidence' | 'low_confidence' | 'insufficient_data';
export type StressVerdict = 'robust' | 'conditional' | 'fragile';
export type PriceEfficiencyVerdict = 'appears_inflated' | 'fairly_priced' | 'appears_conservative' | 'insufficient_data';
export type RedFlagCategory = 'execution' | 'balance_sheet' | 'competitive' | 'regulatory' | 'macro' | 'valuation' | 'governance';
export type MacroRegime = 'disinflation' | 'sticky_inflation' | 'higher_for_longer_rates' | 'recession' | 'goldilocks' | 'unknown';
export type HallucinationStatus = 'clean' | 'warnings' | 'blocked';

export interface AnalyzeRequest {
  ticker: string;
  target_cagr?: number;
  holding_period_years?: number;
  entry_price?: number | null;
  horizons?: number[];
  force_refresh?: boolean;
  debug?: boolean;
}

export interface ProbabilityHorizon {
  years: number;
  prob_ge_target_low: number;
  prob_ge_target_high: number;
}

export interface ProbabilityEntryDependenceRow {
  entry_price: number;
  years: number;
  prob_ge_target_low: number;
  prob_ge_target_high: number;
}

export interface ProbabilityDownsideRiskRow {
  years: number;
  prob_le_zero_cagr_low: number;
  prob_le_zero_cagr_high: number;
}

export interface ProbabilityDistributionPercentile {
  label: string;
  value: number;
  note?: string | null;
}

export interface ProbabilityDistributionSummary {
  summary?: string | null;
  mean_return?: number | null;
  median_return?: number | null;
  p10_return?: number | null;
  p25_return?: number | null;
  p75_return?: number | null;
  p90_return?: number | null;
  probability_ge_target?: number | null;
  probability_le_zero_cagr?: number | null;
  percentiles?: ProbabilityDistributionPercentile[];
  notes?: string | null;
}

export interface SuggestedEntryPrice {
  price: number;
  prob_ge_target_low: number;
  prob_ge_target_high: number;
  note?: string;
}

export interface ProbabilityEngine {
  enabled: boolean;
  reason_disabled?: string | null;
  confidence_tier?: string | null;
  horizons: ProbabilityHorizon[];
  suggested_entry_price?: SuggestedEntryPrice | null;
  entry_dependence: ProbabilityEntryDependenceRow[];
  downside_risk: ProbabilityDownsideRiskRow[];
  calibration_notes?: string | null;
  methodology_notes?: string | null;
  scenario_weights?: { bull: number; base: number; bear: number } | null;
  base_growth?: number | null;
  current_price?: number | null;
  target_cagr?: number | null;
  distribution_summary?: ProbabilityDistributionSummary | null;
  percentile_summary?: ProbabilityDistributionSummary | null;
  return_distribution?: ProbabilityDistributionSummary | null;
}

export interface PriceEfficiencyAssessment {
  implied_revenue_cagr_5yr?: number | null;
  implied_vs_management_guidance?: string | null;
  efficiency_verdict?: PriceEfficiencyVerdict | null;
  efficiency_notes?: string | null;
  sentiment_premium_flag: boolean;
  sentiment_premium_notes?: string | null;
  historical_analog?: string | null;
}

export interface OptionsSentiment {
  expiry?: string | null;
  days_to_expiry?: number | null;
  atm_strike?: number | null;
  implied_volatility?: number | null;
  implied_move_pct?: number | null;
  call_put_oi_ratio?: number | null;
  lean?: 'bullish' | 'bearish' | 'neutral' | string | null;
  thesis_alignment?: 'supports_thesis' | 'mixed' | 'contradicts_thesis' | string | null;
  summary?: string | null;
  source?: string | null;
}

export interface EntryBand {
  accumulate_below?: number | null;
  strong_buy_below?: number | null;
  notes?: string | null;
}

export interface Valuation {
  current_price?: number | null;
  currency: string;
  fair_value_low?: number | null;
  fair_value_base?: number | null;
  fair_value_high?: number | null;
  valuation_method_summary?: string | null;
  suggested_entry_band?: EntryBand | null;
  price_efficiency_assessment?: PriceEfficiencyAssessment | null;
  valuation_confidence?: string | null;
  valuation_notes?: string | null;
}

export interface StressTest {
  base_case_summary?: string | null;
  shocks: Array<{
    assumption_tested: string;
    variable: string;
    mild_shock?: { description: string; thesis_survives: boolean } | null;
    severe_shock?: { description: string; thesis_survives: boolean } | null;
  }>;
  fragile_assumptions: string[];
  robust_assumptions: string[];
  stress_verdict?: StressVerdict | null;
  stress_verdict_notes?: string | null;
}

export interface Sentiment {
  news_sentiment_score?: number | null;
  news_lookback_days?: number;
  options_sentiment?: OptionsSentiment | null;
}

export interface SectionStatusDetail {
  status: string;
  source?: string | null;
  cached: boolean;
  ttl_remaining_s?: number | null;
}

export interface HallucinationCheck {
  validated_at?: string | null;
  numbers_checked: number;
  numbers_matched: number;
  numbers_flagged: number;
  overall_status: HallucinationStatus;
}

export interface RedFlag {
  category: RedFlagCategory;
  description: string;
  likelihood: 'low' | 'medium' | 'high';
  impact: 'low' | 'medium' | 'high';
}

export interface KeyDriver {
  driver: string;
  direction: 'positive' | 'negative' | 'mixed';
  importance: 'high' | 'medium' | 'low';
}

export interface Thesis {
  business_summary?: string | null;
  key_drivers: KeyDriver[];
  growth_bet?: {
    stated_bet: string;
    bet_credibility_score?: string | null;
    credibility_notes?: string | null;
    words_vs_numbers_alignment?: string | null;
    alignment_notes?: string | null;
  } | null;
}

export interface Analysts {
  coverage_level?: string | null;
  revision_trend?: string | null;
  rating_summary?: { buy?: number; hold?: number; sell?: number } | null;
  avg_target_price?: number | null;
  weighted_target_price?: number | null;
  analyst_sentiment_notes?: string | null;
}

export interface MacroAndCrowd {
  macro_regime?: MacroRegime | null;
  macro_regime_confidence?: string | null;
  macro_narrative?: string | null;
  scenario_impacts: Array<{ scenario: string; impact_on_business: string; impact_direction: string }>;
  polymarket_signals?: Array<{ market_name: string; implied_probability: number; direction_for_ticker: string; notes?: string | null }>;
}

export interface AnalyzeResponse {
  ticker: string;
  as_of: string;
  segment?: Segment | null;
  segment_confidence?: string | null;
  data_quality?: DataQuality | null;
  verdict_paragraph?: string | null;
  confidence_verdict?: ConfidenceVerdict | null;
  thesis?: Thesis | null;
  valuation?: Valuation | null;
  sentiment?: Sentiment | null;
  analysts?: Analysts | null;
  macro_and_crowd?: MacroAndCrowd | null;
  probability_engine?: ProbabilityEngine | null;
  stress_test?: StressTest | null;
  red_flags_and_failure_modes: RedFlag[];
  section_statuses: Record<string, SectionStatusDetail>;
  hallucination_check: HallucinationCheck;
  disclaimers: string[];
  debug?: Record<string, unknown> | null;
}

export interface ProgressEvent {
  stage: string;
  message: string;
  node?: string | null;
  progress_pct: number;
}

export type AnalysisState =
  | { status: 'idle' }
  | { status: 'loading'; stage: string; progress_pct: number }
  | { status: 'success'; data: AnalyzeResponse }
  | { status: 'error'; message: string };

// ---------------------------------------------------------------------------
// Prediction Ledger (Phase A)
// ---------------------------------------------------------------------------

export type PredictionStatus = 'on_track' | 'at_risk' | 'off_track' | 'hit' | 'miss';

export interface PredictionOutcome {
  grade_date: string;
  realized_price: number;
  realized_cagr?: number | null;
  thesis_played_out?: string | null;
  outcome: 'hit' | 'miss';
}

export interface PredictionRecord {
  prediction_id: string;
  ticker: string;
  run_at: string;
  entry_price: number;
  target_cagr: number;
  holding_period_years: number;
  horizon_1yr_date: string;
  prob_low?: number | null;
  prob_high?: number | null;
  confidence_verdict?: string | null;
  verdict_paragraph?: string | null;
  fair_value_base?: number | null;
  macro_regime?: string | null;
  segment?: string | null;
  nodes_with_data?: string[];
  outcome_1yr?: PredictionOutcome | null;
  outcome_notes?: string | null;
  stated_bet?: string | null;
  words_vs_numbers?: string | null;
  efficiency_verdict?: string | null;
}

export interface LeaderboardRow extends PredictionRecord {
  current_price?: number | null;
  ytd_growth?: number | null;
  required_by_year_end?: number | null;
  status?: PredictionStatus | null;
  days_remaining?: number | null;
}

export interface ScoreRequest {
  realized_price: number;
  thesis_played_out?: string | null;
  notes?: string | null;
}
