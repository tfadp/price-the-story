"""
Pydantic models for Price the Story API.
These are the LOCKED contracts between backend and frontend.
All enums match SPECS.md Section B — do not change without Change Control.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (LOCKED — SPECS.md)
# ---------------------------------------------------------------------------

class Segment(str, Enum):
    large_cap_blue_chip = "large_cap_blue_chip"
    mid_cap = "mid_cap"
    small_cap_high_vol = "small_cap_high_vol"
    other = "other"


class DataQuality(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ConfidenceVerdict(str, Enum):
    high_confidence = "high_confidence"
    moderate_confidence = "moderate_confidence"
    low_confidence = "low_confidence"
    insufficient_data = "insufficient_data"


class StressVerdict(str, Enum):
    robust = "robust"
    conditional = "conditional"
    fragile = "fragile"


class PriceEfficiencyVerdict(str, Enum):
    appears_inflated = "appears_inflated"
    fairly_priced = "fairly_priced"
    appears_conservative = "appears_conservative"
    insufficient_data = "insufficient_data"


class BetCategory(str, Enum):
    tam_expansion = "TAM_expansion"
    market_share_gain = "market_share_gain"
    new_product = "new_product"
    geographic_expansion = "geographic_expansion"
    cost_structure = "cost_structure"
    regulatory_catalyst = "regulatory_catalyst"
    sector_tailwind = "sector_tailwind"
    platform_network_effect = "platform_network_effect"


class WordsVsNumbersAlignment(str, Enum):
    aligned = "aligned"
    partial_misalignment = "partial_misalignment"
    significant_misalignment = "significant_misalignment"


class AssumptionDimension(str, Enum):
    market = "market"
    company_execution = "company_execution"
    capital = "capital"
    external_cost = "external_cost"
    regulation = "regulation"
    competitive = "competitive"
    technology = "technology"


class AssumptionFragility(str, Enum):
    robust = "robust"
    moderate = "moderate"
    fragile = "fragile"


class RedFlagCategory(str, Enum):
    execution = "execution"
    balance_sheet = "balance_sheet"
    competitive = "competitive"
    regulatory = "regulatory"
    macro = "macro"
    valuation = "valuation"
    governance = "governance"


class MacroRegime(str, Enum):
    disinflation = "disinflation"
    sticky_inflation = "sticky_inflation"
    higher_for_longer_rates = "higher_for_longer_rates"
    recession = "recession"
    goldilocks = "goldilocks"
    unknown = "unknown"


class InsiderNetActivity(str, Enum):
    net_buying = "net_buying"
    net_selling = "net_selling"
    neutral = "neutral"
    minimal_activity = "minimal_activity"


class HallucinationStatus(str, Enum):
    clean = "clean"
    warnings = "warnings"
    blocked = "blocked"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class Preferences(BaseModel):
    risk_focus: str = "balanced"
    theme_depth: str = "standard"
    language: str = "en-US"


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., description="US exchange symbol, e.g. AAPL")
    target_cagr: float = Field(default=0.10, description="Target annual return as decimal")
    entry_price: Optional[float] = Field(default=None, description="Override entry price USD")
    horizons: list[int] = Field(default=[1, 3, 5, 10])
    preferences: Preferences = Field(default_factory=Preferences)
    force_refresh: bool = False
    debug: bool = False


# ---------------------------------------------------------------------------
# Nested response models
# ---------------------------------------------------------------------------

class AssumptionItem(BaseModel):
    assumption: str
    dimension: AssumptionDimension
    linked_metric: str
    current_evidence: str
    fragility: AssumptionFragility
    tracking_source: str


class LeadingIndicator(BaseModel):
    indicator: str
    description: str
    current_reading: Optional[str] = None
    direction: str  # improving | deteriorating | stable
    source: str


class GrowthBet(BaseModel):
    stated_bet: str
    bet_category: Optional[BetCategory] = None
    assumption_sheet: list[AssumptionItem] = []
    words_vs_numbers_alignment: Optional[WordsVsNumbersAlignment] = None
    alignment_notes: Optional[str] = None
    leading_indicators: list[LeadingIndicator] = []
    bet_credibility_score: Optional[str] = None  # high | medium | low
    credibility_notes: Optional[str] = None
    implied_growth_in_price: Optional[float] = None


class LongTermTheme(BaseModel):
    name: str
    strength: str  # high | medium | low
    horizon: str   # 0-3y | 3-5y | 5-10y
    notes: Optional[str] = None


class KeyDriver(BaseModel):
    driver: str
    direction: str      # positive | negative | mixed
    importance: str     # high | medium | low


class Thesis(BaseModel):
    business_summary: Optional[str] = None
    long_term_themes: list[LongTermTheme] = []
    five_to_ten_year_thesis: Optional[str] = None
    key_drivers: list[KeyDriver] = []
    ai_and_disruption_notes: Optional[str] = None
    growth_bet: Optional[GrowthBet] = None


class RelativeValuation(BaseModel):
    sector_median_pe: Optional[float] = None
    company_forward_pe: Optional[float] = None
    percentile_vs_sector: Optional[float] = None


class EntryBand(BaseModel):
    accumulate_below: Optional[float] = None
    strong_buy_below: Optional[float] = None
    notes: Optional[str] = None


class PriceEfficiencyAssessment(BaseModel):
    implied_revenue_cagr_5yr: Optional[float] = None
    implied_vs_management_guidance: Optional[str] = None
    implied_vs_stress_base: Optional[str] = None
    implied_vs_stress_bear: Optional[str] = None
    efficiency_verdict: Optional[PriceEfficiencyVerdict] = None
    efficiency_notes: Optional[str] = None
    sentiment_premium_flag: bool = False
    sentiment_premium_notes: Optional[str] = None
    historical_analog: Optional[str] = None


class Valuation(BaseModel):
    current_price: Optional[float] = None
    currency: str = "USD"
    fair_value_low: Optional[float] = None
    fair_value_base: Optional[float] = None
    fair_value_high: Optional[float] = None
    valuation_method_summary: Optional[str] = None
    relative_valuation: Optional[RelativeValuation] = None
    suggested_entry_band: Optional[EntryBand] = None
    price_efficiency_assessment: Optional[PriceEfficiencyAssessment] = None


class ConsensusYear(BaseModel):
    year: int
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None


class EarningsSurprise(BaseModel):
    quarter: str
    eps_surprise_pct: Optional[float] = None
    revenue_surprise_pct: Optional[float] = None


class TrackedAnalyst(BaseModel):
    analyst_id: str
    analyst_name: str
    firm: str
    current_rating: Optional[str] = None
    current_price_target: Optional[float] = None
    accuracy_score: Optional[float] = None
    graded_calls_count: int = 0


class Analysts(BaseModel):
    coverage_level: Optional[str] = None
    consensus_growth_path: list[ConsensusYear] = []
    revision_trend: Optional[str] = None   # up | flat | down
    surprise_history: list[EarningsSurprise] = []
    rating_summary: Optional[dict] = None  # {buy: int, hold: int, sell: int}
    avg_target_price: Optional[float] = None
    weighted_target_price: Optional[float] = None
    analyst_sentiment_notes: Optional[str] = None
    tracked_analysts: list[TrackedAnalyst] = []


class NewsNarrative(BaseModel):
    label: str
    sentiment: str
    supporting_examples: list[str] = []


class Catalyst(BaseModel):
    date: str
    type: str
    description: str
    market_reaction: Optional[dict] = None


class FilingsRiskEvolution(BaseModel):
    summary: Optional[str] = None
    notable_new_risks: list[str] = []
    risks_downgraded_or_removed: list[str] = []


class InsiderSummary(BaseModel):
    net_activity: Optional[InsiderNetActivity] = None
    lookback_days: int = 90
    notable_transactions: list[dict] = []
    signal_strength: Optional[str] = None


class InstitutionalSummary(BaseModel):
    top_holders: list[dict] = []
    notable_changes: list[str] = []
    tier1_activity: Optional[str] = None


class Sentiment(BaseModel):
    news_sentiment_score: Optional[float] = None
    news_lookback_days: int = 30
    top_narratives: list[NewsNarrative] = []
    recent_catalysts: list[Catalyst] = []
    filings_risk_evolution: Optional[FilingsRiskEvolution] = None
    insider_summary: Optional[InsiderSummary] = None
    institutional_summary: Optional[InstitutionalSummary] = None


class ScenarioImpact(BaseModel):
    scenario: str
    impact_on_business: str
    impact_direction: str   # positive | negative | neutral


class PolymarketSignal(BaseModel):
    market_name: str
    implied_probability: float
    direction_for_ticker: str
    notes: Optional[str] = None


class MacroAndCrowd(BaseModel):
    macro_regime: Optional[MacroRegime] = None
    macro_regime_confidence: Optional[str] = None
    scenario_impacts: list[ScenarioImpact] = []
    polymarket_signals: list[PolymarketSignal] = []


class ProbabilityHorizon(BaseModel):
    years: int
    prob_ge_target_low: float
    prob_ge_target_high: float


class SuggestedEntryPrice(BaseModel):
    price: float
    prob_ge_target_low: float
    prob_ge_target_high: float
    note: Optional[str] = None


class EntryDependenceRow(BaseModel):
    entry_price: float
    years: int
    prob_ge_target_low: float
    prob_ge_target_high: float


class DownsideRiskRow(BaseModel):
    years: int
    prob_le_zero_cagr_low: float
    prob_le_zero_cagr_high: float


class ProbabilityEngine(BaseModel):
    enabled: bool = True
    reason_disabled: Optional[str] = None
    confidence_tier: Optional[str] = None
    horizons: list[ProbabilityHorizon] = []
    suggested_entry_price: Optional[SuggestedEntryPrice] = None
    entry_dependence: list[EntryDependenceRow] = []
    downside_risk: list[DownsideRiskRow] = []
    calibration_notes: Optional[str] = None


class RedFlag(BaseModel):
    category: RedFlagCategory
    description: str
    likelihood: str   # low | medium | high
    impact: str       # low | medium | high


class ShockScenario(BaseModel):
    description: str
    delta: str
    revenue_impact_pct: Optional[float] = None
    margin_impact_bps: Optional[float] = None
    thesis_survives: bool


class Shock(BaseModel):
    assumption_tested: str
    variable: str
    mild_shock: Optional[ShockScenario] = None
    severe_shock: Optional[ShockScenario] = None
    balance_sheet_check: Optional[str] = None
    return_under_mild: Optional[str] = None
    return_under_severe: Optional[str] = None


class StressTest(BaseModel):
    base_case_summary: Optional[str] = None
    shocks: list[Shock] = []
    fragile_assumptions: list[str] = []
    robust_assumptions: list[str] = []
    stress_verdict: Optional[StressVerdict] = None
    stress_verdict_notes: Optional[str] = None


class SectionStatusDetail(BaseModel):
    status: str         # ok | partial | failed | cached
    source: Optional[str] = None
    cached: bool = False
    ttl_remaining_s: Optional[int] = None


class HallucinationCheck(BaseModel):
    validated_at: Optional[str] = None
    numbers_checked: int = 0
    numbers_matched: int = 0
    numbers_flagged: int = 0
    overall_status: HallucinationStatus = HallucinationStatus.clean


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class AnalyzeResponse(BaseModel):
    ticker: str
    as_of: str
    segment: Optional[Segment] = None
    segment_confidence: Optional[str] = None
    data_quality: Optional[DataQuality] = None

    # HERO OUTPUT
    verdict_paragraph: Optional[str] = None
    confidence_verdict: Optional[ConfidenceVerdict] = None

    # Supporting sections (null when node failed/stubbed)
    thesis: Optional[Thesis] = None
    valuation: Optional[Valuation] = None
    analysts: Optional[Analysts] = None
    sentiment: Optional[Sentiment] = None
    macro_and_crowd: Optional[MacroAndCrowd] = None
    probability_engine: Optional[ProbabilityEngine] = None
    stress_test: Optional[StressTest] = None
    red_flags_and_failure_modes: list[RedFlag] = []

    section_statuses: dict[str, SectionStatusDetail] = {}
    hallucination_check: HallucinationCheck = Field(default_factory=HallucinationCheck)
    disclaimers: list[str] = []
    debug: Optional[dict] = None


# ---------------------------------------------------------------------------
# SSE progress events
# ---------------------------------------------------------------------------

PROGRESS_STAGES = [
    ("Pulling financials",         "fundamentals",       15),
    ("Reading filings & transcripts", "filings_rag",     30),
    ("Analyzing the growth story", "themes",             50),
    ("Checking the price",         "valuation",          65),
    ("Running stress scenarios",   "probability_engine", 80),
    ("Writing verdict",            "pm_synthesis",       95),
]


class ProgressEvent(BaseModel):
    stage: str
    message: str
    node: Optional[str] = None
    progress_pct: int = 0


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
