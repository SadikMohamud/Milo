#!/usr/bin/env python3
"""
================================================================================
FORGE-TRADER: Autonomous Multi-Agent Paper Trading Engine
================================================================================

Architecture Overview:
- Pre-Market Data Ingestion: yfinance (Pricing, Indicators, News)
- Multi-Agent Debate Engine: Anthropic Claude (Bull, Bear, Risk, PM), model-selectable
  per role: Opus 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5 / Fable 5
- Programmatic Risk Engine: Hard limits on sizing, cash buffer, stop-loss
- Execution: Alpaca Paper Trading API (alpaca-py)
- Storage & Audit: SQLite (decisions, executions, system events)
- Automation: APScheduler for automated pre-market background execution

Installation & Quickstart:
    1. Install dependencies:
       pip install -r requirements.txt

    2. Create a .env file in the same directory (see .env.example):
       ALPACA_API_KEY="your_alpaca_paper_key"
       ALPACA_SECRET_KEY="your_alpaca_paper_secret"
       ANTHROPIC_API_KEY="your_anthropic_api_key"
       ALPACA_PAPER="True"
       WATCHLIST="AAPL,MSFT,NVDA,AMZN,GOOGL"

    3. Usage CLI:
       python forge_trader.py --dry-run          # Test agent debate without placing trades
       python forge_trader.py --run-once         # Execute one cycle immediately
       python forge_trader.py --reconcile        # Attach missing protective stop-losses
       python forge_trader.py --schedule         # Run background daemon for pre-market daily
       python forge_trader.py --status           # Inspect account & open positions
       python forge_trader.py --models           # List models, pricing & agent routing
       python forge_trader.py --run-once --model claude-opus-5   # Route all agents to Opus 5
       python forge_trader.py --setup            # View PM2 / autostart instructions

================================================================================
"""

import os
import sys
import json
import math
import time
import logging
import sqlite3
import argparse
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Core Third-Party Dependencies
try:
    import pandas as pd
    import numpy as np
    import yfinance as yf
    from pydantic import BaseModel, Field, ValidationError
    import anthropic
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        StopOrderRequest,
        GetOrdersRequest,
    )
    from alpaca.trading.enums import (
        OrderSide,
        TimeInForce,
        QueryOrderStatus,
    )
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError as e:
    print(f"\n[ERROR] Missing required library: {e}")
    print("Run: pip install -r requirements.txt\n")
    sys.exit(1)


# ==============================================================================
# 1. CONFIGURATION & ENVIRONMENT
# ==============================================================================

def load_env_file(filepath: str = ".env") -> None:
    """Minimal standalone .env file loader (does not override real env vars)."""
    env_path = Path(filepath)
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip("'\"")
            os.environ.setdefault(key.strip(), val)


load_env_file()


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"[WARN] {key}='{raw}' is not a number; falling back to {default}")
        return default


def _env_int(key: str, default: int) -> int:
    return int(_env_float(key, float(default)))


def _env_watchlist() -> List[str]:
    raw = os.getenv("WATCHLIST", "AAPL,MSFT,NVDA,AMZN,GOOGL")
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


VALID_EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}


@dataclass
class Config:
    """Runtime configuration. Values are read from the environment on instantiation."""

    alpaca_api_key: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    alpaca_secret_key: str = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", ""))
    alpaca_paper: bool = field(default_factory=lambda: os.getenv("ALPACA_PAPER", "True").lower() == "true")
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    # Model routing. claude_model is the default for every agent; the analyst and
    # PM roles can be pointed at different models (e.g. Sonnet 5 analysts feeding
    # an Opus 5 portfolio manager).
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-5"))
    analyst_model: str = field(default_factory=lambda: os.getenv("ANALYST_MODEL", ""))
    pm_model: str = field(default_factory=lambda: os.getenv("PM_MODEL", ""))
    effort: str = field(default_factory=lambda: os.getenv("CLAUDE_EFFORT", "high"))
    analyst_max_tokens: int = field(default_factory=lambda: _env_int("ANALYST_MAX_TOKENS", 8000))
    pm_max_tokens: int = field(default_factory=lambda: _env_int("PM_MAX_TOKENS", 8000))
    watchlist: List[str] = field(default_factory=_env_watchlist)

    # Risk parameters (fractions, not percentages)
    max_position_percent: float = field(default_factory=lambda: _env_float("MAX_POSITION_PERCENT", 0.10))
    min_cash_buffer_percent: float = field(default_factory=lambda: _env_float("MIN_CASH_BUFFER_PERCENT", 0.20))
    hard_stop_loss_percent: float = field(default_factory=lambda: _env_float("HARD_STOP_LOSS_PERCENT", 0.10))
    daily_loss_limit_percent: float = field(default_factory=lambda: _env_float("DAILY_LOSS_LIMIT_PERCENT", 0.03))
    min_conviction: float = field(default_factory=lambda: _env_float("MIN_CONVICTION", 0.65))

    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "forge_trader.db"))

    # Scheduling (US/Eastern)
    scheduled_hour_est: int = field(default_factory=lambda: _env_int("SCHEDULED_HOUR_EST", 8))
    scheduled_min_est: int = field(default_factory=lambda: _env_int("SCHEDULED_MIN_EST", 30))
    reconcile_hour_est: int = field(default_factory=lambda: _env_int("RECONCILE_HOUR_EST", 10))
    reconcile_min_est: int = field(default_factory=lambda: _env_int("RECONCILE_MIN_EST", 0))

    # Execution tuning
    fill_wait_seconds: int = field(default_factory=lambda: _env_int("FILL_WAIT_SECONDS", 20))

    def __post_init__(self):
        # Guardrails on the guardrails: nonsensical env values must not widen risk.
        self.max_position_percent = _clamp(self.max_position_percent, 0.005, 0.50)
        self.min_cash_buffer_percent = _clamp(self.min_cash_buffer_percent, 0.0, 0.95)
        self.hard_stop_loss_percent = _clamp(self.hard_stop_loss_percent, 0.01, 0.50)
        self.daily_loss_limit_percent = _clamp(self.daily_loss_limit_percent, 0.005, 0.50)
        self.min_conviction = _clamp(self.min_conviction, 0.0, 1.0)
        self.fill_wait_seconds = max(0, self.fill_wait_seconds)

        # Per-role models fall back to the shared default.
        self.analyst_model = self.analyst_model or self.claude_model
        self.pm_model = self.pm_model or self.claude_model

        if self.effort not in VALID_EFFORT_LEVELS:
            print(f"[WARN] CLAUDE_EFFORT='{self.effort}' is not one of {sorted(VALID_EFFORT_LEVELS)}; using 'high'")
            self.effort = "high"

        self.analyst_max_tokens = max(1024, self.analyst_max_tokens)
        self.pm_max_tokens = max(1024, self.pm_max_tokens)

    def describe_models(self) -> str:
        if self.analyst_model == self.pm_model:
            return f"{self.analyst_model} (all agents), effort={self.effort}"
        return f"analysts={self.analyst_model}, PM={self.pm_model}, effort={self.effort}"


# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("forge_trader.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("FORGE-TRADER")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==============================================================================
# 2. SQLITE AUDIT DATABASE
# ==============================================================================

class Database:
    """Manages SQLite storage for debate transcripts, decisions, and trade logs."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL,
                    conviction_score REAL NOT NULL,
                    allocation_percentage REAL NOT NULL,
                    target_price REAL,
                    stop_loss_price REAL,
                    current_price REAL,
                    bull_thesis TEXT,
                    bear_thesis TEXT,
                    risk_assessment TEXT,
                    pm_summary TEXT,
                    key_risks TEXT,
                    risk_approved INTEGER,
                    risk_reason TEXT,
                    approved_qty REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    side TEXT NOT NULL,
                    qty REAL NOT NULL,
                    order_type TEXT NOT NULL,
                    alpaca_order_id TEXT,
                    status TEXT NOT NULL,
                    execution_notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON agent_decisions(ticker)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_executions_ticker ON trade_executions(ticker)")
            conn.commit()

    def save_decision(
        self,
        ticker: str,
        decision: Dict[str, Any],
        debate: Dict[str, str],
        current_price: float,
    ) -> int:
        """Persists the debate + verdict. Returns the row id for later risk annotation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_decisions (
                    timestamp, ticker, action, conviction_score, allocation_percentage,
                    target_price, stop_loss_price, current_price,
                    bull_thesis, bear_thesis, risk_assessment, pm_summary, key_risks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                _utc_now(),
                ticker,
                decision.get("action", "HOLD"),
                decision.get("conviction_score", 0.0),
                decision.get("allocation_percentage", 0.0),
                decision.get("target_price", 0.0),
                decision.get("stop_loss_price", 0.0),
                current_price,
                debate.get("bull", ""),
                debate.get("bear", ""),
                debate.get("risk", ""),
                decision.get("thesis_summary", ""),
                json.dumps(decision.get("key_risks", [])),
            ))
            conn.commit()
            return int(cursor.lastrowid)

    def record_risk_outcome(self, decision_id: int, approved: bool, reason: str, qty: float):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE agent_decisions SET risk_approved = ?, risk_reason = ?, approved_qty = ? WHERE id = ?",
                (1 if approved else 0, reason, qty, decision_id),
            )
            conn.commit()

    def save_execution(
        self,
        ticker: str,
        side: str,
        qty: float,
        order_type: str,
        order_id: str,
        status: str,
        notes: str,
    ):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO trade_executions (
                    timestamp, ticker, side, qty, order_type, alpaca_order_id, status, execution_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (_utc_now(), ticker, side, qty, order_type, order_id, status, notes))
            conn.commit()

    def log_event(self, level: str, event: str, details: str = ""):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO system_events (timestamp, level, event, details) VALUES (?, ?, ?, ?)",
                (_utc_now(), level, event, details),
            )
            conn.commit()


# ==============================================================================
# 3. MARKET DATA FETCHER (PRICE, INDICATORS, NEWS)
# ==============================================================================

class MarketDataFetcher:
    """Ingests historical technicals & headline sentiment via yfinance."""

    MIN_BARS = 60  # enough history for a meaningful SMA-50

    @staticmethod
    def _summarize_news(stock: "yf.Ticker") -> str:
        """yfinance has shipped two news payload shapes; tolerate both."""
        try:
            raw_news = stock.news or []
        except Exception as e:  # network hiccup or upstream schema change
            logger.warning(f"News fetch failed: {e}")
            return "No recent headlines available."

        items = []
        for entry in raw_news[:5]:
            if not isinstance(entry, dict):
                continue
            content = entry.get("content")
            if isinstance(content, dict):
                title = content.get("title", "")
                provider = content.get("provider") or {}
                publisher = provider.get("displayName", "") if isinstance(provider, dict) else ""
            else:
                title = entry.get("title", "")
                publisher = entry.get("publisher", "")
            if title:
                items.append(f"- [{publisher or 'Unknown'}] {title}")
        return "\n".join(items) if items else "No recent headlines available."

    @staticmethod
    def get_market_packet(ticker: str) -> Optional[Dict[str, Any]]:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval="1d")
            if df.empty or len(df) < MarketDataFetcher.MIN_BARS:
                logger.warning(f"Insufficient history data returned for {ticker}")
                return None

            current_price = float(df["Close"].iloc[-1])
            sma_20 = float(df["Close"].rolling(window=20).mean().iloc[-1])
            sma_50 = float(df["Close"].rolling(window=50).mean().iloc[-1])

            # Calculate 14-day RSI
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            rsi_14 = float(100 - (100 / (1 + rs)).iloc[-1])

            # Calculate 14-day ATR (Average True Range)
            high_low = df["High"] - df["Low"]
            high_cp = np.abs(df["High"] - df["Close"].shift())
            low_cp = np.abs(df["Low"] - df["Close"].shift())
            tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            atr_14 = float(tr.rolling(window=14).mean().iloc[-1])

            if not all(math.isfinite(v) for v in (current_price, sma_20, sma_50, rsi_14, atr_14)):
                logger.warning(f"Non-finite indicator computed for {ticker}; skipping")
                return None
            if current_price <= 0:
                logger.warning(f"Invalid price for {ticker}: {current_price}")
                return None

            # Trailing 52-week range from the same one-year window
            window = df.tail(252)

            return {
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "sma_20": round(sma_20, 2),
                "sma_50": round(sma_50, 2),
                "rsi_14": round(rsi_14, 2),
                "atr_14": round(atr_14, 2),
                "52w_high": round(float(window["High"].max()), 2),
                "52w_low": round(float(window["Low"].min()), 2),
                "recent_volume": int(df["Volume"].iloc[-1]),
                "news_summary": MarketDataFetcher._summarize_news(stock),
            }
        except Exception as e:
            logger.error(f"Failed to fetch market data for {ticker}: {e}")
            return None


# ==============================================================================
# 4. MODEL CATALOG & CAPABILITY PROFILES
# ==============================================================================

@dataclass(frozen=True)
class ModelProfile:
    """What a given Claude model supports, and what it costs to run."""

    label: str
    input_price: float          # USD per 1M input tokens
    output_price: float         # USD per 1M output tokens
    context: str
    adaptive_thinking: bool     # accepts thinking={"type": "adaptive"}
    effort: bool                # accepts output_config.effort
    server_side_fallbacks: bool # accepts the server-side refusal fallback beta


# Pricing and capabilities as published; see README for the source table.
MODEL_CATALOG: Dict[str, ModelProfile] = {
    "claude-opus-5":     ModelProfile("Claude Opus 5",     5.00, 25.00, "1M",   True,  True,  True),
    "claude-opus-4-8":   ModelProfile("Claude Opus 4.8",   5.00, 25.00, "1M",   True,  True,  False),
    "claude-opus-4-7":   ModelProfile("Claude Opus 4.7",   5.00, 25.00, "1M",   True,  True,  False),
    "claude-opus-4-6":   ModelProfile("Claude Opus 4.6",   5.00, 25.00, "1M",   True,  True,  False),
    "claude-fable-5":    ModelProfile("Claude Fable 5",   10.00, 50.00, "1M",   True,  True,  True),
    "claude-sonnet-5":   ModelProfile("Claude Sonnet 5",   2.00, 10.00, "1M",   True,  True,  False),
    "claude-sonnet-4-6": ModelProfile("Claude Sonnet 4.6", 3.00, 15.00, "1M",   True,  True,  False),
    "claude-haiku-4-5":  ModelProfile("Claude Haiku 4.5",  1.00,  5.00, "200K", False, False, False),
}

# Conservative assumptions for a model released after this catalog was written:
# send the plainest possible request rather than risk a 400 on every call.
UNKNOWN_MODEL_PROFILE = ModelProfile("Unrecognized model", 0.0, 0.0, "unknown", False, False, False)


def get_model_profile(model_id: str) -> ModelProfile:
    return MODEL_CATALOG.get(model_id, UNKNOWN_MODEL_PROFILE)


def print_model_catalog(config: "Config"):
    print("\n" + "=" * 78)
    print("                    MODELS AVAILABLE TO FORGE-TRADER")
    print("=" * 78)
    print(f"  {'Model ID':<20} {'Name':<20} {'Context':<9} {'$/1M in':>8} {'$/1M out':>9}")
    print("-" * 78)
    for model_id, p in MODEL_CATALOG.items():
        print(f"  {model_id:<20} {p.label:<20} {p.context:<9} {p.input_price:>8.2f} {p.output_price:>9.2f}")
    print("-" * 78)
    print(f"  Analyst agents (Bull/Bear/Risk): {config.analyst_model}")
    print(f"  Portfolio Manager (decides):     {config.pm_model}")
    print(f"  Reasoning effort:                {config.effort}")
    print("\n  Override with --model / --analyst-model / --pm-model, or set")
    print("  CLAUDE_MODEL, ANALYST_MODEL, PM_MODEL, CLAUDE_EFFORT in .env")
    print("=" * 78 + "\n")


def apply_model_overrides(config: "Config", args: Any) -> None:
    """Applies --model / --analyst-model / --pm-model / --effort on top of the env config."""
    if getattr(args, "model", None):
        config.claude_model = args.model
        config.analyst_model = args.model
        config.pm_model = args.model
    if getattr(args, "analyst_model", None):
        config.analyst_model = args.analyst_model
    if getattr(args, "pm_model", None):
        config.pm_model = args.pm_model
    if getattr(args, "effort", None):
        config.effort = args.effort

    # An unknown ID is allowed through (models ship faster than this catalog), but
    # it runs with every optional request feature disabled, so say so loudly.
    for role, model_id in (("analyst", config.analyst_model), ("portfolio manager", config.pm_model)):
        if model_id not in MODEL_CATALOG:
            logger.warning(
                f"Unrecognized {role} model '{model_id}'. It will be called with no thinking, "
                f"effort, or structured-output settings, and its cost cannot be estimated. "
                f"Known models: {', '.join(MODEL_CATALOG)}"
            )


class UsageLedger:
    """Accumulates token spend so a daily cycle's API cost is visible in the log."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.calls = 0

    def record(self, model: str, usage: Any):
        profile = get_model_profile(model)
        inp = int(getattr(usage, "input_tokens", 0) or 0)
        out = int(getattr(usage, "output_tokens", 0) or 0)
        # Cached reads are billed at a fraction of the input rate; counting them at
        # full rate keeps this an upper bound rather than an understatement.
        inp += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        inp += int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        self.input_tokens += inp
        self.output_tokens += out
        self.cost_usd += (inp / 1_000_000) * profile.input_price + (out / 1_000_000) * profile.output_price
        self.calls += 1

    def summary(self) -> str:
        return (
            f"{self.calls} API calls | {self.input_tokens:,} in / {self.output_tokens:,} out tokens "
            f"| ~${self.cost_usd:,.2f}"
        )


# ==============================================================================
# 5. MULTI-AGENT DEBATE ENGINE (ANTHROPIC CLAUDE)
# ==============================================================================

class DecisionSchema(BaseModel):
    """Contract the Portfolio Manager agent must satisfy before anything reaches the broker."""

    action: str = Field(description="Must be 'BUY', 'SELL', or 'HOLD'")
    conviction_score: float = Field(description="Confidence rating from 0.0 (none) to 1.0 (absolute)")
    allocation_percentage: float = Field(description="Recommended portfolio allocation fraction between 0.0 and 0.10")
    target_price: float = Field(description="Projected upside target price")
    stop_loss_price: float = Field(description="Strict stop-loss price (8-12% below entry)")
    thesis_summary: str = Field(description="Concise 2-3 sentence executive summary of the trade rationale")
    key_risks: List[str] = Field(default_factory=list, description="Top 2 downside risk factors")


# Server-enforced shape for the PM verdict. Cheaper and far more reliable than
# asking for JSON in the prompt and parsing whatever comes back.
DECISION_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
        "conviction_score": {"type": "number"},
        "allocation_percentage": {"type": "number"},
        "target_price": {"type": "number"},
        "stop_loss_price": {"type": "number"},
        "thesis_summary": {"type": "string"},
        "key_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "action", "conviction_score", "allocation_percentage",
        "target_price", "stop_loss_price", "thesis_summary", "key_risks",
    ],
    "additionalProperties": False,
}


class ModelRefusal(RuntimeError):
    """Raised when a safety classifier declines the request outright."""


class MultiAgentDebateEngine:
    """Orchestrates adversarial Bull vs Bear debate, Risk check, and PM decision."""

    MAX_RETRIES = 3

    # Order in which optional request features are surrendered if the API rejects
    # the request. Least essential first; the plain request is always reachable.
    DEGRADE_ORDER = ("fallbacks", "json_schema", "effort", "thinking")

    def __init__(
        self,
        api_key: str,
        analyst_model: str,
        pm_model: str,
        effort: str = "high",
        min_conviction: float = 0.65,
        analyst_max_tokens: int = 8000,
        pm_max_tokens: int = 8000,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.analyst_model = analyst_model
        self.pm_model = pm_model
        self.effort = effort
        self.min_conviction = min_conviction
        self.analyst_max_tokens = analyst_max_tokens
        self.pm_max_tokens = pm_max_tokens
        self.usage = UsageLedger()

    # -- request construction --------------------------------------------------

    def supported_features(self, model: str, want_json_schema: bool) -> set:
        profile = get_model_profile(model)
        features = set()
        if profile.adaptive_thinking:
            features.add("thinking")
        if profile.effort:
            features.add("effort")
        if profile.server_side_fallbacks:
            features.add("fallbacks")
        if want_json_schema:
            features.add("json_schema")
        return features

    def build_request(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        max_tokens: int,
        features: set,
    ) -> Dict[str, Any]:
        request: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }
        if "thinking" in features:
            # budget_tokens is rejected on current models; adaptive is the on-mode.
            request["thinking"] = {"type": "adaptive"}
        output_config: Dict[str, Any] = {}
        if "effort" in features:
            output_config["effort"] = self.effort
        if "json_schema" in features:
            output_config["format"] = {"type": "json_schema", "schema": DECISION_JSON_SCHEMA}
        if output_config:
            request["output_config"] = output_config
        if "fallbacks" in features:
            # If a classifier declines, the API re-runs the turn on a fallback model
            # inside the same call rather than returning nothing.
            request["betas"] = ["server-side-fallback-2026-07-01"]
            request["fallbacks"] = "default"
        return request

    def _send(self, request: Dict[str, Any], use_beta: bool) -> Any:
        endpoint = self.client.beta.messages if use_beta else self.client.messages
        return endpoint.create(**request)

    def _call_claude(
        self,
        system_prompt: str,
        user_content: str,
        model: str,
        max_tokens: int,
        want_json_schema: bool = False,
    ) -> str:
        features = self.supported_features(model, want_json_schema)
        attempt = 0
        last_error: Optional[Exception] = None

        while True:
            request = self.build_request(model, system_prompt, user_content, max_tokens, features)
            try:
                response = self._send(request, use_beta="fallbacks" in features)
            except anthropic.BadRequestError as e:
                dropped = next((f for f in self.DEGRADE_ORDER if f in features), None)
                if dropped is None:
                    raise RuntimeError(f"Claude rejected the request for {model}: {e}") from e
                features.discard(dropped)
                logger.warning(
                    f"{model} rejected '{dropped}' ({e}); retrying without it. "
                    f"Remaining features: {sorted(features) or 'none'}"
                )
                continue
            except (anthropic.RateLimitError, anthropic.APIStatusError,
                    anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
                last_error = e
                attempt += 1
                if attempt >= self.MAX_RETRIES:
                    raise RuntimeError(f"Claude API unavailable after {self.MAX_RETRIES} attempts: {e}") from e
                backoff = 2 ** attempt
                logger.warning(f"Claude call failed (attempt {attempt}/{self.MAX_RETRIES}): {e}. Retrying in {backoff}s")
                time.sleep(backoff)
                continue

            self.usage.record(model, getattr(response, "usage", None))
            return self._read_text(response, model)

        raise RuntimeError(f"Claude API unavailable: {last_error}")  # pragma: no cover

    @staticmethod
    def _read_text(response: Any, model: str) -> str:
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            raise ModelRefusal(f"{model} declined the request (category: {category})")
        if stop_reason == "max_tokens":
            logger.warning(f"{model} hit max_tokens; output may be truncated")
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()

    # -- parsing ---------------------------------------------------------------

    @staticmethod
    def extract_json(raw: str) -> Dict[str, Any]:
        """Pulls a JSON object out of a model response, fenced or otherwise.

        Structured output makes this the fallback path, not the primary one.
        """
        text = (raw or "").strip()
        if "```" in text:
            fenced = text.split("```")
            for chunk in fenced[1:]:
                candidate = chunk.split("```")[0]
                if candidate.lstrip().lower().startswith("json"):
                    candidate = candidate.lstrip()[4:]
                candidate = candidate.strip()
                if candidate.startswith("{"):
                    text = candidate
                    break
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON object found in model response")
        return json.loads(text[start:end + 1])

    def _normalize_decision(self, payload: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates against DecisionSchema and re-applies the conviction rule in code."""
        payload = dict(payload)
        payload["action"] = str(payload.get("action", "HOLD")).strip().upper()
        payload.setdefault("target_price", data["current_price"])
        payload.setdefault("stop_loss_price", round(data["current_price"] * 0.90, 2))
        payload.setdefault("thesis_summary", "")
        if isinstance(payload.get("key_risks"), str):
            payload["key_risks"] = [payload["key_risks"]]

        decision = DecisionSchema(**payload).model_dump()

        if decision["action"] not in {"BUY", "SELL", "HOLD"}:
            logger.warning(f"Unrecognized action '{decision['action']}' for {data['ticker']}; coercing to HOLD")
            decision["action"] = "HOLD"

        decision["conviction_score"] = _clamp(decision["conviction_score"], 0.0, 1.0)
        decision["allocation_percentage"] = _clamp(decision["allocation_percentage"], 0.0, 1.0)

        # The PM prompt states this rule; enforcing it here means a disobedient
        # model cannot open a low-conviction position.
        if decision["action"] == "BUY" and decision["conviction_score"] < self.min_conviction:
            decision["action"] = "HOLD"
            decision["allocation_percentage"] = 0.0
            decision["thesis_summary"] = (
                f"[Auto-downgraded to HOLD: conviction {decision['conviction_score']:.2f} "
                f"< {self.min_conviction:.2f}] {decision['thesis_summary']}"
            )
        return decision

    @staticmethod
    def fallback_decision(data: Dict[str, Any], reason: str) -> Dict[str, Any]:
        return {
            "action": "HOLD",
            "conviction_score": 0.0,
            "allocation_percentage": 0.0,
            "target_price": data["current_price"],
            "stop_loss_price": round(data["current_price"] * 0.90, 2),
            "thesis_summary": f"Defaulted to HOLD: {reason}",
            "key_risks": [reason],
        }

    # -- the debate ------------------------------------------------------------

    def run_debate(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        context = f"""
Ticker: {data['ticker']}
Current Price: ${data['current_price']}
SMA 20: ${data['sma_20']} | SMA 50: ${data['sma_50']}
14-Day RSI: {data['rsi_14']}
14-Day ATR: ${data['atr_14']}
52-Week Range: ${data['52w_low']} - ${data['52w_high']}
Recent News:
{data['news_summary']}
"""
        brevity = " Keep your argument under 300 words."
        debate_log = {"bull": "", "bear": "", "risk": ""}

        def analyst(system_prompt: str, user_content: str) -> str:
            return self._call_claude(
                system_prompt + brevity, user_content,
                model=self.analyst_model, max_tokens=self.analyst_max_tokens,
            )

        try:
            # 1. Bull Analyst Agent
            debate_log["bull"] = analyst(
                "You are an aggressive Growth & Momentum Analyst. Highlight upward catalysts, "
                "technical breakouts, and bullish market drivers.",
                f"Build the maximum Bull Case for:\n{context}",
            )

            # 2. Bear Analyst Agent (Adversarial)
            debate_log["bear"] = analyst(
                "You are a skeptical Short-Seller & Risk Auditor. Identify valuation traps, overbought "
                "indicators, macroeconomic headwinds, and downside vulnerabilities.",
                f"Debate and dismantle this Bull case for {data['ticker']}.\n"
                f"Market Context:\n{context}\nBull Argument:\n{debate_log['bull']}",
            )

            # 3. Risk Committee Agent
            debate_log["risk"] = analyst(
                "You are the Chief Risk Officer. Review volatility (ATR), RSI overextension, and market "
                "regime risks. Formulate stop-loss boundaries.",
                f"Evaluate risk for {data['ticker']}.\nBull:\n{debate_log['bull']}\n"
                f"Bear:\n{debate_log['bear']}\nTechnicals:\n{context}",
            )
        except (RuntimeError, ModelRefusal) as e:
            logger.error(f"Debate aborted for {data['ticker']}: {e}")
            return self.fallback_decision(data, "Claude API unavailable during debate"), debate_log

        # 4. Portfolio Manager Agent (Synthesizer & Structured Output)
        pm_prompt = f"""You are the Senior Portfolio Manager with final execution authority.
Synthesize the Bull, Bear, and Risk arguments into a single execution decision.
Fields: action (BUY/SELL/HOLD), conviction_score (0.0-1.0), allocation_percentage
(0.0-0.10 of portfolio), target_price, stop_loss_price (8-12% below entry),
thesis_summary (2-3 sentences), key_risks (the top 2 downside factors).
Strict Rule: If conviction_score < {self.min_conviction}, action MUST be 'HOLD' and
allocation_percentage MUST be 0.0."""

        pm_input = (
            f"Market Context:\n{context}\n\nBull Case:\n{debate_log['bull']}\n\n"
            f"Bear Case:\n{debate_log['bear']}\n\nRisk Assessment:\n{debate_log['risk']}"
        )

        try:
            pm_response = self._call_claude(
                pm_prompt, pm_input,
                model=self.pm_model, max_tokens=self.pm_max_tokens, want_json_schema=True,
            )
        except (RuntimeError, ModelRefusal) as e:
            logger.error(f"PM synthesis failed for {data['ticker']}: {e}")
            return self.fallback_decision(data, "Claude API unavailable during PM synthesis"), debate_log

        try:
            decision = self._normalize_decision(self.extract_json(pm_response), data)
        except (ValueError, ValidationError, json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse PM JSON for {data['ticker']}: {e}. Raw: {pm_response}")
            decision = self.fallback_decision(data, "Model output parsing failed")

        return decision, debate_log


# ==============================================================================
# 6. HARDCODED PROGRAMMATIC RISK ENGINE
# ==============================================================================

class ProgrammaticRiskEngine:
    """Non-LLM immutable risk guardrails enforced before touching the broker."""

    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def _position_value(position: Any) -> float:
        try:
            return abs(float(getattr(position, "market_value", 0.0) or 0.0))
        except (TypeError, ValueError):
            return 0.0

    def validate_order(
        self,
        ticker: str,
        decision: Dict[str, Any],
        current_price: float,
        account_nav: float,
        cash_balance: float,
        active_positions: Dict[str, Any],
        open_orders: List[str],
    ) -> Tuple[bool, str, float]:
        """Returns (is_approved, rejection_or_approval_reason, approved_qty)."""

        action = str(decision.get("action", "HOLD")).upper()
        conviction = float(decision.get("conviction_score", 0.0) or 0.0)
        allocation_pct = float(decision.get("allocation_percentage", 0.0) or 0.0)

        # 0. Sanity on inputs
        if current_price <= 0:
            return False, f"Invalid reference price (${current_price:.2f})", 0.0
        if account_nav <= 0:
            return False, "Account NAV is zero or negative", 0.0

        # 1. Action Check
        if action == "HOLD":
            return False, "Decision is HOLD", 0.0

        # 2. Duplicate Order Guard (pending entry orders only; protective stops are handled separately)
        if ticker in open_orders:
            return False, f"Duplicate guard: Pending order already exists for {ticker}", 0.0

        # 3. Sell Validation
        if action == "SELL":
            position = active_positions.get(ticker)
            if position is None:
                return False, f"Cannot SELL: No active position held in {ticker}", 0.0
            try:
                held_qty = float(position.qty)
            except (TypeError, ValueError):
                return False, f"Cannot SELL: Unreadable quantity on {ticker} position", 0.0
            if held_qty <= 0:
                return False, f"Cannot SELL: {ticker} position is not long ({held_qty} shares)", 0.0
            return True, f"Approved SELL of existing position ({held_qty} shares)", held_qty

        # 4. Buy Conviction Threshold
        if conviction < self.config.min_conviction:
            return False, (
                f"Conviction {conviction:.2f} is below minimum threshold {self.config.min_conviction:.2f}"
            ), 0.0

        # 5. Position Sizing Limits (cap at configured % of NAV, net of existing exposure)
        capped_allocation = min(allocation_pct, self.config.max_position_percent)
        if capped_allocation <= 0:
            return False, "Recommended allocation is 0%", 0.0

        target_capital = account_nav * capped_allocation
        existing_exposure = self._position_value(active_positions.get(ticker))
        position_headroom = (account_nav * self.config.max_position_percent) - existing_exposure
        if position_headroom <= 0:
            return False, (
                f"Concentration cap: {ticker} exposure (${existing_exposure:,.2f}) already at the "
                f"{self.config.max_position_percent*100:.1f}% NAV limit"
            ), 0.0

        # 6. Minimum Cash Buffer Guard
        required_cash_reserve = account_nav * self.config.min_cash_buffer_percent
        available_surplus_cash = cash_balance - required_cash_reserve
        if available_surplus_cash <= 0:
            return False, (
                f"Cash buffer triggered: Available cash (${cash_balance:,.2f}) is below reserve "
                f"(${required_cash_reserve:,.2f})"
            ), 0.0

        capital_to_deploy = min(target_capital, position_headroom, available_surplus_cash)
        if capital_to_deploy < current_price:
            return False, (
                f"Insufficient allocated capital (${capital_to_deploy:,.2f}) to purchase 1 share "
                f"(${current_price:,.2f})"
            ), 0.0

        shares_to_buy = math.floor(capital_to_deploy / current_price)
        if shares_to_buy <= 0:
            return False, "Calculated order quantity is 0 shares", 0.0

        return True, (
            f"Approved BUY of {shares_to_buy} shares (${shares_to_buy * current_price:,.2f})"
        ), float(shares_to_buy)


# ==============================================================================
# 7. BROKER EXECUTION ENGINE (ALPACA PAPER API)
# ==============================================================================

class AlpacaBroker:
    """Manages order submission, account state, and stop-loss attachments."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db

        if not config.alpaca_api_key or not config.alpaca_secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be configured.")

        # STRICT PAPER CHECK
        if not config.alpaca_paper:
            logger.critical("SAFETY HALT: ALPACA_PAPER is set to False. System only permits Paper Trading mode.")
            sys.exit(1)

        self.client = TradingClient(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_secret_key,
            paper=True,
        )

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _order_type(order: Any) -> str:
        raw = getattr(order, "order_type", None) or getattr(order, "type", "")
        return str(getattr(raw, "value", raw)).lower()

    @staticmethod
    def _order_side(order: Any) -> str:
        raw = getattr(order, "side", "")
        return str(getattr(raw, "value", raw)).lower()

    def _is_protective_stop(self, order: Any) -> bool:
        return "stop" in self._order_type(order) and self._order_side(order) == "sell"

    def resolve_stop_price(self, reference_price: float, suggested: Optional[float]) -> float:
        """Accepts the PM's stop only inside a sane band; otherwise uses the hard default."""
        default_stop = reference_price * (1 - self.config.hard_stop_loss_percent)
        widest = reference_price * (1 - min(0.9, self.config.hard_stop_loss_percent * 2))
        tightest = reference_price * 0.98
        try:
            candidate = float(suggested) if suggested is not None else 0.0
        except (TypeError, ValueError):
            candidate = 0.0
        if widest <= candidate <= tightest:
            return round(candidate, 2)
        return round(default_stop, 2)

    # -- account ---------------------------------------------------------------

    def get_account_overview(self) -> Dict[str, Any]:
        account = self.client.get_account()
        positions = self.client.get_all_positions()
        pos_map = {p.symbol: p for p in positions}

        open_orders = self.client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))

        # A resting GTC stop-loss must NOT look like a pending entry, or the duplicate
        # guard would permanently block every future decision on that ticker.
        pending_entry_symbols = [o.symbol for o in open_orders if not self._is_protective_stop(o)]
        protected_symbols = {o.symbol for o in open_orders if self._is_protective_stop(o)}

        nav = float(account.portfolio_value)
        cash = float(account.cash)
        last_nav = float(account.last_equity)
        daily_pnl_pct = (nav - last_nav) / last_nav if last_nav > 0 else 0.0

        return {
            "nav": nav,
            "cash": cash,
            "daily_pnl_pct": daily_pnl_pct,
            "positions": pos_map,
            "open_orders": list(open_orders),
            "open_order_symbols": pending_entry_symbols,
            "protected_symbols": protected_symbols,
            "is_day_loss_triggered": daily_pnl_pct < -self.config.daily_loss_limit_percent,
        }

    def cancel_protective_stops(self, ticker: str) -> int:
        """Releases shares reserved by resting stop orders so a SELL can fill."""
        cancelled = 0
        try:
            open_orders = self.client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
            for order in open_orders:
                if order.symbol == ticker and self._is_protective_stop(order):
                    self.client.cancel_order_by_id(order.id)
                    cancelled += 1
                    logger.info(f"[STOP CANCELLED] Released resting stop {order.id} on {ticker}")
        except Exception as e:
            logger.error(f"Failed cancelling protective stops for {ticker}: {e}")
        if cancelled:
            time.sleep(1)  # allow Alpaca to release the held quantity
        return cancelled

    def _await_fill(self, order_id: str, timeout_seconds: int) -> Optional[Any]:
        """Polls until the order fills. Returns None if still working at timeout."""
        deadline = time.time() + timeout_seconds
        order = None
        while time.time() < deadline:
            time.sleep(2)
            try:
                order = self.client.get_order_by_id(order_id)
            except Exception as e:
                logger.warning(f"Could not poll order {order_id}: {e}")
                continue
            status = str(getattr(order.status, "value", order.status)).lower()
            if status == "filled":
                return order
            if status in {"canceled", "cancelled", "expired", "rejected"}:
                logger.warning(f"Order {order_id} terminated with status '{status}'")
                return None
        return None

    # -- execution -------------------------------------------------------------

    def submit_stop_loss(self, ticker: str, qty: float, stop_price: float, note: str) -> bool:
        try:
            sl_order = self.client.submit_order(order_data=StopOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.SELL,
                stop_price=stop_price,
                time_in_force=TimeInForce.GTC,
            ))
            logger.info(f"[STOP-LOSS SET] {ticker} pegged at ${stop_price:.2f} | Order ID: {sl_order.id}")
            self.db.save_execution(
                ticker=ticker, side="SELL", qty=qty, order_type="STOP",
                order_id=str(sl_order.id), status="SUBMITTED", notes=note,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to attach stop-loss for {ticker}: {e}")
            self.db.save_execution(
                ticker=ticker, side="SELL", qty=qty, order_type="STOP",
                order_id="NONE", status="FAILED", notes=f"{note} | {e}",
            )
            return False

    def execute_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        current_price: float,
        stop_loss_price: Optional[float] = None,
    ) -> bool:
        try:
            is_buy = side.upper() == "BUY"

            # Exiting a position first requires releasing the shares its stop reserves.
            if not is_buy:
                self.cancel_protective_stops(ticker)

            order_req = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if is_buy else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            order = self.client.submit_order(order_data=order_req)
            order_id = str(order.id)
            logger.info(f"[EXECUTED] {side} {qty}x {ticker} | Order ID: {order_id}")

            self.db.save_execution(
                ticker=ticker, side=side, qty=qty, order_type="MARKET",
                order_id=order_id, status="SUBMITTED",
                notes=f"Entry market order submitted at ~${current_price:.2f}",
            )

            if not is_buy:
                return True

            # Companion hard stop-loss, sized to what actually filled.
            filled = self._await_fill(order_id, self.config.fill_wait_seconds)
            if filled is None:
                logger.warning(
                    f"[STOP DEFERRED] {ticker} entry not filled within {self.config.fill_wait_seconds}s "
                    f"(pre-market orders queue until the open). Run --reconcile after the open to attach the stop."
                )
                self.db.save_execution(
                    ticker=ticker, side="SELL", qty=qty, order_type="STOP",
                    order_id="NONE", status="DEFERRED",
                    notes="Entry unfilled at submission; stop-loss deferred to reconciliation",
                )
                return True

            filled_qty = float(filled.filled_qty or qty)
            fill_price = float(filled.filled_avg_price or current_price)
            stop_price = self.resolve_stop_price(fill_price, stop_loss_price)
            self.submit_stop_loss(
                ticker, filled_qty, stop_price,
                note=f"Companion GTC stop-loss at ${stop_price:.2f} (fill ${fill_price:.2f})",
            )
            return True
        except Exception as e:
            logger.error(f"Execution failed for {ticker}: {e}")
            self.db.save_execution(
                ticker=ticker, side=side, qty=qty, order_type="FAILED",
                order_id="NONE", status="FAILED", notes=str(e),
            )
            return False

    def reconcile_stops(self) -> int:
        """Attaches a protective stop to every long position that is currently unprotected."""
        attached = 0
        try:
            acct = self.get_account_overview()
        except Exception as e:
            logger.error(f"Reconciliation aborted; could not read account: {e}")
            return 0

        for symbol, position in acct["positions"].items():
            try:
                qty = float(position.qty)
            except (TypeError, ValueError):
                continue
            if qty <= 0 or symbol in acct["protected_symbols"]:
                continue
            reference = float(getattr(position, "current_price", 0) or getattr(position, "avg_entry_price", 0) or 0)
            if reference <= 0:
                logger.warning(f"Skipping stop reconciliation for {symbol}: no usable reference price")
                continue
            stop_price = self.resolve_stop_price(reference, None)
            logger.info(f"[RECONCILE] {symbol} is unprotected; attaching stop at ${stop_price:.2f}")
            if self.submit_stop_loss(symbol, qty, stop_price, note="Reconciliation stop-loss"):
                attached += 1

        if attached == 0:
            logger.info("[RECONCILE] All long positions already carry a protective stop.")
        self.db.log_event("INFO", "reconcile_stops", f"Attached {attached} stop-loss order(s)")
        return attached


# ==============================================================================
# 8. MASTER WORKFLOW CONTROLLER
# ==============================================================================

class ForgeTrader:
    """Master controller coordinating data ingestion, debates, risk checks, and execution."""

    def __init__(self, config: Config):
        self.config = config
        self.db = Database(config.db_path)
        self.risk_engine = ProgrammaticRiskEngine(config)
        self.broker = AlpacaBroker(config, self.db)
        self.agent_engine = MultiAgentDebateEngine(
            api_key=config.anthropic_api_key,
            analyst_model=config.analyst_model,
            pm_model=config.pm_model,
            effort=config.effort,
            min_conviction=config.min_conviction,
            analyst_max_tokens=config.analyst_max_tokens,
            pm_max_tokens=config.pm_max_tokens,
        )

    def run_cycle(self, dry_run: bool = False):
        mode = "DRY-RUN" if dry_run else "LIVE PAPER"
        logger.info(f"=== Starting FORGE-TRADER Workflow ({mode}) ===")
        logger.info(f"Models: {self.config.describe_models()}")
        self.db.log_event(
            "INFO", "cycle_start",
            f"mode={mode} watchlist={','.join(self.config.watchlist)} models={self.config.describe_models()}",
        )

        # 1. Inspect Account State
        try:
            acct = self.broker.get_account_overview()
        except Exception as e:
            logger.error(f"Aborting cycle; account state unavailable: {e}")
            self.db.log_event("ERROR", "cycle_abort", str(e))
            return

        logger.info(
            f"Account NAV: ${acct['nav']:,.2f} | Cash: ${acct['cash']:,.2f} | "
            f"Today's P&L: {acct['daily_pnl_pct']*100:.2f}%"
        )

        if acct["is_day_loss_triggered"]:
            msg = (
                f"EMERGENCY HALT: Account daily loss ({acct['daily_pnl_pct']*100:.2f}%) exceeds hard limit "
                f"(-{self.config.daily_loss_limit_percent*100:.2f}%). Halting all trades."
            )
            logger.critical(msg)
            self.db.log_event("CRITICAL", "daily_loss_halt", msg)
            return

        executed, rejected, skipped = 0, 0, 0

        # 2. Iterate Through Target Watchlist
        for ticker in self.config.watchlist:
            logger.info(f"--- Processing Candidate: {ticker} ---")
            data_packet = MarketDataFetcher.get_market_packet(ticker)
            if not data_packet:
                skipped += 1
                continue

            # Run Multi-Agent Claude Debate
            logger.info(f"Triggering Claude Multi-Agent Debate for {ticker}...")
            decision, debate_transcripts = self.agent_engine.run_debate(data_packet)

            logger.info(
                f"Verdict: {decision['action']} | Conviction: {decision['conviction_score']:.2f} | "
                f"Target: ${decision['target_price']} | SL: ${decision['stop_loss_price']}"
            )
            logger.info(f"Thesis: {decision['thesis_summary']}")

            # Save Decision to Audit Database
            decision_id = self.db.save_decision(ticker, decision, debate_transcripts, data_packet["current_price"])

            # Validate against Programmatic Guardrails
            approved, reason, qty = self.risk_engine.validate_order(
                ticker=ticker,
                decision=decision,
                current_price=data_packet["current_price"],
                account_nav=acct["nav"],
                cash_balance=acct["cash"],
                active_positions=acct["positions"],
                open_orders=acct["open_order_symbols"],
            )
            self.db.record_risk_outcome(decision_id, approved, reason, qty)

            if not approved:
                logger.info(f"[ORDER REJECTED BY GUARDRAILS] {reason}")
                rejected += 1
                continue

            logger.info(f"[ORDER APPROVED] {reason}")

            # Execute via Alpaca Paper API
            if dry_run:
                logger.info(
                    f"[DRY-RUN SIMULATION] Would execute {decision['action']} {qty}x {ticker} "
                    f"at ${data_packet['current_price']:.2f}"
                )
                executed += 1
                continue

            if self.broker.execute_order(
                ticker=ticker,
                side=decision["action"],
                qty=qty,
                current_price=data_packet["current_price"],
                stop_loss_price=decision.get("stop_loss_price"),
            ):
                executed += 1
                # Cash and exposure moved; refresh before sizing the next candidate.
                try:
                    acct = self.broker.get_account_overview()
                except Exception as e:
                    logger.error(f"Could not refresh account after {ticker}; halting cycle: {e}")
                    break
            else:
                rejected += 1

        spend = self.agent_engine.usage.summary()
        summary = f"executed={executed} rejected={rejected} skipped={skipped} | {spend}"
        logger.info(f"Agent spend this cycle: {spend}")
        logger.info(f"=== Workflow Completed ({summary}) ===")
        self.db.log_event("INFO", "cycle_complete", summary)

    def reconcile(self):
        logger.info("=== Reconciling protective stop-loss coverage ===")
        self.broker.reconcile_stops()

    def display_status(self):
        acct = self.broker.get_account_overview()
        print("\n" + "=" * 60)
        print("               FORGE-TRADER ACCOUNT STATUS")
        print("=" * 60)
        print("  Mode:                ALPACA PAPER TRADING")
        print(f"  Portfolio Value:     ${acct['nav']:,.2f}")
        print(f"  Cash Balance:        ${acct['cash']:,.2f}")
        print(f"  Day's P&L:           {acct['daily_pnl_pct']*100:.2f}%")
        print("-" * 60)
        print("  Active Positions:")
        if not acct["positions"]:
            print("    (No open positions)")
        for symbol, pos in acct["positions"].items():
            shield = "protected" if symbol in acct["protected_symbols"] else "NO STOP"
            print(
                f"    - {symbol:<6} : {pos.qty:>8} sh | Entry: ${float(pos.avg_entry_price):>9,.2f} | "
                f"P&L: ${float(pos.unrealized_pl):>10,.2f} | {shield}"
            )
        print("-" * 60)
        print("  Open Orders:")
        if not acct["open_orders"]:
            print("    (None)")
        for order in acct["open_orders"]:
            print(
                f"    - {order.symbol:<6} : {AlpacaBroker._order_side(order).upper():<4} "
                f"{order.qty} @ {AlpacaBroker._order_type(order).upper()}"
            )
        print("=" * 60 + "\n")


# ==============================================================================
# 9. SETUP DOCUMENTATION PRINTER
# ==============================================================================

def print_setup_instructions():
    print("""
================================================================================
                    FORGE-TRADER SETUP & AUTOSTART GUIDE
================================================================================

1. PREREQUISITES & API KEYS:
   - Alpaca Paper Account: https://app.alpaca.markets/signup
   - Anthropic Claude API Key: https://console.anthropic.com/

2. CONFIGURE LOCAL .env FILE:
   Copy .env.example to .env and fill in your keys:
   -----------------------------------------------------------------------------
   ALPACA_API_KEY=your_alpaca_paper_key_here
   ALPACA_SECRET_KEY=your_alpaca_paper_secret_here
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ALPACA_PAPER=True
   CLAUDE_MODEL=claude-opus-5
   CLAUDE_EFFORT=high
   WATCHLIST=AAPL,MSFT,NVDA,AMZN,GOOGL,TSLA
   MAX_POSITION_PERCENT=0.10
   MIN_CASH_BUFFER_PERCENT=0.20
   HARD_STOP_LOSS_PERCENT=0.10
   DAILY_LOSS_LIMIT_PERCENT=0.03
   -----------------------------------------------------------------------------

   (Run 'python forge_trader.py --models' to see every selectable model, its
    pricing, and which agent is currently routed to it.)

3. CONFIGURE SILENT AUTOSTART ON LAPTOP BOOT:

   Option A: PM2 Process Manager (Recommended)
   -----------------------------------------------------------------------------
   npm install pm2 -g
   # On Windows (in admin PowerShell):
   npm install pm2-windows-startup -g
   pm2-startup install

   # Start background scheduled daemon:
   pm2 start forge_trader.py --name "forge-trader" --interpreter python -- --schedule
   pm2 save

   Option B: Windows Task Scheduler (Native)
   -----------------------------------------------------------------------------
   1. Win + R -> 'taskschd.msc' -> Create Basic Task
   2. Trigger: 'When I log on'
   3. Action: 'Start a program'
   4. Program/script: Browse to 'pythonw.exe' (in your virtualenv)
   5. Arguments: forge_trader.py --schedule
   6. Start in: The folder containing forge_trader.py

   Option C: systemd (Linux)
   -----------------------------------------------------------------------------
   Create /etc/systemd/system/forge-trader.service:
     [Unit]
     Description=Forge-Trader paper trading daemon
     After=network-online.target

     [Service]
     WorkingDirectory=/path/to/forge-trader
     ExecStart=/path/to/venv/bin/python forge_trader.py --schedule
     Restart=on-failure

     [Install]
     WantedBy=multi-user.target

   Then: sudo systemctl enable --now forge-trader
================================================================================
""")


# ==============================================================================
# 10. CLI ENTRY POINT & SCHEDULER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="FORGE-TRADER Multi-Agent Paper Trading Engine")
    parser.add_argument("--run-once", action="store_true", help="Execute one immediate trading cycle")
    parser.add_argument("--dry-run", action="store_true", help="Run debate & risk checks without placing orders")
    parser.add_argument("--reconcile", action="store_true", help="Attach protective stops to unprotected positions")
    parser.add_argument("--schedule", action="store_true", help="Run scheduler daemon for automated daily execution")
    parser.add_argument("--status", action="store_true", help="Display Alpaca account metrics & positions")
    parser.add_argument("--setup", action="store_true", help="Print complete setup and autostart instructions")
    parser.add_argument("--models", action="store_true", help="List selectable Claude models, pricing, and current routing")
    parser.add_argument("--model", metavar="ID", help="Model for every agent (e.g. claude-opus-5, claude-opus-4-8)")
    parser.add_argument("--analyst-model", metavar="ID", help="Override the model for the Bull/Bear/Risk agents")
    parser.add_argument("--pm-model", metavar="ID", help="Override the model for the Portfolio Manager agent")
    parser.add_argument("--effort", metavar="LEVEL", choices=sorted(VALID_EFFORT_LEVELS),
                        help="Reasoning effort: low, medium, high, xhigh, max")

    args = parser.parse_args()

    if args.setup:
        print_setup_instructions()
        return

    config = Config()
    apply_model_overrides(config, args)

    if args.models:
        print_model_catalog(config)
        return

    if not config.alpaca_api_key or not config.anthropic_api_key:
        print("\n[ERROR] Missing API keys. Ensure ALPACA_API_KEY and ANTHROPIC_API_KEY are in your environment or .env file.")
        print("Run 'python forge_trader.py --setup' for instructions.\n")
        sys.exit(1)

    trader = ForgeTrader(config)

    if args.status:
        trader.display_status()
    elif args.reconcile:
        trader.reconcile()
    elif args.dry_run:
        trader.run_cycle(dry_run=True)
    elif args.run_once:
        trader.run_cycle(dry_run=False)
    elif args.schedule:
        scheduler = BlockingScheduler(timezone="America/New_York")
        scheduler.add_job(
            trader.run_cycle,
            trigger=CronTrigger(
                hour=config.scheduled_hour_est,
                minute=config.scheduled_min_est,
                day_of_week="mon-fri",
                timezone="America/New_York",
            ),
            args=[False],
            id="trading_cycle",
            misfire_grace_time=900,
            coalesce=True,
        )
        # Pre-market entries queue until the open, so sweep for unprotected
        # positions once the market has actually been trading.
        scheduler.add_job(
            trader.reconcile,
            trigger=CronTrigger(
                hour=config.reconcile_hour_est,
                minute=config.reconcile_min_est,
                day_of_week="mon-fri",
                timezone="America/New_York",
            ),
            id="stop_reconciliation",
            misfire_grace_time=900,
            coalesce=True,
        )
        logger.info(
            f"Daemon armed. Trading cycle {config.scheduled_hour_est:02d}:{config.scheduled_min_est:02d} ET, "
            f"stop reconciliation {config.reconcile_hour_est:02d}:{config.reconcile_min_est:02d} ET (Mon-Fri)."
        )
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler daemon shut down gracefully.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
