"""
Unit tests for Phase C additions:
- edgar_client: get_risk_factor_evolution, get_insider_transactions, get_institutional_holders
- filings_rag node: _aggregate_insider_activity, _build_institutional_summary
- main.py: _state_to_response merges Phase C keys from filings_rag into sentiment
"""


# ---------------------------------------------------------------------------
# edgar_client — get_risk_factor_evolution
# ---------------------------------------------------------------------------

class TestGetRiskFactorEvolution:
    def test_returns_unavailable_when_edgartools_missing(self, monkeypatch):
        """If edgartools cannot be imported, return the unavailable fallback."""
        import app.data.edgar_client as ec

        def _raise(*_a, **_kw):
            raise RuntimeError("edgartools not installed")

        monkeypatch.setattr(ec, "_get_company_class", _raise)
        result = ec.get_risk_factor_evolution("AAPL")
        assert result == {"available": False}

    def test_returns_unavailable_when_no_filings(self, monkeypatch):
        """Return unavailable when get_filings returns nothing."""
        import app.data.edgar_client as ec

        class _FakeFilings:
            def latest(self, _n):
                return None

        class _FakeCompany:
            def __init__(self, ticker):
                pass

            def get_filings(self, form):
                return _FakeFilings()

        monkeypatch.setattr(ec, "_get_company_class", lambda: _FakeCompany)
        result = ec.get_risk_factor_evolution("AAPL")
        assert result == {"available": False}

    def test_returns_available_true_with_risk_text(self, monkeypatch):
        """When two filings are present, return both risk texts with available=True."""
        import app.data.edgar_client as ec

        class _FakeObj:
            def __init__(self, text):
                self.risk_factors = text

        class _FakeFiling:
            def __init__(self, text):
                self._text = text

            def obj(self):
                return _FakeObj(self._text)

        class _FakeFilings:
            def latest(self, _n):
                return [_FakeFiling("current risk text"), _FakeFiling("prior risk text")]

        class _FakeCompany:
            def __init__(self, ticker):
                pass

            def get_filings(self, form):
                return _FakeFilings()

        monkeypatch.setattr(ec, "_get_company_class", lambda: _FakeCompany)
        result = ec.get_risk_factor_evolution("AAPL")
        assert result["available"] is True
        assert result["current_risks_text"] == "current risk text"
        assert result["prior_risks_text"] == "prior risk text"

    def test_prior_text_empty_when_only_one_filing(self, monkeypatch):
        """If only one 10-K exists, prior_risks_text should be empty string."""
        import app.data.edgar_client as ec

        class _FakeObj:
            risk_factors = "only year risk text"

        class _FakeFiling:
            def obj(self):
                return _FakeObj()

        class _FakeFilings:
            def latest(self, _n):
                return [_FakeFiling()]  # single-item list

        class _FakeCompany:
            def __init__(self, ticker):
                pass

            def get_filings(self, form):
                return _FakeFilings()

        monkeypatch.setattr(ec, "_get_company_class", lambda: _FakeCompany)
        result = ec.get_risk_factor_evolution("AAPL")
        assert result["available"] is True
        assert result["prior_risks_text"] == ""

    def test_truncates_to_6000_chars(self, monkeypatch):
        """Risk text longer than 6000 chars is truncated."""
        import app.data.edgar_client as ec

        long_text = "x" * 10_000

        class _FakeObj:
            risk_factors = long_text

        class _FakeFiling:
            def obj(self):
                return _FakeObj()

        class _FakeFilings:
            def latest(self, _n):
                return [_FakeFiling(), _FakeFiling()]

        class _FakeCompany:
            def __init__(self, ticker):
                pass

            def get_filings(self, form):
                return _FakeFilings()

        monkeypatch.setattr(ec, "_get_company_class", lambda: _FakeCompany)
        result = ec.get_risk_factor_evolution("AAPL")
        assert len(result["current_risks_text"]) == 6_000
        assert len(result["prior_risks_text"]) == 6_000


# ---------------------------------------------------------------------------
# edgar_client — get_insider_transactions
# ---------------------------------------------------------------------------

class TestGetInsiderTransactions:
    def test_returns_empty_list_when_edgartools_missing(self, monkeypatch):
        """If edgartools cannot be imported, return [] gracefully."""
        import app.data.edgar_client as ec

        def _raise(*_a, **_kw):
            raise RuntimeError("edgartools not installed")

        monkeypatch.setattr(ec, "_get_company_class", _raise)
        result = ec.get_insider_transactions("AAPL")
        assert result == []

    def test_returns_empty_list_when_no_form4_filings(self, monkeypatch):
        """Return [] when get_filings returns nothing."""
        import app.data.edgar_client as ec

        class _FakeCompany:
            def __init__(self, ticker):
                pass

            def get_filings(self, form):
                return None

        monkeypatch.setattr(ec, "_get_company_class", lambda: _FakeCompany)
        result = ec.get_insider_transactions("AAPL")
        assert result == []


# ---------------------------------------------------------------------------
# edgar_client — get_institutional_holders
# ---------------------------------------------------------------------------

class TestGetInstitutionalHolders:
    def test_returns_unavailable_when_edgartools_missing(self, monkeypatch):
        """If edgartools cannot be imported, return unavailable."""
        import app.data.edgar_client as ec

        def _raise(*_a, **_kw):
            raise RuntimeError("edgartools not installed")

        monkeypatch.setattr(ec, "_get_company_class", _raise)
        result = ec.get_institutional_holders("AAPL")
        assert result == {"available": False}

    def test_returns_unavailable_when_no_13f_filings(self, monkeypatch):
        """Return unavailable when no 13F-HR filings found."""
        import app.data.edgar_client as ec

        class _FakeCompany:
            def __init__(self, ticker):
                pass

            def get_filings(self, form):
                return None

        monkeypatch.setattr(ec, "_get_company_class", lambda: _FakeCompany)
        result = ec.get_institutional_holders("AAPL")
        assert result == {"available": False}


# ---------------------------------------------------------------------------
# filings_rag — _aggregate_insider_activity
# ---------------------------------------------------------------------------

class TestAggregateInsiderActivity:
    def test_returns_none_for_empty_list(self):
        from app.nodes.filings_rag import _aggregate_insider_activity
        assert _aggregate_insider_activity([]) is None

    def test_net_buying_when_buys_exceed_sells(self):
        from app.nodes.filings_rag import _aggregate_insider_activity
        txns = [
            {"filer_name": "CEO", "transaction_date": "2026-01-10", "transaction_type": "buy", "shares": 1000.0, "value_usd": None},
            {"filer_name": "CFO", "transaction_date": "2026-01-05", "transaction_type": "sell", "shares": 100.0, "value_usd": None},
        ]
        result = _aggregate_insider_activity(txns)
        assert result is not None
        assert result["net_activity"] == "net_buying"

    def test_net_selling_when_sells_exceed_buys(self):
        from app.nodes.filings_rag import _aggregate_insider_activity
        txns = [
            {"filer_name": "CEO", "transaction_date": "2026-01-10", "transaction_type": "sell", "shares": 5000.0, "value_usd": None},
            {"filer_name": "CFO", "transaction_date": "2026-01-05", "transaction_type": "buy", "shares": 200.0, "value_usd": None},
        ]
        result = _aggregate_insider_activity(txns)
        assert result["net_activity"] == "net_selling"

    def test_signal_strength_strong_when_ratio_above_3x(self):
        from app.nodes.filings_rag import _aggregate_insider_activity
        txns = [
            {"filer_name": "CEO", "transaction_date": "2026-01-10", "transaction_type": "buy", "shares": 10000.0, "value_usd": None},
            {"filer_name": "CFO", "transaction_date": "2026-01-05", "transaction_type": "sell", "shares": 100.0, "value_usd": None},
        ]
        result = _aggregate_insider_activity(txns)
        # 10000 / 100 = 100x, far above 3x threshold for "strong"
        assert result["signal_strength"] == "strong"

    def test_neutral_when_only_grants(self):
        from app.nodes.filings_rag import _aggregate_insider_activity
        txns = [
            {"filer_name": "CEO", "transaction_date": "2026-01-10", "transaction_type": "grant", "shares": 5000.0, "value_usd": None},
        ]
        result = _aggregate_insider_activity(txns)
        # grants don't count as buy or sell — net is neutral
        assert result["net_activity"] == "neutral"
        assert result["signal_strength"] == "weak"

    def test_lookback_days_always_90(self):
        from app.nodes.filings_rag import _aggregate_insider_activity
        txns = [{"filer_name": "CEO", "transaction_date": "2026-01-10", "transaction_type": "buy", "shares": 100.0, "value_usd": None}]
        result = _aggregate_insider_activity(txns)
        assert result["lookback_days"] == 90


# ---------------------------------------------------------------------------
# filings_rag — _build_institutional_summary
# ---------------------------------------------------------------------------

class TestBuildInstitutionalSummary:
    def test_returns_none_when_unavailable(self):
        from app.nodes.filings_rag import _build_institutional_summary
        assert _build_institutional_summary({"available": False}) is None

    def test_returns_none_when_empty_holders(self):
        from app.nodes.filings_rag import _build_institutional_summary
        assert _build_institutional_summary({"available": True, "top_holders": []}) is None

    def test_returns_dict_with_top_holders(self):
        from app.nodes.filings_rag import _build_institutional_summary
        holders = [{"holder": "Vanguard", "shares": 1_000_000, "pct_outstanding": 5.0}]
        result = _build_institutional_summary({"available": True, "top_holders": holders})
        assert result is not None
        assert result["top_holders"] == holders
        assert result["notable_changes"] == []
        assert result["tier1_activity"] is None


# ---------------------------------------------------------------------------
# main.py — _state_to_response merges Phase C keys
# ---------------------------------------------------------------------------

class TestStateToResponsePhaseC:
    def test_phase_c_fields_merged_from_filings_rag(self):
        """filings_risk_evolution, insider_summary, institutional_summary
        must appear in the sentiment object when present in filings_rag."""
        from app.main import _state_to_response
        from app.models import AnalyzeRequest

        request = AnalyzeRequest(ticker="AAPL", target_cagr=0.10)
        state = {
            "ticker": "AAPL",
            "pm_synthesis": {},
            "probability_engine": {},
            "stress_test": {},
            "fundamentals": {},
            "valuation": {},
            "news_sentiment": {"news_sentiment_score": 0.5},
            "analyst_estimates": {},
            "macro": {},
            "filings_rag": {
                "filings_risk_evolution": {
                    "summary": "One new risk found.",
                    "notable_new_risks": ["cyber threat"],
                    "risks_downgraded_or_removed": [],
                },
                "insider_summary": {
                    "net_activity": "net_buying",
                    "lookback_days": 90,
                    "notable_transactions": [],
                    "signal_strength": "moderate",
                },
                "institutional_summary": None,  # absent — should not be set
            },
            "thesis_debate": None,
            "red_flags": [],
            "section_statuses": {},
        }

        response = _state_to_response(state, request)
        assert response.sentiment is not None
        # Phase C fields populated from filings_rag
        assert response.sentiment.filings_risk_evolution is not None
        assert response.sentiment.filings_risk_evolution.summary == "One new risk found."
        assert response.sentiment.insider_summary is not None
        assert response.sentiment.insider_summary.net_activity == "net_buying"
        # institutional_summary was None — should remain None
        assert response.sentiment.institutional_summary is None

    def test_phase_c_absent_when_filings_rag_is_none(self):
        """If filings_rag is None, sentinel fields should be None in sentiment."""
        from app.main import _state_to_response
        from app.models import AnalyzeRequest

        request = AnalyzeRequest(ticker="AAPL", target_cagr=0.10)
        state = {
            "ticker": "AAPL",
            "pm_synthesis": {},
            "probability_engine": {},
            "stress_test": {},
            "fundamentals": {},
            "valuation": {},
            "news_sentiment": {"news_sentiment_score": 0.3},
            "analyst_estimates": {},
            "macro": {},
            "filings_rag": None,
            "thesis_debate": None,
            "red_flags": [],
            "section_statuses": {},
        }

        response = _state_to_response(state, request)
        assert response.sentiment is not None
        assert response.sentiment.filings_risk_evolution is None
        assert response.sentiment.insider_summary is None
        assert response.sentiment.institutional_summary is None

    def test_news_sentiment_fields_preserved_alongside_phase_c(self):
        """Adding Phase C data must not overwrite existing news_sentiment fields."""
        from app.main import _state_to_response
        from app.models import AnalyzeRequest

        request = AnalyzeRequest(ticker="AAPL", target_cagr=0.10)
        state = {
            "ticker": "AAPL",
            "pm_synthesis": {},
            "probability_engine": {},
            "stress_test": {},
            "fundamentals": {},
            "valuation": {},
            "news_sentiment": {"news_sentiment_score": 0.75, "news_lookback_days": 30},
            "analyst_estimates": {},
            "macro": {},
            "filings_rag": {
                "filings_risk_evolution": {
                    "summary": "No change.",
                    "notable_new_risks": [],
                    "risks_downgraded_or_removed": [],
                },
                "insider_summary": None,
                "institutional_summary": None,
            },
            "thesis_debate": None,
            "red_flags": [],
            "section_statuses": {},
        }

        response = _state_to_response(state, request)
        # Original news sentiment score is intact
        assert response.sentiment.news_sentiment_score == 0.75
        # Phase C is present
        assert response.sentiment.filings_risk_evolution is not None
