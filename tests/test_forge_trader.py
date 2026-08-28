"""Unit tests for the non-networked core: risk guardrails, stop sizing, and PM parsing."""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forge_trader import (  # noqa: E402
    AlpacaBroker,
    Config,
    MultiAgentDebateEngine,
    ProgrammaticRiskEngine,
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
