# Hermes Token Usage Plugin

## Purpose

Surface token usage from the local Hermes database directly in the CLI.
Produces lifetime totals, a per-model breakdown, and a per-session breakdown,
all filterable by time window, model, profile, and session. All user-facing
labels are config-driven; nothing is hardcoded.

## CLI Interface

Install:

```bash
hermes plugins install priyankarpal/hermes-agent-token-usages --enable
```

If you already had the plugin installed, update it so Hermes picks up the new CLI arguments:

```bash
hermes plugins update token-usage
```

Invoke:

```bash
hermes tokens [--window 7d|30d|90d|lifetime] [--model <model>] [--session <id>] [--format table|json] [--profile <profile>] [--timeline hour|day|month]
```

| Argument | Values | Meaning |
|----------|--------|---------|
| `--window` | `lifetime`, `7d`, `30d`, `90d` | Time window for aggregation |
| `--model` | <model name> | Filter to a specific model |
| `--session` | <session id> | Drill down into one session's model/billing rows |
| `--profile` | <profile_name> | Filter to a specific profile |
| `--format` | `table`, `json` | Output format |
| `--timeline` | `hour`, `day`, `month` | Show usage timeline grouped by time bucket with a simple bar chart |

## Feature 1: Current session

Every normal report identifies the **current session** — the most recent
active session by `last_activity_at`. It appears:

* In the report header/meta section (`Current Session` row).
* In the per-session table, marked with a trailing `*` next to the session id.
* In JSON output under the `current_session` key.

## Feature 2: Token Usage Timeline

`--timeline hour|day|month` groups sessions into time buckets and renders a
simple ASCII bar chart of total tokens per bucket, ordered chronologically.
Use it to spot usage patterns over time:

```bash
hermes tokens --timeline day     # usage per day
hermes tokens --timeline hour    # usage per hour
hermes tokens --timeline month   # usage per month
```

In JSON output, the timeline appears under `timeline_granularity` and
`timeline_buckets`.

## Configuration

All configuration lives under `token_plugin:` in `~/.hermes/config.yaml`
(or `TOKEN_PLUGIN_*` environment variables):

| Config key | Env var | Default | Description |
|------------|---------|---------|-------------|
| `token_plugin.db_path` | `TOKEN_PLUGIN_DB_PATH` | `~/.hermes/state.db` | Path to the Hermes state SQLite database (read-only). |
| `token_plugin.default_window` | `TOKEN_PLUGIN_DEFAULT_WINDOW` | `lifetime` | Default time window. |
| `token_plugin.include_archived` | `TOKEN_PLUGIN_INCLUDE_ARCHIVED` | `false` | Include archived sessions in totals. |
| `token_plugin.output_format` | `TOKEN_PLUGIN_OUTPUT_FORMAT` | `table` | `table` or `json`. |
| `token_plugin.max_sessions` | `TOKEN_PLUGIN_MAX_SESSIONS` | `50` | Max sessions to list in the per-session breakdown. |
| `token_plugin.profile` | `TOKEN_PLUGIN_PROFILE` | `` | Optional `profile_name` filter applied to all queries. |
|| `token_plugin.currency_label` | `TOKEN_PLUGIN_CURRENCY_LABEL` | `USD` | Currency label for cost columns (USD only; no FX conversion). ||

Labels and column headers are config-driven under `token_plugin.labels:*`; unset
labels fall back to the key name itself.

## Pricing

The DB stores claimed cost **totals**, not per-token **rates**, so the plugin
never fabricates a `USD 0.0000` price:

* When `token_plugin.pricing` has an entry for the model (exact match, else the
  longest configured prefix match), estimated cost is computed per model as
  `(input_tokens / 1M) × input_per_1m + (output_tokens / 1M) × output_per_1m`,
  and per-model costs sum exactly to the window total.
* When no pricing entry exists for a model, its cost shows `n/a` — honest
  rather than a fabricated `USD 0.0000`. The window total shows `n/a` if any
  model in it lacks pricing.

| Config key | Env var | Default | Description |
|------------|---------|---------|-------------|
| `token_plugin.pricing.<model>.input_per_1m` | `TOKEN_PLUGIN_PRICING_<MODEL>_INPUT_PER_1M` | — | Estimated USD per 1M input tokens for `<model>`. |
| `token_plugin.pricing.<model>.output_per_1m` | `TOKEN_PLUGIN_PRICING_<MODEL>_OUTPUT_PER_1M` | — | Estimated USD per 1M output tokens for `<model>`. |

Model names match exactly, or by longest configured prefix (e.g.
`nvidia/nemotron-3.5` covers all that provider's models). Pricing is per-user
config; there is no shared price list. Add pricing only for the models you
actually want priced — everything else stays `n/a`.

### Future: opt-in provider API (not implemented)

A future option is an opt-in `token_plugin.pricing_source` config pointing at a
billing endpoint the plugin polls for per-model rates. That is deliberately
**not** implemented here: it breaks the plugin's no-network guarantee, and the
DB holds no rates to derive them from. Leave `token_plugin.pricing` unset and
cost columns will show `n/a` until you opt in.

## Database

Reads only from `~/.hermes/state.db`. Two independent safety layers guarantee
the Hermes state database is never written, locked, or modified:

1. **URI `mode=ro`** — the database is opened with a read-only file descriptor,
   so SQLite cannot write at the OS level.
2. **`PRAGMA query_only = ON`** — SQLite rejects every INSERT/UPDATE/DELETE/
   CREATE/DROP/ALTER statement at runtime.

Only `SELECT` statements are executed. Tables used: `sessions` and
`session_model_usage`. Never writes to the database.

## Example output

Running `hermes tokens` (default `lifetime` window, `table` format):

```text
┌──────────┬───────────────────────────────┐
│ Key      │ Value                         │
├──────────┼───────────────────────────────┤
│ Database │ /home/ubuntu/.hermes/state.db │
│ Window   │ Lifetime                      │
│ Profile  │ —                             │
│ Format   │ table                         │
└──────────┴───────────────────────────────┘

Token Usage — Lifetime Totals

┌───────────────────┬────────────┐
│ Sessions          │ Value      │
├───────────────────┼────────────┤
│ Sessions          │ 34         │
│ Input Tokens      │ 15.5M      │
│ Output Tokens     │ 1.6M       │
│ Cache Read        │ 429.4M     │
│ Cache Write       │ 0          │
│ Reasoning         │ 632.9K     │
│ Total Tokens      │ 17.1M      │
│ API Calls         │ 2.3K       │
│ Est. Cost (USD)   │ n/a        │
│ Actual Cost (USD) │ n/a        │
└───────────────────┴────────────┘

Token Usage — Per-Model Breakdown

┌──────────────────────────┬──────────┬──────────────┬───────────────┬────────────┬──────────────┬─────────┬───────────┬─────────────────┐
│ Model                    │ Sessions │ Input Tokens │ Output Tokens │ Cache Read │ Total Tokens │ Share % │ API Calls │ Est. Cost (USD) │
├──────────────────────────┼──────────┼──────────────┼───────────────┼────────────┼──────────────┼─────────┼───────────┼─────────────────┤
│ nvidia/nemotron-3.5-sup… │ 24       │ 15.2M        │ 1.6M          │ 418.1M     │ 16.9M        │ 98.4    │ 2.2K      │ n/a               │
│ nvidia/nemotron-3-ultra… │ 7        │ 3.2M         │ 196.5K        │ 48.1M      │ 3.4M         │ 19.7    │ 420       │ n/a               │
│ private/nvidia/nemotron… │ 24       │ 149.1K       │ 13.1K         │ 0          │ 162.2K       │ 0.9     │ 94        │ n/a               │
│ stepfun/step-3.7-flash:… │ 1        │ 13.7K        │ 170           │ 1.7K       │ 13.9K        │ 0.1     │ 1         │ n/a               │
└──────────────────────────┴──────────┴──────────────┴───────────────┴────────────┴──────────────┴─────────┴───────────┴─────────────────┘

Token Usage — Per-Session Breakdown

┌──────────────────────────┬──────────────────────────┬──────────────────┬──────────────────┬──────────────┬───────────────┬────────────┬───────────┬──────────────┬───────────┬─────────────────┐
│ Session ID               │ Model                    │ Started At       │ Last Activity    │ Input Tokens │ Output Tokens │ Cache Read │ Reasoning │ Total Tokens │ API Calls │ Est. Cost (USD) │
├──────────────────────────┼──────────────────────────┼──────────────────┼──────────────────┼──────────────┼───────────────┼────────────┼───────────┼──────────────┼───────────┼─────────────────┤
│ local-e0431b53af21ff312… │ nvidia/nemotron-3.5-sup… │ 2026-11-08 13:58 │ 2026-11-08 17:02 │ 6.2M         │ 682.0K        │ 253.7M     │ 205.6K    │ 6.9M         │ 922       │ n/a             │
│ local-a12cc1362c85e6095… │ nvidia/nemotron-3.5-sup… │ 2026-11-19 12:17 │ 2026-11-19 12:45 │ 1.9M         │ 106.8K        │ 15.0M      │ 60.7K     │ 2.1M         │ 136       │ n/a             │
└──────────────────────────┴──────────────────────────┴──────────────────┴──────────────────┴──────────────┴───────────────┴────────────┴───────────┴──────────────┴───────────┴─────────────────┘
```

The per-session table lists the top sessions by total token count, capped at
`max_sessions` (default 50).

The report also surfaces two ratio columns: **Cache Ratio** (cache reads ÷ real
tokens, per totals/model/session) and **Share %** (a model's share of *that
session's* tokens, not lifetime — so shares sum to ~100 within a session).

## Module layout

| Module | Responsibility |
|--------|----------------|
| `__init__.py` | Package entry; exports `register(ctx)` |
| `plugin.py` | Hermes plugin registration (`register_cli_command`) |
| `config.py` | Config loading (`config.yaml` / `TOKEN_PLUGIN_*` env) |
| `db.py` | Read-only SQLite connection (`mode=ro`) |
| `domain.py` | Entities + value objects (Session, ModelUsage, Window, Currency, UsageReport) |
| `service.py` | Report use case: DB queries + `TokenUsageService` |
| `render.py` | Formatters + text/JSON rendering |
| `cli.py` | Argparse + CLI handler + backward-compatible `run(ns, cfg)` |

## Requirements

* Python stdlib only (`sqlite3`, `argparse`, `json`).
* PyYAML is used when available (already a Hermes dependency); a small
  built-in fallback parser handles simple config files.
