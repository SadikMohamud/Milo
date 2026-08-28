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
| `python forge_trader.py --models` | List selectable models, pricing, and agent routing |
| `python forge_trader.py --setup` | Setup + PM2 / Task Scheduler / systemd autostart guide |

## Model selection

Every agent runs on **Claude Opus 5** by default. Any model in the catalog can be used,
and the two roles can be split — the analysts do the reading, the PM makes the call:

| Model ID | Context | $/1M in | $/1M out |
| --- | --- | --- | --- |
| `claude-opus-5` *(default)* | 1M | $5.00 | $25.00 |
| `claude-opus-4-8` | 1M | $5.00 | $25.00 |
| `claude-opus-4-7` / `claude-opus-4-6` | 1M | $5.00 | $25.00 |
| `claude-fable-5` | 1M | $10.00 | $50.00 |
| `claude-sonnet-5` | 1M | $2.00 | $10.00 |
| `claude-sonnet-4-6` | 1M | $3.00 | $15.00 |
| `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

```bash
python forge_trader.py --run-once --model claude-opus-5
python forge_trader.py --run-once --model claude-opus-4-8 --effort xhigh

# Cheap analysts, expensive decision-maker
python forge_trader.py --run-once --analyst-model claude-sonnet-5 --pm-model claude-opus-5
```

Or set `CLAUDE_MODEL`, `ANALYST_MODEL`, `PM_MODEL`, and `CLAUDE_EFFORT` in `.env`.
Effort levels are `low`, `medium`, `high` (default), `xhigh`, `max`.

**Requests are built per model, not one-size-fits-all.** Opus 5, Opus 4.8, Sonnet 5 and
Fable 5 get adaptive thinking (`thinking: {"type": "adaptive"}`) plus `output_config.effort`;
Haiku 4.5 gets neither, because it rejects both. `budget_tokens` is never sent — current
models return a 400 for it. Opus 5 and Fable 5 additionally get server-side refusal
fallbacks, so a declined turn is re-run on a fallback model inside the same call instead
of returning nothing. If any of that is rejected anyway, the engine drops one feature at
a time (fallbacks → structured output → effort → thinking), logging each drop, until the
request goes through — so a model released after this catalog was written still works,
just without the extras.

The PM's verdict is requested as a **server-enforced JSON schema** (`output_config.format`),
not asked for in prose, so the action field can only ever be `BUY`/`SELL`/`HOLD`. Prose
parsing remains as the fallback path.

Each cycle logs its own API spend, e.g.
`Agent spend this cycle: 20 API calls | 48,120 in / 9,430 out tokens | ~$0.48`.
A 5-ticker watchlist is 4 calls per ticker per day. Costs scale with watchlist size and
effort level; the analyst/PM split above is the main lever if a daily Opus 5 run is more
than you want to spend.

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

54 tests cover the risk engine, stop-price banding, PM JSON parsing, per-model request
construction, feature degradation, cost accounting, config sanitation, and controller
wiring. They stub the broker and the API, so no network or API keys are required.
