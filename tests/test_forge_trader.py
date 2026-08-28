"""Unit tests for the non-networked core: risk guardrails, stop sizing, and PM parsing."""

import json
import os
import sys
from types import SimpleNamespace

import anthropic
import httpx2 as httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import forge_trader as forge_trader_module  # noqa: E402

from forge_trader import (  # noqa: E402
    MODEL_CATALOG,
    AlpacaBroker,
    Config,
    MultiAgentDebateEngine,
    ProgrammaticRiskEngine,
    UsageLedger,
    apply_model_overrides,
    get_model_profile,
)


def make_config(**overrides) -> Config:
    cfg = Config()
    cfg.max_position_percent = 0.10
    cfg.min_cash_buffer_percent = 0.20
    cfg.hard_stop_loss_percent = 0.10
    cfg.daily_loss_limit_percent = 0.03
    cfg.min_conviction = 0.65
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return cfg


def position(qty, market_value):
    return SimpleNamespace(qty=str(qty), market_value=str(market_value))


def decision(action="BUY", conviction=0.80, allocation=0.10):
    return {
        "action": action,
        "conviction_score": conviction,
        "allocation_percentage": allocation,
        "target_price": 120.0,
        "stop_loss_price": 90.0,
        "thesis_summary": "test",
        "key_risks": [],
    }


@pytest.fixture
def engine():
    return ProgrammaticRiskEngine(make_config())


BASE = dict(current_price=100.0, account_nav=100_000.0, cash_balance=100_000.0,
            active_positions={}, open_orders=[])


# --- BUY sizing ---------------------------------------------------------------

def test_buy_sized_to_max_position_percent(engine):
    approved, reason, qty = engine.validate_order("AAPL", decision(allocation=0.50), **BASE)
    assert approved, reason
    assert qty == 100  # 10% of 100k NAV / $100


def test_buy_respects_model_allocation_when_below_cap(engine):
    approved, _, qty = engine.validate_order("AAPL", decision(allocation=0.04), **BASE)
    assert approved
    assert qty == 40


def test_low_conviction_is_rejected(engine):
    approved, reason, qty = engine.validate_order("AAPL", decision(conviction=0.64), **BASE)
    assert not approved and qty == 0
    assert "below minimum threshold" in reason


def test_hold_is_rejected(engine):
    approved, reason, _ = engine.validate_order("AAPL", decision(action="HOLD"), **BASE)
    assert not approved and "HOLD" in reason


def test_pending_entry_order_blocks_duplicate(engine):
    args = {**BASE, "open_orders": ["AAPL"]}
    approved, reason, _ = engine.validate_order("AAPL", decision(), **args)
    assert not approved and "Duplicate guard" in reason


# --- Cash buffer --------------------------------------------------------------

def test_cash_buffer_blocks_when_reserve_breached(engine):
    args = {**BASE, "cash_balance": 15_000.0}  # reserve is 20k
    approved, reason, _ = engine.validate_order("AAPL", decision(), **args)
    assert not approved and "Cash buffer" in reason


def test_cash_buffer_caps_deployable_capital(engine):
    args = {**BASE, "cash_balance": 25_000.0}  # only 5k above the 20k reserve
    approved, _, qty = engine.validate_order("AAPL", decision(), **args)
    assert approved and qty == 50


# --- Concentration ------------------------------------------------------------

def test_existing_exposure_reduces_headroom(engine):
    args = {**BASE, "active_positions": {"AAPL": position(60, 6_000)}}
    approved, _, qty = engine.validate_order("AAPL", decision(), **args)
    assert approved and qty == 40  # 10k cap - 6k held = 4k of headroom


def test_position_at_cap_is_rejected(engine):
    args = {**BASE, "active_positions": {"AAPL": position(100, 10_000)}}
    approved, reason, qty = engine.validate_order("AAPL", decision(), **args)
    assert not approved and qty == 0
    assert "Concentration cap" in reason


# --- SELL ---------------------------------------------------------------------

def test_sell_without_position_is_rejected(engine):
    approved, reason, _ = engine.validate_order("AAPL", decision(action="SELL"), **BASE)
    assert not approved and "No active position" in reason


def test_sell_liquidates_full_long_position(engine):
    args = {**BASE, "active_positions": {"AAPL": position(37, 3_700)}}
    approved, _, qty = engine.validate_order("AAPL", decision(action="SELL"), **args)
    assert approved and qty == 37


def test_sell_ignores_short_position(engine):
    args = {**BASE, "active_positions": {"AAPL": position(-25, 2_500)}}
    approved, reason, qty = engine.validate_order("AAPL", decision(action="SELL"), **args)
    assert not approved and qty == 0
    assert "not long" in reason


# --- Degenerate inputs --------------------------------------------------------

def test_zero_price_is_rejected(engine):
    args = {**BASE, "current_price": 0.0}
    approved, reason, _ = engine.validate_order("AAPL", decision(), **args)
    assert not approved and "Invalid reference price" in reason


def test_account_too_small_for_one_share(engine):
    args = {**BASE, "account_nav": 1_000.0, "cash_balance": 1_000.0, "current_price": 500.0}
    approved, reason, _ = engine.validate_order("AAPL", decision(), **args)
    assert not approved and "Insufficient allocated capital" in reason


# --- Stop-loss band -----------------------------------------------------------

class StopBroker(AlpacaBroker):
    """Exercises resolve_stop_price without constructing a live Alpaca client."""

    def __init__(self, config):
        self.config = config


@pytest.fixture
def broker():
    return StopBroker(make_config())


def test_sane_model_stop_is_honored(broker):
    assert broker.resolve_stop_price(100.0, 92.0) == 92.0


def test_stop_above_entry_falls_back_to_hard_default(broker):
    assert broker.resolve_stop_price(100.0, 105.0) == 90.0


def test_absurdly_wide_stop_falls_back_to_hard_default(broker):
    assert broker.resolve_stop_price(100.0, 40.0) == 90.0


def test_missing_stop_falls_back_to_hard_default(broker):
    assert broker.resolve_stop_price(100.0, None) == 90.0


# --- PM output parsing --------------------------------------------------------

def test_extract_json_from_fenced_block():
    raw = 'Here is my call:\n```json\n{"action": "BUY", "conviction_score": 0.9}\n```\nThanks.'
    assert MultiAgentDebateEngine.extract_json(raw)["action"] == "BUY"


def test_extract_json_from_bare_prose():
    raw = 'I recommend {"action": "HOLD", "conviction_score": 0.2} for now.'
    assert MultiAgentDebateEngine.extract_json(raw)["action"] == "HOLD"


def test_extract_json_raises_without_object():
    with pytest.raises(ValueError):
        MultiAgentDebateEngine.extract_json("No structured output here.")


def _debate_engine():
    eng = MultiAgentDebateEngine.__new__(MultiAgentDebateEngine)
    eng.min_conviction = 0.65
    return eng


DATA = {"ticker": "AAPL", "current_price": 100.0}


def test_low_conviction_buy_is_downgraded_to_hold():
    result = _debate_engine()._normalize_decision(
        {"action": "buy", "conviction_score": 0.5, "allocation_percentage": 0.08,
         "target_price": 130.0, "stop_loss_price": 90.0, "thesis_summary": "momentum"},
        DATA,
    )
    assert result["action"] == "HOLD"
    assert result["allocation_percentage"] == 0.0


def test_unknown_action_coerced_to_hold():
    result = _debate_engine()._normalize_decision(
        {"action": "ACCUMULATE", "conviction_score": 0.9, "allocation_percentage": 0.05,
         "target_price": 130.0, "stop_loss_price": 90.0, "thesis_summary": "x"},
        DATA,
    )
    assert result["action"] == "HOLD"


def test_out_of_range_scores_are_clamped():
    result = _debate_engine()._normalize_decision(
        {"action": "BUY", "conviction_score": 4.2, "allocation_percentage": 3.0,
         "target_price": 130.0, "stop_loss_price": 90.0, "thesis_summary": "x"},
        DATA,
    )
    assert result["conviction_score"] == 1.0
    assert result["allocation_percentage"] == 1.0


def test_missing_optional_fields_are_defaulted():
    result = _debate_engine()._normalize_decision(
        {"action": "BUY", "conviction_score": 0.8, "allocation_percentage": 0.05}, DATA
    )
    assert result["stop_loss_price"] == 90.0
    assert result["key_risks"] == []


# --- Config sanitation --------------------------------------------------------

def test_config_clamps_reckless_env_values(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_PERCENT", "5.0")
    monkeypatch.setenv("DAILY_LOSS_LIMIT_PERCENT", "0.0")
    cfg = Config()
    assert cfg.max_position_percent == 0.50
    assert cfg.daily_loss_limit_percent == 0.005


def test_config_ignores_unparseable_env_values(monkeypatch):
    monkeypatch.setenv("HARD_STOP_LOSS_PERCENT", "ten percent")
    assert Config().hard_stop_loss_percent == 0.10


def test_watchlist_is_normalized(monkeypatch):
    monkeypatch.setenv("WATCHLIST", " aapl , msft ,, nvda ")
    assert Config().watchlist == ["AAPL", "MSFT", "NVDA"]


# --- Controller wiring (stubbed broker + agents, no network) -------------------

class StubBroker:
    def __init__(self, nav=100_000.0, cash=100_000.0, daily_pnl=0.0):
        self.overview = {
            "nav": nav, "cash": cash, "daily_pnl_pct": daily_pnl,
            "positions": {}, "open_orders": [], "open_order_symbols": [],
            "protected_symbols": set(),
            "is_day_loss_triggered": daily_pnl < -0.03,
        }
        self.orders = []

    def get_account_overview(self):
        return dict(self.overview)

    def execute_order(self, ticker, side, qty, current_price, stop_loss_price=None):
        self.orders.append((ticker, side, qty, stop_loss_price))
        return True


class StubAgents:
    def __init__(self, verdict):
        self.verdict = verdict
        self.usage = UsageLedger()

    def run_debate(self, data):
        return dict(self.verdict), {"bull": "b", "bear": "r", "risk": "k"}


def build_trader(tmp_path, monkeypatch, broker, verdict, tickers=("AAPL",)):
    import forge_trader

    cfg = make_config(db_path=str(tmp_path / "t.db"), watchlist=list(tickers))
    trader = forge_trader.ForgeTrader.__new__(forge_trader.ForgeTrader)
    trader.config = cfg
    trader.db = forge_trader.Database(cfg.db_path)
    trader.risk_engine = ProgrammaticRiskEngine(cfg)
    trader.broker = broker
    trader.agent_engine = StubAgents(verdict)

    monkeypatch.setattr(
        forge_trader.MarketDataFetcher, "get_market_packet",
        staticmethod(lambda ticker: {
            "ticker": ticker, "current_price": 100.0, "sma_20": 99.0, "sma_50": 95.0,
            "rsi_14": 55.0, "atr_14": 2.5, "52w_high": 120.0, "52w_low": 80.0,
            "recent_volume": 1_000_000, "news_summary": "none",
        }),
    )
    return trader


def test_cycle_executes_high_conviction_buy(tmp_path, monkeypatch):
    broker = StubBroker()
    trader = build_trader(tmp_path, monkeypatch, broker, decision())
    trader.run_cycle(dry_run=False)
    assert broker.orders == [("AAPL", "BUY", 100.0, 90.0)]


def test_dry_run_places_no_orders(tmp_path, monkeypatch):
    broker = StubBroker()
    trader = build_trader(tmp_path, monkeypatch, broker, decision())
    trader.run_cycle(dry_run=True)
    assert broker.orders == []


def test_daily_loss_limit_halts_cycle(tmp_path, monkeypatch):
    broker = StubBroker(daily_pnl=-0.05)
    trader = build_trader(tmp_path, monkeypatch, broker, decision())
    trader.run_cycle(dry_run=False)
    assert broker.orders == []


def test_cycle_records_risk_outcome_in_audit_db(tmp_path, monkeypatch):
    import sqlite3

    broker = StubBroker()
    trader = build_trader(tmp_path, monkeypatch, broker, decision(conviction=0.10))
    trader.run_cycle(dry_run=False)
    row = sqlite3.connect(trader.config.db_path).execute(
        "SELECT ticker, risk_approved, risk_reason FROM agent_decisions"
    ).fetchone()
    assert row[0] == "AAPL" and row[1] == 0
    assert "below minimum threshold" in row[2]


# --- Model routing & capability profiles --------------------------------------

def test_default_model_is_opus_5(monkeypatch):
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    monkeypatch.delenv("ANALYST_MODEL", raising=False)
    monkeypatch.delenv("PM_MODEL", raising=False)
    cfg = Config()
    assert cfg.claude_model == "claude-opus-5"
    assert cfg.analyst_model == "claude-opus-5"
    assert cfg.pm_model == "claude-opus-5"


def test_per_role_models_override_the_shared_default(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("PM_MODEL", "claude-opus-5")
    cfg = Config()
    assert cfg.analyst_model == "claude-sonnet-5"
    assert cfg.pm_model == "claude-opus-5"


def test_invalid_effort_falls_back_to_high(monkeypatch):
    monkeypatch.setenv("CLAUDE_EFFORT", "turbo")
    assert Config().effort == "high"


def test_cli_model_flag_sets_every_role(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5")
    cfg = Config()
    apply_model_overrides(cfg, SimpleNamespace(
        model="claude-opus-4-8", analyst_model=None, pm_model=None, effort=None))
    assert cfg.analyst_model == "claude-opus-4-8"
    assert cfg.pm_model == "claude-opus-4-8"


def test_cli_pm_model_flag_wins_over_model_flag():
    cfg = make_config()
    apply_model_overrides(cfg, SimpleNamespace(
        model="claude-sonnet-5", analyst_model=None, pm_model="claude-opus-5", effort="xhigh"))
    assert cfg.analyst_model == "claude-sonnet-5"
    assert cfg.pm_model == "claude-opus-5"
    assert cfg.effort == "xhigh"


def test_opus_models_are_in_the_catalog():
    for model_id in ("claude-opus-5", "claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"):
        assert model_id in MODEL_CATALOG


def test_unknown_model_gets_conservative_profile():
    profile = get_model_profile("claude-something-unreleased")
    assert not profile.adaptive_thinking
    assert not profile.effort
    assert not profile.server_side_fallbacks


# --- Request construction per model -------------------------------------------

def debate_engine(analyst="claude-opus-5", pm="claude-opus-5", effort="high"):
    eng = MultiAgentDebateEngine.__new__(MultiAgentDebateEngine)
    eng.analyst_model, eng.pm_model = analyst, pm
    eng.effort, eng.min_conviction = effort, 0.65
    eng.analyst_max_tokens = eng.pm_max_tokens = 8000
    eng.usage = UsageLedger()
    return eng


def build(model, want_json_schema=False, effort="high"):
    eng = debate_engine(effort=effort)
    features = eng.supported_features(model, want_json_schema)
    return eng.build_request(model, "sys", "user", 8000, features), features


def test_opus_5_request_uses_adaptive_thinking_and_effort():
    request, _ = build("claude-opus-5")
    assert request["thinking"] == {"type": "adaptive"}
    assert request["output_config"]["effort"] == "high"


def test_opus_5_request_enables_server_side_fallbacks():
    request, features = build("claude-opus-5")
    assert "fallbacks" in features
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]


def test_opus_4_8_gets_thinking_but_not_fallbacks():
    request, features = build("claude-opus-4-8")
    assert request["thinking"] == {"type": "adaptive"}
    assert "fallbacks" not in features
    assert "betas" not in request


def test_haiku_request_omits_thinking_and_effort():
    """Haiku 4.5 rejects adaptive thinking and output_config.effort outright."""
    request, _ = build("claude-haiku-4-5")
    assert "thinking" not in request
    assert "output_config" not in request


def test_budget_tokens_is_never_sent():
    for model in MODEL_CATALOG:
        request, _ = build(model)
        assert "budget_tokens" not in json.dumps(request.get("thinking", {}))


def test_pm_request_carries_the_decision_json_schema():
    request, _ = build("claude-opus-5", want_json_schema=True)
    fmt = request["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"]["properties"]["action"]["enum"] == ["BUY", "SELL", "HOLD"]
    assert fmt["schema"]["additionalProperties"] is False


def test_effort_level_is_propagated():
    request, _ = build("claude-opus-5", effort="max")
    assert request["output_config"]["effort"] == "max"


# --- Graceful degradation on a rejected feature -------------------------------

class RejectingMessages:
    """Rejects requests carrying a named key, then succeeds."""

    def __init__(self, reject_key, response):
        self.reject_key, self.response = reject_key, response
        self.attempts = []

    def create(self, **request):
        self.attempts.append(request)
        if self.reject_key in request:
            raise anthropic.BadRequestError(
                message=f"{self.reject_key} not supported",
                response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com")),
                body=None,
            )
        return self.response


def text_response(text, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        stop_details=None,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
    )


def test_rejected_fallbacks_are_dropped_and_the_call_succeeds():
    eng = debate_engine()
    stable = RejectingMessages("never", text_response("ok"))
    beta = RejectingMessages("fallbacks", text_response("unused"))
    eng.client = SimpleNamespace(messages=stable, beta=SimpleNamespace(messages=beta))

    assert eng._call_claude("sys", "user", model="claude-opus-5", max_tokens=8000) == "ok"
    assert len(beta.attempts) == 1          # tried once with fallbacks
    assert "fallbacks" not in stable.attempts[0]


def test_degradation_stops_at_a_plain_request():
    """A model that rejects everything still gets one bare request before failing."""
    eng = debate_engine()
    rejecting = RejectingMessages("model", text_response("never"))  # rejects unconditionally
    eng.client = SimpleNamespace(messages=rejecting, beta=SimpleNamespace(messages=rejecting))

    with pytest.raises(RuntimeError):
        eng._call_claude("sys", "user", model="claude-opus-5", max_tokens=8000)
    assert "thinking" not in rejecting.attempts[-1]
    assert "output_config" not in rejecting.attempts[-1]


def test_refusal_stop_reason_is_raised():
    eng = debate_engine()
    refusal = text_response("", stop_reason="refusal")
    refusal.stop_details = SimpleNamespace(category="cyber")
    ok = RejectingMessages("never", refusal)
    eng.client = SimpleNamespace(messages=ok, beta=SimpleNamespace(messages=ok))

    with pytest.raises(forge_trader_module.ModelRefusal):
        eng._call_claude("sys", "user", model="claude-opus-5", max_tokens=8000)


# --- Cost accounting ----------------------------------------------------------

def test_usage_ledger_prices_opus_5_tokens():
    ledger = UsageLedger()
    ledger.record("claude-opus-5", SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000))
    assert ledger.cost_usd == pytest.approx(5.00 + 2.50)


def test_usage_ledger_prices_sonnet_lower_than_opus():
    opus, sonnet = UsageLedger(), UsageLedger()
    usage = SimpleNamespace(input_tokens=500_000, output_tokens=50_000)
    opus.record("claude-opus-5", usage)
    sonnet.record("claude-sonnet-5", usage)
    assert sonnet.cost_usd < opus.cost_usd


def test_usage_ledger_ignores_unknown_model_pricing():
    ledger = UsageLedger()
    ledger.record("claude-unreleased", SimpleNamespace(input_tokens=1_000_000, output_tokens=1_000_000))
    assert ledger.cost_usd == 0.0
    assert ledger.calls == 1


# --- Full debate routing (stubbed API) ----------------------------------------

class RecordingMessages:
    """Returns the PM verdict for schema-bearing requests, prose otherwise."""

    def __init__(self, verdict):
        self.verdict, self.calls = verdict, []

    def create(self, **request):
        self.calls.append(request)
        wants_json = "format" in request.get("output_config", {})
        return text_response(json.dumps(self.verdict) if wants_json else "argument text")


def test_debate_routes_analysts_and_pm_to_their_own_models():
    verdict = {"action": "BUY", "conviction_score": 0.82, "allocation_percentage": 0.06,
               "target_price": 128.5, "stop_loss_price": 91.0,
               "thesis_summary": "Breakout.", "key_risks": ["macro"]}
    eng = debate_engine(analyst="claude-sonnet-5", pm="claude-opus-5")
    api = RecordingMessages(verdict)
    eng.client = SimpleNamespace(messages=api, beta=SimpleNamespace(messages=api))

    decision, debate = eng.run_debate({
        "ticker": "AAPL", "current_price": 100.0, "sma_20": 99.0, "sma_50": 95.0,
        "rsi_14": 55.0, "atr_14": 2.5, "52w_high": 120.0, "52w_low": 80.0,
        "recent_volume": 1_000_000, "news_summary": "none",
    })

    assert [c["model"] for c in api.calls] == ["claude-sonnet-5"] * 3 + ["claude-opus-5"]
    assert decision["action"] == "BUY" and decision["conviction_score"] == 0.82
    assert all(debate[k] for k in ("bull", "bear", "risk"))
    assert eng.usage.calls == 4 and eng.usage.cost_usd > 0


def test_only_the_pm_call_requests_structured_output():
    eng = debate_engine()
    api = RecordingMessages({"action": "HOLD", "conviction_score": 0.1, "allocation_percentage": 0.0,
                             "target_price": 100.0, "stop_loss_price": 90.0,
                             "thesis_summary": "wait", "key_risks": []})
    eng.client = SimpleNamespace(messages=api, beta=SimpleNamespace(messages=api))
    eng.run_debate({"ticker": "AAPL", "current_price": 100.0, "sma_20": 99.0, "sma_50": 95.0,
                    "rsi_14": 55.0, "atr_14": 2.5, "52w_high": 120.0, "52w_low": 80.0,
                    "recent_volume": 1, "news_summary": "none"})
    schema_flags = ["format" in c.get("output_config", {}) for c in api.calls]
    assert schema_flags == [False, False, False, True]
