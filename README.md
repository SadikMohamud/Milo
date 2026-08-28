# FORGE-TRADER

Autonomous multi-agent **paper** trading engine. Four Claude agents debate each watchlist
ticker, a non-LLM risk engine gets the final word, and approved orders go to Alpaca's paper
API with a protective stop attached.

> Paper trading only. The broker client hard-fails at startup if `ALPACA_PAPER` is not `True`,
> and it always constructs the Alpaca client with `paper=True`. Nothing here is investment advice.

## Pipeline

```
yfinance  ->  Bull -> Bear -> Risk -> PM (JSON verdict)  ->  Risk engine  ->  Alpaca paper
(price,        adversarial Claude debate                    hard limits,     market order
 SMA/RSI/ATR,  (Anthropic API)                              non-LLM         + GTC stop-loss
 headlines)                                                                       |
                                    SQLite audit log (decisions, executions, events)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys
python forge_trader.py --setup
```

Keys needed: an [Alpaca paper](https://app.alpaca.markets/signup) key/secret and an
[Anthropic API key](https://console.anthropic.com/).

## Usage

| Command | What it does |
| --- | --- |
| `python forge_trader.py --dry-run` | Full debate + risk checks, no orders placed |
| `python forge_trader.py --run-once` | One live paper cycle |
| `python forge_trader.py --reconcile` | Attach stop-losses to any unprotected long position |
| `python forge_trader.py --schedule` | Daemon: cycle 08:30 ET, reconciliation 10:00 ET, Mon–Fri |
| `python forge_trader.py --status` | Account, positions, stop coverage, open orders |
| `python forge_trader.py --setup` | Setup + PM2 / Task Scheduler / systemd autostart guide |

## Risk guardrails

These are enforced in code, after the agents have spoken — the LLM can only ever propose a
smaller trade than the limits allow, never a larger one.

| Guardrail | Env var | Default |
| --- | --- | --- |
| Max single-position size (NAV %, net of existing exposure) | `MAX_POSITION_PERCENT` | 10% |
| Minimum cash buffer held back | `MIN_CASH_BUFFER_PERCENT` | 20% |
| Hard stop-loss below fill | `HARD_STOP_LOSS_PERCENT` | 10% |
| Daily loss limit (halts the whole cycle) | `DAILY_LOSS_LIMIT_PERCENT` | 3% |
| Minimum conviction to open a position | `MIN_CONVICTION` | 0.65 |

Also enforced: no BUY without a position-size headroom check, no SELL without a long position
to sell, no duplicate order while an entry is still pending, and out-of-range values in `.env`
are clamped to sane bounds rather than trusted.

### Stop-loss handling

Every filled BUY gets a companion GTC stop, sized to the **actual filled quantity** and priced
off the **actual fill price**. The PM agent's suggested stop is used only if it sits in a sane
band (between 2% and 2× the hard stop below the fill); otherwise the hard default applies.

The scheduled cycle runs pre-market at 08:30 ET, so entries queue until the open and cannot be
stopped-out-protected at submission time. `--reconcile` (scheduled at 10:00 ET) sweeps every
long position and attaches a stop to any that lacks one. A SELL first cancels the resting stop,
otherwise Alpaca holds those shares and the exit is rejected.

## Audit trail

Everything lands in SQLite (`DB_PATH`, default `forge_trader.db`):

- `agent_decisions` — full bull/bear/risk transcripts, PM verdict, and the risk engine's
  approve/reject reason and approved quantity
- `trade_executions` — every order submitted, including stop-losses and failures
- `system_events` — cycle start/complete, loss-limit halts, reconciliation runs

## Tests

```bash
pip install pytest && python -m pytest tests/ -q
```

32 tests cover the risk engine, stop-price banding, PM JSON parsing, config sanitation, and
controller wiring. They stub the broker and agents, so no network or API keys are required.
